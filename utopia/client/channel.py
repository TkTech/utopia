# -*- coding: utf8 -*-
__all__ = ('Channel',)
import time
from collections import deque

from utopia.protocol.messages import parse_prefix


class Channel(object):
    def __init__(self, client, name):
        self._name = name
        self._client = client
        self._client.add_handler(self)
        self._users = set()
        self._joined = False

        self._message_queue = deque()
        self._message_last_sent = None
        # Wait at least one second before messages.
        self._message_min_delay = 1

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
        self._message_queue.append(message)

    def _check_message_queue(self):
        # Can't do anything if we aren't in the channel.
        if not self._joined or not self._message_queue:
            return len(self._message_queue)

        now = time.time()
        if self._message_last_sent:
            if now < self._message_last_sent + self._message_min_delay:
                # Not enough time has elapsed, don't send anything.
                return

        message = self._message_queue.popleft()
        self.client.send_c('PRIVMSG', self.name, message)
        self._message_last_sent = time.time()

    def notice(self, message):
        """
        Sends a NOTICE to the channel.
        """
        self.client.send_c('NOTICE', self.name, message)

    def __contains__(self, name):
        return name.lower() in [u.lower() for u in self._users]

    def event_tick(self, client, *args, **kwargs):
        self._check_message_queue()
