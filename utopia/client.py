# -*- coding: utf-8 -*-
import gevent
import gevent.ssl
import gevent.event
import gevent.socket


class IRCClient(object):
    def __init__(self, host, port=6667, ssl=False):
        assert(isinstance(ssl, bool))
        assert(isinstance(port, (int, long)))

        self._host = host
        self._port = port
        self._ssl = ssl
        self._socket = None

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

    def connect(self, timeout=10, source=None, ssl_args=None):
        """
        Connect to the remote IRC server.

        :param timeout: How long to wait before giving up on the connect.
        :param source: The source address to bind to.
        :param ssl_args: A dict of arguments to pass to wrap_socket if using
                         ssl.
        :rtype: gevent.event.AsyncResult
        """
        result = gevent.event.AsyncResult()
        gevent.spawn(
            self._connect,
            timeout=timeout,
            source=source,
            ssl_args=ssl_args
        ).link(result)
        return result

    def _connect(self, timeout, source, ssl_args):
        self._socket = gevent.socket.create_connection(
            (self.host, self.port),
            timeout=timeout,
            source_address=source
        )

        if self.ssl:
            ssl_args = ssl_args or {}
            self._socket = gevent.ssl.wrap_socket(self._socket, **ssl_args)

        return True
