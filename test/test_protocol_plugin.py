# -*- coding: utf-8 -*-
from utopia.client import ProtocolClient, Identity
from utopia.plugins.handshake import HandshakePlugin
from utopia.plugins.protocol import EasyProtocolPlugin
from utopia.plugins.util import LogPlugin
from utopia import signals
from test.util import TestVarContainer, get_two_joined_clients


def test_ctcp_events():
    def _plugins():
        return [HandshakePlugin, LogPlugin(), EasyProtocolPlugin()]

    client1, client2 = get_two_joined_clients(protocol_factory=_plugins)

    c = TestVarContainer(
        'got_ctcp', 'got_ctcpreply',
        'got_version', 'got_version_reply'
    )

    signals.m.on_CTCP_VERSION.connect(
        c.set_callback('got_version'), sender=client2
    )
    signals.m.on_CTCPREPLY_VERSION.connect(
        c.set_callback('got_version_reply'), sender=client1
    )
    signals.m.on_CTCP.connect(
        c.set_callback('got_ctcp'), sender=client2
    )
    signals.m.on_CTCPREPLY.connect(
        c.set_callback('got_ctcpreply'), sender=client1
    )

    client1.ctcp(client2.identity.nick, [('VERSION', '')])
    client2.ctcp_reply(client1.identity.nick, [('VERSION', 'utopiatest')])

    assert c.wait_all(timeout=2)
