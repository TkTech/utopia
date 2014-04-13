# -*- coding: utf-8 -*)
"""
Utility plugins, typically used for debugging and tests.
"""
import logging

from utopia import signals


class RecPlugin(object):
    def __init__(self, terminate_on=None):
        """
        A utility plugin to log messages that occur dugin
        a clients lifetime.

        :param terminate_on: An iterable of commands that will cause the
                             client to terminate when recieved.
        """
        self.terminate_on = terminate_on or tuple()
        self.recieved = []

    def bind(self, client):
        signals.on_raw_message.connect(
            self.have_raw_message,
            sender=client
        )
        return self

    def have_raw_message(self, client, prefix, command, args):
        self.recieved.append((prefix, command, args))

        if command in self.terminate_on:
            client.terminate()

    def did_recieve(self, command):
        for prefix, command_recv, args in self.recieved:
            if command_recv == command:
                return True
        return False


class LogPlugin(object):
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger('LogPlugin')

    def bind(self, client):
        signals.on_raw_message.connect(
            self.have_raw_message,
            sender=client
        )
        return self

    def have_raw_message(self, client, prefix, command, args):
        self.logger.debug(
            '{client.host}: ({prefix}) {command} {args}'.format(
                client=client,
                prefix=prefix,
                command=command,
                args=args
            )
        )
