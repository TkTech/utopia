# -*- coding: utf-8 -*-
from utopia import signals
from utopia.client import CoreClient, Identity


def test_connect_success():
    identity = Identity('testbot', password='password')
    client = CoreClient(identity, 'localhost')
    result = client.connect()
    assert(result.get() is True)


def test_disconnect_event():
    identity = Identity('testbot', password='password')

    class ConnectPlugin(object):
        def __init__(self):
            self.got_connect = False
            self.got_disconnect = False

        def bind(self, client):
            signals.on_connect.connect(self.connected, sender=client)
            signals.on_disconnect.connect(self.disconnected, sender=client)

        def connected(self, client):
            self.got_connect = True

        def disconnected(self, client):
            self.got_disconnect = True

    connect_plugin = ConnectPlugin()

    client = CoreClient(identity, 'localhost', plugins=[connect_plugin])
    result = client.connect()
    assert(result.get() is True)

    client.terminate()
    assert(connect_plugin.got_connect)
    assert(connect_plugin.got_disconnect)


