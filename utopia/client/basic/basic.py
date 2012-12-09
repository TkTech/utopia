# -*- coding: utf8 -*-
__all__ = ('BasicClient',)
from collections import defaultdict

import gevent
import gevent.event

from utopia.client.core import CoreClient
from utopia.client.basic.collector import MessageCollector
from utopia.client.basic.channel import Channel


class BasicClient(CoreClient):
    """
    A basic IRC client that implements typical functionality, such as
    pings and channels.
    """
    def __init__(self, *args, **kwargs):
        self._nickname = kwargs.pop('nickname', None)
        self._username = kwargs.pop('username', None)
        self._password = kwargs.pop('password', None)
        self._realname = kwargs.pop('realname', None)

        super(BasicClient, self).__init__(*args, **kwargs)
        self._callbacks = defaultdict(set)
        self._channels = {}

    def connect(self, *args, **kwargs):
        super(BasicClient, self).connect(*args, **kwargs)
        self.event_connected()

    def handle_message(self, message):
        """
        When a message is received, call message_<command>, if it
        exists.
        """
        command = message.command.lower()
        for callback in self._callbacks[command]:
            gevent.spawn(callback, callback, message)

        handler = getattr(self, 'message_{command}'.format(
            command=command
        ), self.message_not_handled)
        gevent.spawn(handler, message)

    def message_not_handled(self, message):
        """
        Called when a message is recieved for which no handler
        is implemented.
        """

    def event_connected(self):
        """
        Called when the connection to the remote server has been
        established.
        """
        # TODO: Passwords, SASL
        self.send('NICK', self._nickname)
        self.send('USER', self._username, '8', '*', self._realname)

    def message_ping(self, message):
        """
        Respond to the servers PING to keep the connection alive.
        """
        self.send('PONG', *message.args)

    def collect(self, *message_types):
        """
        A helper that sets up a new `MessageCollector` to collect messages of
        `message_types` and returns it.
        """
        q = MessageCollector(self)
        q.collect(message_types)
        return q

    def wait_for(self, *message_types):
        """
        A helper that sets up a new `MessageCollector` to wait for messages of
        `message_types` and returns it.
        """
        q = MessageCollector(self)
        q.wait_for(message_types)
        return q

    def channel(self, channel_name):
        """
        Returns a `Channel` object for `channel_name`.
        """
        if channel_name not in self._channels:
            self._channels[channel_name] = Channel(self, channel_name)
        return self._channels[channel_name]
