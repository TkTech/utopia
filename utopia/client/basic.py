# -*- coding: utf8 -*-
__all__ = ('Client', 'Account', 'Network')
from collections import namedtuple, defaultdict
from utopia.client.core import CoreClient
from utopia.client.channel import Channel

_account = namedtuple('Account', ['nickname', 'username', 'realname'])
_network = namedtuple('Network', ['host', 'port', 'ssl', 'password'])


class Account(_account):
    __slots__ = ()

    @classmethod
    def new(cls, nickname, username=None, realname=None):
        return cls(
            nickname=nickname,
            username=username or nickname,
            realname=realname or nickname
        )


class Network(_network):
    __slots__ = ()

    @classmethod
    def new(cls, host, port=6667, ssl=False, password=None):
        return cls(
            host=host,
            port=port,
            ssl=ssl,
            password=password
        )


class Client(CoreClient):
    """
    A basic client providing the generic functionality common to most
    IRC applications.
    """
    def __init__(self, account, network):
        super(Client, self).__init__(
            host=network.host,
            port=network.port,
            ssl=network.ssl
        )
        self._account = account
        self._network = network
        self._handlers = set([self])
        self._single_callback = defaultdict(set)
        self._channels = {}

    def handle_message(self, message):
        """
        Handles a single incoming IRC message by finding suitable registered
        handlers and calling them.
        """
        command = message.command.lower()
        self.do_event(
            'message_{0}'.format(command),
            default='message_not_handled',
            args=(self, message)
        )

        # One-off callbacks added with run_once
        callbacks = self._single_callback[command]
        while callbacks:
            callback = callbacks.pop()
            callback(self, message)

    def do_event(self, method, default=None, args=None, kwargs=None):
        args = args or []
        kwargs = kwargs or {}

        for callback in self._handlers:
            handler = getattr(callback, method, None)
            if handler is None and default:
                handler = getattr(callback, default, None)

            if handler is not None:
                handler(*args, **kwargs)

    def run_once(self, message, callback):
        """
        Adds `callback` as a one-off callback to be called when `message` is
        recieved, and then removed.
        """
        self._single_callback[message].add(callback)

    def add_handler(self, handler):
        """
        Adds `handler` as a handler from this client if it is not
        already registered.
        """
        self._handlers.add(handler)
        return self

    __iadd__ = add_handler

    def remove_handler(self, handler):
        """
        Removes `handler` as a handler from this client.
        """
        self._handlers.discard(handler)
        return self

    __isub__ = remove_handler

    @property
    def account(self):
        return self._account

    @property
    def network(self):
        return self._network

    def event_connected(self):
        if self.network.password:
            self.send('PASS', self.network.password)

        self.send('NICK', self.account.nickname)
        self.send(
            'USER',
            self.account.username,
            '8',
            '*',
            self.account.realname
        )

    def _event_tick(self):
        self.do_event('event_tick', args=(self,))

    def channel(self, name):
        """
        Returns a :class:`Channel` object for `name`.
        """
        if name not in self._channels:
            self._channels[name] = Channel(self, name)
        return self._channels[name]

    __getitem__ = channel

    def message_ping(self, client, message):
        """
        Default handler for server PINGs.
        """
        client.send('PING', *message.args)
