# -*- coding: utf8 -*-
__all__ = ('Channel',)

from utopia import Errors, Responses


class Channel(object):
    def __init__(self, client, name):
        self._name = name
        self._client = client

    @property
    def client(self):
        return self._client

    @property
    def channel_name(self):
        return self._name

    def names(self):
        """
        Returns a list of all the users in this channel.
        """
        with self.collect(353, 366).wait_for(366) as ar:
            self.send('NAMES', self._name)

            final_names = set()

            for message in ar.get():
                if message.command == '353':
                    to, chan_mode, for_channel, names = message.args
                    if for_channel != self._name:
                        # This was a listing for a channel other than the
                        # one requested.
                        continue

                    final_names.update(names.split())

            return final_names

    def join(self, key=None):
        """
        Joins the channel and waits until it has recieved the names list
        (or an error) before returning.
        """
        responses = (
            Errors.NEEDMOREPARAMS,
            Errors.INVITEONLYCHAN,
            Errors.CHANNELISFULL,
            Errors.NOSUCHCHANNEL,
            Errors.TOOMANYTARGETS,
            Errors.BANNEDFROMCHAN,
            Errors.BADCHANNELKEY,
            Errors.TOOMANYCHANNELS,
            Errors.UNAVAILRESOURCE,
            Responses.ENDOFNAMES
        )

        with self.client.collect(*responses).wait_for(*responses) as ar:
            if key:
                self.client.send('JOIN', self.channel_name, key)
            else:
                self.client.send('JOIN', self.channel_name)

            results = []
            for message in ar.get():
                if message.args[0] == self.channel_name:
                    results.append(message)

            return results
