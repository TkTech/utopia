# -*- coding: utf-8 -*-
from collections import defaultdict
from functools import wraps
import socket

import gevent
import gevent.ssl
import gevent.pool
import gevent.event
import gevent.queue
import gevent.socket

import utopia.parsing
from utopia import signals
from utopia.plugins.protocol import EasyProtocolPlugin


def async_result(f):
    @wraps(f)
    def _f(*args, **kwargs):
        result = gevent.event.AsyncResult()
        gevent.spawn(
            f,
            *args,
            **kwargs
        ).link(result)
        return result
    return _f


class Identity(object):
    """
    Manages the "identity" of a client, including the nickname,
    username, realname, and server password.
    """
    def __init__(self, nick, user=None, real=None, password=None):
        self._nick = nick
        self._user = user or nick
        self._real = real or nick
        self._password = password

    @property
    def nick(self):
        return self._nick

    @property
    def user(self):
        return self._user

    @property
    def real(self):
        return self._real

    @property
    def password(self):
        return self._password


class CoreClient(object):
    def __init__(self, identity, host, port=6667, ssl=False, plugins=None):
        assert(isinstance(ssl, bool))
        assert(isinstance(port, (int, long)))

        self._host = host
        self._port = port
        self._ssl = ssl
        self._socket = None
        self._identity = identity

        # Outgoing message queue. Used to throttle network
        # writes.
        self._message_queue = gevent.queue.Queue()
        # Message write delay in seconds. 1 second should be more
        # than reasonable as a default. Some networks will send
        # new limits upon registration.
        self._message_delay = 1

        # Used to cleanly shutdown the IO workers on termination.
        self._io_workers = gevent.pool.Group()

        # Maximum number of bytes to read from the socket in one
        # call to recv().
        self._chunk_size = 4096

        # Setup plugins.
        self._plugins = [p.bind(self) for p in plugins or []]

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def ssl(self):
        return self._ssl

    @property
    def socket(self):
        return self._socket

    @property
    def identity(self):
        return self._identity

    @async_result
    def connect(self, timeout=10, source=None, ssl_args=None):
        """
        Connect to the remote IRC server.

        :param timeout: How long to wait before giving up on the connect.
        :param source: The source address to bind to.
        :param ssl_args: A dict of arguments to pass to wrap_socket if using
                         ssl.
        :rtype: gevent.event.AsyncResult
        """
        self._socket = gevent.socket.create_connection(
            (self.host, self.port),
            timeout=timeout,
            source_address=source
        )

        if self.ssl:
            ssl_args = ssl_args or {}
            self._socket = gevent.ssl.wrap_socket(self._socket, **ssl_args)

        # Wait until we can write before continuing.
        gevent.socket.wait_write(self.socket.fileno(), timeout=timeout)
        gevent.spawn(signals.on_connect.send, self)

        # Start our read/write workers.
        read = self._io_workers.spawn(self._io_read)
        # the read greenlet exits (e.g. other end closes connection, timeout)
        # but the write greenlet will still wait for information
        read.link(lambda g: self.terminate())
        # notify everyone, the client disconnected
        # the callable will already be called in its own greenlet, so no
        # need to call send via gevent.spawn
        read.link(lambda g: signals.on_disconnect.send(self))
        self._io_workers.spawn(self._io_write)

        return True

    def _io_read(self):
        # TODO: The cost from using a string for our buffer is probably
        #       pretty high. Evaluate alternatives like bytearray.
        message_buffer = ''
        while True:
            gevent.socket.wait_read(self.socket.fileno())

            message_chunk = ''
            try:
                message_chunk = self.socket.recv(self._chunk_size)
            except socket.error:
                pass

            if not message_chunk:
                # If recv() returned but the result is empty, then
                # the remote end disconnected.
                break

            message_buffer += message_chunk
            while '\r\n' in message_buffer:
                line, message_buffer = message_buffer.split('\r\n', 1)
                message = utopia.parsing.unpack_message(line)
                gevent.spawn(
                    signals.on_raw_message.send,
                    self,
                    prefix=message[0],
                    command=message[1],
                    args=message[2]
                )

    def _io_write(self):
        while True:
            # Block until there's a message to write.
            next_message = self._message_queue.get()
            # gevent will yield on this sendall() if it can't write it
            # all to the socket at once.
            # TODO: Evaluate if we need to worry about trickle attacks.
            #       It's possible for malicious servers to accept writes
            #       very, very slowly. We should probably timeout here.
            self.socket.sendall(next_message)

    def send(self, command, *args):
        """
        Sends an IRC message to the server. The last argument (if any)
        will be prepended by ':'.

        :param command: The command to send (ex: PING, NICK)
        :param *args: Arguments for the given command.
        """
        message = [command]
        if args:
            message.extend(args[:-1])
            message.append(u':' + args[-1])
        message.append('\r\n')

        self._message_queue.put(u' '.join(message))

    def sendraw(self, message, appendrn=True):
        """
        Sends a raw message to the server.

        :param message: The message to send.
        :param appendrn: If True (default) adds \r\n if missing.
        """

        if not message.endswith('\r\n') and appendrn:
            message = message + '\r\n'

        self._message_queue.put(message)

    def terminate(self, block=True):
        """
        Terminate IO workers immediately.
        """
        try:
            self.socket.shutdown(gevent.socket.SHUT_RDWR)
            self.socket.close()
        except (OSError, socket.error):
            # Connection already down
            pass

        self._io_workers.kill(block=block)


