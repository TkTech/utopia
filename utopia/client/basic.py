# -*- coding: utf8 -*-
__all__ = ('Client', 'Account', 'Network', 'client_queue')
import gevent

from functools import wraps
from collections import namedtuple, defaultdict, deque
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


def client_queue(f):
    @wraps(f)
    def _f(self, *args, **kwargs):
        for m in f(self, *args, **kwargs):
            self._message_queue.append(m)
    return _f


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

        self._message_queue = deque()
        # Minimum delay between messages.
        self._message_min_delay = 1.

        # Cached results of the 005 (RPL_ISUPPORT) command.
        self._supported = {}

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

        for callback in list(self._handlers):
            handler = getattr(callback, method, None)
            if handler is None and default:
                handler = getattr(callback, default, None)

            if handler is not None:
                handler(*args, **kwargs)

    def _check_message_queue(self):
        """
        Check the clients's message queue. If non-empty, pop a message and
        send it.
        """
        if self._message_queue:
            message = self._message_queue.popleft()
            message[0](*message[1:])
        gevent.spawn_later(self._message_min_delay, self._check_message_queue)

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

    # ----
    # Channel(s) interaction.
    # ----

    def channel(self, name):
        """
        Returns a :class:`Channel` object for `name`.
        """
        if name not in self._channels:
            self._channels[name] = Channel(self, name)
        return self._channels[name]

    __getitem__ = channel

    @property
    def channels(self):
        """
        A list of all the channels attached to this client.
        """
        return list(self._channels.keys())

    def channels_by_prefix(self, prefix='#'):
        """
        Returns all channels beginning with `prefix` that this client
        is currently in.
        """
        for channel in self.channels:
            if channel.startswith(prefix):
                yield channel

    def channel_limit(self, prefix='#', default=None):
        """
        Returns the maximum number of channels per connection allowed by this
        IRCd for the given channel `prefix`, or `default` if it is not known.
        """
        # The IRCd hasn't told us its channel limitations.
        if 'CHANLIMIT' not in self._supported:
            return default

        chan_limit = self._supported['CHANLIMIT'].split(',')
        for limit_prefix, limit in (p.split(':') for p in chan_limit):
            if limit_prefix == prefix:
                try:
                    return int(limit)
                except ValueError:
                    return default

        return default

    # ----
    # Default message handlers.
    # ----

    def message_ping(self, client, message):
        """
        Default handler for server PINGs.
        """
        client.send('PING', *message.args)

    def message_001(self, client, message):
        # Once we've recieved 001, we can start sending out non-handshake
        # messages.
        self.do_event('event_ready', args=(client,))
        self._check_message_queue()

    def message_005(self, client, message):
        """
        Cache the results of the 005 (RPL_ISUPPORT) response.
        """
        for result in message.args[1:-1]:
            param, _, value = result.partition('=')
            self._supported[param] = value
