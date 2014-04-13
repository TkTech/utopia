# -*- coding: utf-8 -*-
from utopia import signals


class HandshakePlugin(object):
    @classmethod
    def bind(cls, client):
        signals.on_connect.connect(
            cls.have_connected,
            sender=client
        )

        signals.m.on_001.connect(
            cls.have_welcome,
            sender=client
        )

        return cls

    @staticmethod
    def have_connected(client):
        if client.identity.password:
            client.send('PASS', client.identity.password)

        client.send('NICK', client.identity.nick)
        client.send(
            'USER',
            client.identity.user,
            '8',
            '*',
            client.identity.real
        )

    @classmethod
    def have_welcome(cls, client, prefix, args):
        # We're only interested in the RPL_WELCOME event once,
        # after registration.
        signals.m.on_001.disconnect(cls.have_welcome, sender=client)
        signals.on_registered.send(sender=client)
