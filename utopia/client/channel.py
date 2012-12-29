# -*- coding: utf8 -*-
__all__ = ('Channel',)
from functools import wraps
from collections import deque

import gevent

from utopia.protocol.messages import parse_prefix


class Channel(object):
    def channel_queue(f):
        @wraps(f)
        def _f(self, *args, **kwargs):
            for m in f(self, *args, **kwargs):
                self._message_queue.append(m)
        return _f

    def __init__(self, client, name):
        self._name = name
        self._client = client
        self._client.add_handler(self)
        self._users = set()
        self._joined = False

        self._message_queue = deque()
        # Wait at least one second before messages.
        self._message_min_delay = 1.

    @property
    def client(self):
        """
        The client this Channel object is attached to.
        """
        return self._client

    @property
    def name(self):
        """
        The channel name.
        """
        return self._name

    @property
    def users(self):
        """
        A set() containing all the users currently in the channel.
        """
        return self._users

    def join(self, password=None):
        """
        Attempt to join the channel.
        """
        if not self._joined:
            if password:
                self.client.send('JOIN', self.name, password)
            else:
                self.client.send('JOIN', self.name)

    def message_353(self, client, message):
        """
        Handle RPL_NAMREPLY
        """
        to, names = message.args[2:]
        if to == self.name:
            self._users |= set(names.split(' '))

    def message_366(self, client, message):
        """
        Handle RPL_ENDOFNAMES
        """
        to = message.args[1]
        if to == self.name:
            self._joined = True
            self._check_message_queue()

    def message_part(self, client, message):
        """
        Track channel PARTs to keep our user list up to date.
        """
        if message.args[0] == self.name:
            nickname, _, _ = parse_prefix(message.prefix)
            self._users.discard(nickname)

    def message_join(self, client, message):
        """
        Track channel JOINs to keep our user list up to date.
        """
        if message.args[0] == self.name:
            nickname, _, _ = parse_prefix(message.prefix)
            self._users.add(nickname)

    def message_kick(self, client, message):
        """
        Track channel KICKs to keep our user list up to date.
        """
        to, who = message.args[:2]
        if to == self.name:
            self._users.discard(who)
            if who.lower() == self.client.account.nickname.lower():
                # It's us who got kicked (that was mean)
                self._joined = False
                self._users.clear()

    def message_quit(self, client, message):
        """
        Track network QUITs to keep our user list up to date.
        """
        nickname, _, _ = parse_prefix(message.prefix)
        self._users.dicard(nickname)

    @channel_queue
    def send(self, message):
        """
        Sends a PRIVMSG to the channel.
        """
        yield (self.client.send_c, 'PRIVMSG', self.name, message)

    @channel_queue
    def notice(self, message):
        """
        Sends a NOTICE to the channel.
        """
        yield (self.client.send_c, 'NOTICE', self.name, message)

    def _check_message_queue(self):
        """
        Check the channel's message queue. If non-empty, pop a message and
        send it.
        """
        if self._joined and self._message_queue:
            message = self._message_queue.popleft()
            message[0](*message[1:])
        gevent.spawn_later(self._message_min_delay, self._check_message_queue)

    def __contains__(self, name):
        return name.lower() in [u.lower() for u in self._users]
