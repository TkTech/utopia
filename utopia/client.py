# -*- coding: utf-8 -*-
from functools import wraps
import socket

import gevent
import gevent.ssl
import gevent.pool
import gevent.event
import gevent.queue
import gevent.socket

from utopia import signals
from utopia.parsing import unpack_message


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


class IRCClient(object):
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
                message = unpack_message(line)
                gevent.spawn(
                    signals.on_raw_message.send,
                    self,
                    prefix=message[0],
                    command=message[1],
                    args=message[2]
                )
                gevent.spawn(
                    getattr(signals.m, 'on_' + message[1]).send,
                    self,
                    prefix=message[0],
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
