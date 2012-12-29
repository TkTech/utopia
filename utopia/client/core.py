# -*- coding: utf8 -*-
__all__ = ('CoreClient',)
import gevent
import gevent.ssl
import gevent.queue
import gevent.socket
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
        self._in_queue = gevent.queue.Queue()
        self._out_queue = gevent.queue.Queue()

    def close(self):
        self._shutting_down = True
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
        The raw socket in use by this `Client`.
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
        self._socket = gevent.socket.create_connection(self._address)
        if self._ssl:
            self._socket = gevent.ssl.wrap_socket(self._socket)

        self.event_connected()
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

    def send(self, command, *args):
        """
        Adds a new message to the outgoing message queue.
        """
        self._out_queue.put('{command} {args}\r\n'.format(
            command=command, args=' '.join(args)
        ).encode('utf8'))

    def send_c(self, command, *args):
        """
        Same as `send()`, but prefixes the last argument with a colon.
        """
        line = [command]
        line.extend(args[0:-1])
        line.append(':{0}\r\n'.format(args[-1]))
        self._out_queue.put(' '.join(line).encode('utf8'))

    def handle_message(self, message):
        """
        Called each time a complete message is read from the socket.
        """
        raise NotImplementedError()

    def event_connected(self):
        """
        Called when the client has connected to the host.
        """
