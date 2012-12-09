# -*- coding: utf8 -*-
__all__ = ('CoreClient',)

import gevent
import gevent.ssl
import gevent.socket
import gevent.queue

from utopia.protocol import parse_message


class CoreClient(object):
    """
    A minimal client which does nothing other than connect and handle basic
    IO.
    """
    def __init__(self, host, port=6667, ssl=False):
        self._in_queue = gevent.queue.Queue()
        self._out_queue = gevent.queue.Queue()
        self._socket = None
        self._chunk_size = 4096
        self._shutting_down = False
        self._jobs = None
        self._address = (host, port)
        self._ssl = ssl

    def close(self):
        """
        Closes the client connection, attempting to do so gracefully.
        Automatically called when the `Client` is garbage collected.
        """
        self._shutting_down = True
        gevent.joinall(self._jobs)

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
        Connect to the remote server and begin working, returning
        immediately without blocking.
        """
        self._socket = gevent.socket.create_connection(self._address)

        # If we want to connect over SSL we need to use gevent's
        # utility wrapper to setup the socket.
        if self._ssl:
            self._socket = gevent.ssl.wrap_socket(self._socket)

        self._jobs = (
            gevent.spawn(self._read_greenlet),
            gevent.spawn(self._write_greenlet)
        )

    def _read_greenlet(self):
        """
        Handles reading complete lines from the server.
        """
        read_buffer = ''
        while not self._shutting_down:
            read_tmp = self.socket.recv(self._chunk_size)

            # Remote end disconnected, either due to an error or an
            # intentional disconnect (usually KILL).
            if not read_tmp:
                self.close()
                return

            # Handle any complete messages sitting in the buffer.
            read_buffer += read_tmp
            while '\r\n' in read_buffer:
                line, read_buffer = read_buffer.split('\r\n', 1)
                message = parse_message(line)
                self.handle_message(message)

    def _write_greenlet(self):
        """
        Handles writing complete lines to the server.
        """
        while not self._shutting_down:
            to_send = self._out_queue.get()
            while to_send:
                bytes_sent = self.socket.send(to_send)
                to_send = to_send[bytes_sent:]

    def send(self, command, args, c=False):
        """
        Adds a new message to the outgoing message queue. If `c` is `True`,
        the last arugment is prefixed with a colon.
        """
        if c and args:
            args[-1] = ':{0!s}'.format(args[-1])

        message = '{0} {1}\r\n'.format(command, ' '.join(args))
        self._out_queue.put(message.encode('utf8'))

    def handle_message(self, message):
        """
        Called each time a complete message is read from the socket.
        """
        raise NotImplementedError()
