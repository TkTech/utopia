# -*- coding: utf8 -*-
__all__ = ('BasicClient',)

from utopia.client.core import CoreClient


class BasicClient(CoreClient):
    """
    A basic IRC client that implements typical functionality, such as
    pings and channels.
    """
    def handle_message(self, message):
        getattr(self, 'message_{command}'.format(
            command=message.command.lower()
        ), self.message_not_handled)(message)

    def message_not_handled(self, message):
        """
        Called when a message is recieved for which no handler
        is implemented.
        """
