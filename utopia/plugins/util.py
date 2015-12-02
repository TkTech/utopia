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
                             client to terminate when received.
        """
        self.terminate_on = terminate_on or tuple()
        self.received = []

    def bind(self, client):
        signals.on_raw_message.connect(
            self.have_raw_message,
            sender=client
        )
        return self

    def have_raw_message(self, client, message):
        self.received.append((message.prefix, message.command, message.args))

        if message.command in self.terminate_on:
            client.terminate()

    def did_receive(self, command):
        for prefix, command_recv, args in self.received:
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

    def have_raw_message(self, client, message):
        self.logger.debug(
            '{client.host}: ({prefix}) {command} {args}'.format(
                client=client,
                prefix=message.prefix,
                command=message.command,
                args=message.args
            )
        )
