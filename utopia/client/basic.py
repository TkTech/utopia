# -*- coding: utf8 -*-
__all__ = ('Client', 'Account', 'Network')
from collections import namedtuple, defaultdict
from utopia.client.core import CoreClient
from utopia.protocol.messages import parse_prefix

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


class Channel(object):
    def __init__(self, client, name):
        self._name = name
        self._client = client
        self._client.add_handler(self)
        self._users = set()

    @property
    def client(self):
        return self._client

    @property
    def name(self):
        return self._name

    @property
    def users(self):
        return self._users

    def join(self, password=None):
        """
        Attempt to join the channel.
        """
        if password:
            self.client.send('JOIN', self.name, password)
        else:
            self.client.send('JOIN', self.name)

    def message_353(self, client, message):
        to, names = message.args[2:]
        if to == self.name:
            self._users |= set(names.split(' '))

    def message_part(self, client, message):
        if message.args[0] == self.name:
            nickname, _, _ = parse_prefix(message.prefix)
            self._users.discard(nickname)

    def message_join(self, client, message):
        if message.args[0] == self.name:
            nickname, _, _ = parse_prefix(message.prefix)
            self._users.add(nickname)

    def message_kick(self, client, message):
        to, by, who = message.args[:2]
        if to == self.name:
            self._users.discard(who)

    def message_quit(self, client, message):
        nickname, _, _ = parse_prefix(message.prefix)
        self._users.dicard(nickname)

    def send(self, message):
        """
        Sends a PRIVMSG to the channel.
        """
        self.client.send_c('PRIVMSG', self.name, message)

    def notice(self, message):
        """
        Sends a NOTICE to the channel.
        """
        self.client.send_c('NOTICE', self.name, message)

    def __contains__(self, name):
        return name.lower() in [u.lower() for u in self._users]


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
        for callback in self._handlers:
            handler = getattr(callback, 'message_{command}'.format(
                command=command
            ), None)
            if handler is None:
                handler = getattr(callback, 'message_not_handled', None)

            if handler is not None:
                self._dispatch_handler(handler, self, message)

        # One-off callbacks added with run_once
        callbacks = self._single_callback[command]
        while callbacks:
            callback = callbacks.pop()
            callback(self, message)

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

    def _dispatch_handler(self, handler, client, message):
        """
        Called to dispatch `message` to `handler` on behalf of `client`.
        Replacing this method allows you to, for example, use threads for
        handlers.
        """
        handler(client, message)

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
