# -*- coding: utf8 -*-
__all__ = ('Channel',)

from utopia import Errors, Responses


class Channel(object):
    def __init__(self, client, name):
        self._name = name
        self._client = client
        self._users = {}

    @property
    def client(self):
        return self._client

    @property
    def channel(self):
        return self._name

    def join(self, password=None):
        """
        Attempts to join and waits until it has recieved the names list
        (or an error) before returning.

        :param password: The channel password (key) if needed to join.
        """
        # Possible error responses from JOIN.
        errors = (
            Errors.NEEDMOREPARAMS,
            Errors.INVITEONLYCHAN,
            Errors.CHANNELISFULL,
            Errors.NOSUCHCHANNEL,
            Errors.TOOMANYTARGETS,
            Errors.BANNEDFROMCHAN,
            Errors.BADCHANNELKEY,
            Errors.TOOMANYCHANNELS
        )
        success = (
            Responses.ENDOFNAMES,
        )

        q = self.client.wait_for(
            *success, f=lambda m: m.args[1] == self.channel
        ).errors(
            *errors, f=lambda m: m.args[0] == self.channel
        )

        with q:
            if password:
                self.client.send('JOIN', self.channel, password)
            else:
                self.client.send('JOIN', self.channel)

            return q.get()
