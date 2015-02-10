# -*- coding: utf-8 -*-
from utopia import signals


class HandshakePlugin(object):
    @classmethod
    def bind(cls, client):
        signals.on_connect.connect(
            cls.have_connected,
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

