# -*- coding: utf-8 -*-
from utopia.client import IRCClient, Identity
from utopia.plugins.handshake import HandshakePlugin
from utopia.plugins.util import RecPlugin, LogPlugin


def test_handshake_success():
    """
    Ensure the handshake works when configured properly.
    """
    identity = Identity('testbot1', password='password')

    rec_plugin = RecPlugin(terminate_on=('001',))

    client = IRCClient(identity, 'localhost', plugins=[
        HandshakePlugin,
        rec_plugin,
        LogPlugin()
    ])

    result = client.connect()
    assert(result.get() is True)

    client._io_workers.join(timeout=5)
    assert(rec_plugin.did_recieve('001'))
