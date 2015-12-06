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
from utopia.plugins.handshake import HandshakePlugin
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
        # Message write delay in seconds.
        # Set to 0 seconds since it is an undocumented feature for now.
        # Some networks will send new limits upon registration.
        self._message_delay = 0

        # Used to cleanly shutdown the IO workers on termination.
        self._io_workers = gevent.pool.Group()

        # Maximum number of bytes to read from the socket in one
        # call to recv().
        self._chunk_size = 4096

        # Default encoding, for this connection, everything will
        # be sent as this encoding and decoded on arrival using this encoding.
        self._encoding = 'utf-8'

        # Message class which is used for parsing.
        # Plugins can change this to alter parsing (e.g. useful for IRCv3).
        self._message_cls = utopia.parsing.Message

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
        message_buffer = u''
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

            try:
                message_chunk = message_chunk.decode(self._encoding)
            except UnicodeDecodeError:
                # Fallback if the above fails, IRC has no set encoding
                # and a lot of old clients use latin-1 by default
                message_chunk = message_chunk.decode(
                    'iso-8859-1', errors='ignore'
                )

            message_buffer += message_chunk
            while '\r\n' in message_buffer:
                line, message_buffer = message_buffer.split('\r\n', 1)
                message = self._message_cls.parse(line)
                gevent.spawn(
                    signals.on_raw_message.send,
                    self,
                    message=message
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

            if self._message_delay > 0:
                gevent.sleep(self._message_delay)

    def send(self, command, *args):
        """
        Sends an IRC message to the server. The last argument (if any)
        will be prepended by ':'.

        :param command: The command to send (ex: PING, NICK)
        :param args: Arguments for the given command.
        """
        message = [command]
        if args:
            message.extend(args[:-1])
            message.append(u':' + args[-1])
        message = u' '.join(message)

        self.sendraw(message, True)

    def sendraw(self, message, appendrn=True):
        """
        Sends a raw message to the server.

        :param message: The message to send.
        :param appendrn: If True (default) adds \r\n if missing.
        """

        if not message.endswith('\r\n') and appendrn:
            message = message + '\r\n'

        if isinstance(message, unicode):
            message = message.encode(self._encoding)

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
        self.ctcp(target, ((u'ACTION', action),))

    def admin(self, server=None):
        self.sendraw(u'ADMIN {0}'.format(server or u''))

    def ctcp(self, target, messages):
        """
        sends a ctcp request to target.
        messages is a list containing (tag, data) tuples,
        data may be None.
        """
        self.privmsg(target, utopia.parsing.make_ctcp_string(messages))

    def ctcp_reply(self, target, messages):
        """
        sends a ctcp reply to target.
        messages is a list containing (tag, data) tuples,
        data may be None.
        """
        self.notice(target, utopia.parsing.make_ctcp_string(messages))

    def globops(self, text):
        self.sendraw(u'GLOBOPS :{0}'.format(text))

    def info(self, server=None):
        self.sendraw(u'INFO {0}'.format(server or u''))

    def invite(self, nick, channel):
        self.sendraw(u'INVITE {0} {1}'.format(nick, channel))

    def ison(self, nicks):
        self.sendraw(u'ISON {0}'.format(u' '.join(nicks)))

    def join_channel(self, channel, key=None):
        self.sendraw(u'JOIN {0} {1}'.format(channel, key or u''))

    def kick(self, channel, nick, comment=None):
        self.sendraw(u'KICK {0} {1} :{2}'.format(
            channel, nick, comment or u'')
        )

    def links(self, server_mask, remote_server=None):
        cmd = u'LINKS'
        if remote_server is not None:
            cmd += u' ' + remote_server
        cmd += u' ' + server_mask
        self.sendraw(cmd)

    def list(self, channels=None, server=None):
        cmd = u'LIST'
        if channels is not None:
            cmd = u'LIST {0}'.format(u','.join(channels))
        cmd += u' ' + (server or u'')
        self.sendraw(cmd)

    def lusers(self, server=None):
        self.sendraw(u'LUSERS {0}'.format(server or u''))

    def mode(self, channel, mode, user=None):
        self.sendraw(u'MODE {0} {1} {2}'.format(channel, mode, user or u''))

    def motd(self, server=None):
        self.sendraw(u'MOTD {0}'.format(server or u''))

    def names(self, channel=None):
        self.sendraw(u'NAMES {0}'.format(channel or u''))

    def nick(self, newnick):
        self.sendraw(u'NICK {0}'.format(newnick))

    def notice(self, target, text):
        for part in utopia.parsing.ssplit(text, 420):
            self.sendraw(u'NOTICE {0} :{1}'.format(
                target, u''.join(filter(None, part)))
            )

    def oper(self, nick, password):
        self.sendraw(u'OPER {0} {1}'.format(nick, password))

    def part(self, channel, message=None):
        self.sendraw(u'PART {0} {1}'.format(channel, message or u''))

    def pass_(self, password):
        self.sendraw(u'PASS {0}'.format(password))

    def ping(self, target, target2=None):
        self.sendraw(u'PING {0} {1}'.format(target, target2 or u''))

    def pong(self, target, target2=None):
        self.sendraw(u'PONG {0} {1}'.format(target, target2 or u''))

    def privmsg(self, target, text):
        for part in utopia.parsing.ssplit(text, 420):
            self.sendraw(u'PRIVMSG {0} :{1}'.format(
                target, u''.join(filter(None, part)))
            )

    def privmsg_many(self, targets, text):
        for part in utopia.parsing.ssplit(text, 420):
            self.sendraw(u'PRIVMSG {0} :{1}'.format(
                u','.join(targets), u''.join(filter(None, part))))

    def quit(self, message=None):
        self.sendraw(u'QUIT :{0}'.format(message or u''))

    def squit(self, server, comment=None):
        self.sendraw(u'SQUIT {0} :{1}'.format(server, comment or u''))

    def stats(self, statstype, server=None):
        self.sendraw(u'STATS {0} {1}'.format(statstype, server or u''))

    def time(self, server=None):
        self.sendraw(u'TIME {0}'.format(server or u''))

    def topic(self, channel, new_topic=None):
        if new_topic is None:
            self.sendraw(u'TOPIC {0}'.format(channel))
        else:
            self.sendraw(u'TOPIC {0} :{1}'.format(channel, new_topic))

    def trace(self, target=None):
        self.sendraw('TRACE {0}'.format(target or u''))

    def user(self, username, realname):
        self.sendraw(u'USER {0} 0 * :{1}'.format(username, realname))

    def userhost(self, nick):
        self.sendraw(u'USERHOST {0}'.format(nick))

    def users(self, server=None):
        self.sendraw(u'USERS {0}'.format(server or u''))

    def version(self, server=None):
        self.sendraw(u'VERSION {0}'.format(server or u''))

    def wallops(self, text):
        self.sendraw(u'WALLOPS :{0}'.format(text))

    def who(self, target, op=None):
        self.sendraw(u'WHO {0} {1}'.format(target, op or u''))

    def whois(self, target):
        self.sendraw(u'WHOIS {0}'.format(target))

    def whowas(self, nick, max=None, server=None):
        self.sendraw(u'WHOWAS {0} {1} {2}'.format(
            nick, max or u'', server or u'')
        )


class EasyClient(ProtocolClient):
    def __init__(self, identity, host, port=6667, ssl=False, plugins=None,
                 pubmsg=True):
        plugins = plugins or []
        plugins.extend([HandshakePlugin, EasyProtocolPlugin(pubmsg=pubmsg)])
        ProtocolClient.__init__(self, identity, host, port, ssl, plugins)