class ProtocolClient(CoreClient):
    def action(self, target, action):
        self.ctcp(target, (('ACTION', action),))

    def admin(self, server=''):
        self.sendraw('ADMIN {0}'.format(server))

    def ctcp(self, target, messages):
        '''sends a ctcp request to target.
        messages is a list containing (tag, data) tuples,
        data may be None.'''
        self.privmsg(target, utopia.parsing.make_ctcp_string(messages))

    def ctcp_reply(self, target, messages):
        '''sends a ctcp reply to target.
        messages is a list containing (tag, data) tuples,
        data may be None.'''
        self.notice(target, utopia.parsing.make_ctcp_string(messages))

    def globops(self, text):
        self.sendraw('GLOBOPS :{0}'.format(text))

    def info(self, server=''):
        self.sendraw('INFO {0}'.format(server))

    def invite(self, nick, channel):
        self.sendraw('INVITE {0} {1}'.format(nick, channel))

    def ison(self, nicks):
        self.sendraw('ISON {0}'.format(' '.join(nicks)))

    def join_channel(self, channel, key=''):
        self.sendraw('JOIN {0} {1}'.format(channel, key))

    def kick(self, channel, nick, comment=''):
        self.sendraw('KICK {0} {1} :{2}'.format(channel, nick, comment))

    def links(self, server_mask, remote_server=''):
        cmd = 'LINKS'
        if remote_server:
            cmd += ' ' + remote_server
        cmd += ' ' + server_mask
        self.sendraw(cmd)

    def list(self, channels=None, server=''):
        cmd = 'LIST'
        if channels is not None:
            cmd = 'LIST {0}'.format(','.join(channels))
        cmd += ' ' + server
        self.sendraw(cmd)

    def lusers(self, server=''):
        self.sendraw('LUSERS {0}'.format(server))

    def mode(self, channel, mode, user=''):
        self.sendraw('MODE {0} {1} {2}'.format(channel, mode, user))

    def motd(self, server=''):
        self.sendraw('MOTD {0}'.format(server))

    def names(self, channel=''):
        self.sendraw('NAMES {0}'.format(channel))

    def nick(self, newnick):
        self.sendraw('NICK {0}'.format(newnick))

    def notice(self, target, text):
        for part in utopia.parsing.ssplit(text, 420):
            self.sendraw('NOTICE {0} :{1}'.format(
                target, ''.join(filter(None, part)))
            )

    def oper(self, nick, password):
        self.sendraw('OPER {0} {1}'.format(nick, password))

    def part(self, channel, message=''):
        self.sendraw('PART {0} {1}'.format(channel, message))

    def pass_(self, password):
        self.sendraw('PASS {0}'.format(password))

    def ping(self, target, target2=''):
        self.sendraw('PING {0} {1}'.format(target, target2))

    def pong(self, target, target2=''):
        self.sendraw('PONG {0} {1}'.format(target, target2))

    def privmsg(self, target, text):
        for part in utopia.parsing.ssplit(text, 420):
            self.sendraw('PRIVMSG {0} :{1}'.format(
                target, ''.join(filter(None, part)))
            )

    def privmsg_many(self, targets, text):
        for part in utopia.parsing.ssplit(text, 420):
            self.sendraw('PRIVMSG {0} :{1}'.format(
                ','.join(targets), ''.join(filter(None, part))))

    def quit(self, message=''):
        self.sendraw('QUIT :{0}'.format(message))

    def squit(self, server, comment=''):
        self.sendraw('SQUIT {0} :{1}'.format(server, comment))

    def stats(self, statstype, server=''):
        self.sendraw('STATS {0} {1}'.format(statstype, server))

    def time(self, server=''):
        self.sendraw('TIME {0}'.format(server))

    def topic(self, channel, new_topic=None):
        if new_topic is None:
            self.sendraw('TOPIC {0}'.format(channel))
        else:
            self.sendraw('TOPIC {0} :{1}'.format(channel, new_topic))

    def trace(self, target=''):
        self.sendraw('TRACE {0}'.format(target))

    def user(self, username, realname):
        self.sendraw('USER {0} 0 * :{1}'.format(username, realname))

    def userhost(self, nick):
        self.sendraw('USERHOST {0}'.format(nick))

    def users(self, server=''):
        self.sendraw('USERS {0}'.format(server))

    def version(self, server=''):
        self.sendraw('VERSION {0}'.format(server))

    def wallops(self, text):
        self.sendraw('WALLOPS :{0}'.format(text))

    def who(self, target, op=''):
        self.sendraw('WHO {0} {1}'.format(target, op))

    def whois(self, target):
        self.sendraw('WHOIS {0}'.format(target))

    def whowas(self, nick, max='', server=''):
        self.sendraw('WHOWAS {0} {1} {2}'.format(nick, max, server))


class EasyClient(ProtocolClient):
    def __init__(self, identity, host, port=6667, ssl=False, plugins=None,
                 pubmsg=True):
        plugins = plugins or []
        plugins.extend([EasyProtocolPlugin(pubmsg=pubmsg)])
        ProtocolClient.__init__(self, identity, host, port, ssl, plugins)
