# -*- coding: utf8 -*-
__all__ = ('CoreClient',)
import ssl
import errno
import socket
from collections import deque

from utopia.protocol import parse_message


class CoreClient(object):
    """
    A minimal client which does nothing other than connect and handle basic
    IO.
    """
    def __init__(self, host, port=6667, ssl=False):
        self._socket = None
        self._chunk_size = 4096
        self._shutting_down = False
        self._jobs = None
        self._address = (host, port)
        self._ssl = ssl

        # IO Buffers & Queues
        self._in_queue = deque()
        self._out_queue = deque()
        self._read_buffer = ''

    def close(self):
        if self._socket is not None:
            self._socket.close()

    @property
    def host(self):
        """
        The host this `CoreClient` is connected to.
        """
        return self._address[0]

    @property
    def port(self):
        """
        The port this `CoreClient` is connected to.
        """
        return self._address[1]

    @property
    def address(self):
        return self._address

    @property
    def ssl(self):
        """
        ``True`` if this `CoreClient` is communicating over SSL.
        """
        return self._ssl

    @property
    def socket(self):
        """
        The raw gevent socket in use by this `Client`.
        """
        return self._socket

    @property
    def plugins(self):
        """
        The currently loaded plugins on this Client.
        """
        return self._plugins

    def __del__(self):
        """
        Make sure we're closed when we get collected.
        """
        self.close()

    def connect(self):
        """
        Connect to the remote server and begin working.
        """
        self._socket = socket.create_connection(self._address)
        self._socket.setblocking(0)
        if self._ssl:
            self._socket = ssl.wrap_socket(self._socket)

        self.event_connected()

        while True:
            if self._try_read():
                # The other end killed the connection.
                return
            self._try_write()
            yield

    def _try_read(self):
        """
        Handles reading complete lines from the server.
        """
        try:
            read_tmp = self.socket.recv(self._chunk_size)
        except socket.error as e:
            if e.errno == errno.EWOULDBLOCK:
                return
            raise

        # Remote end disconnected, either due to an error or an
        # intentional disconnect (usually KILL).
        if not read_tmp:
            self.close()
            return True

        # Handle any complete messages sitting in the buffer.
        self._read_buffer += read_tmp
        while '\r\n' in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split('\r\n', 1)
            message = parse_message(line)
            self.handle_message(message)

    def _try_write(self):
        """
        Handles writing complete lines to the server.
        """
        if not self._out_queue:
            # Nothing waiting to go out, so nothing to do.
            return

        to_send = self._out_queue.popleft()
        bytes_sent = self.socket.send(to_send)
        if bytes_sent != len(to_send):
            # We didn't send the complete message, add what's left
            # back on the front of the queue.
            self._out_queue.appendleft(to_send[bytes_sent:])

    def send(self, command, *args):
        """
        Adds a new message to the outgoing message queue.
        """
        self._out_queue.append('{command} {args}\r\n'.format(
            command=command, args=' '.join(args)
        ).encode('utf8'))

    def send_c(self, command, *args):
        """
        Same as `send()`, but prefixes the last argument with a colon.
        """
        line = [command]
        line.extend(args[0:-1])
        line.append(':{0}\r\n'.format(args[-1]))
        self._out_queue.append(' '.join(line).encode('utf8'))

    def handle_message(self, message):
        """
        Called each time a complete message is read from the socket.
        """
        raise NotImplementedError()

    def event_connected(self):
        """
        Called when the client has connected to the host.
        """
