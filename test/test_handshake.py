#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from utopia.client import CoreClient
from utopia.plugins.handshake import HandshakePlugin
from utopia.plugins.util import RecPlugin
from test.util import unique_identity


def test_handshake_success():
    """
    Ensure the handshake works when configured properly.
    """
    identity = unique_identity()

    rec_plugin = RecPlugin(terminate_on=('001',))

    client = CoreClient(identity, 'localhost', plugins=[
        HandshakePlugin,
        rec_plugin
    ])

    result = client.connect()
    assert(result.get() is True)

    client._io_workers.join(timeout=5)
    assert(rec_plugin.did_receive('001'))
