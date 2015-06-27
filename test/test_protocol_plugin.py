# -*- coding: utf-8 -*-
from utopia.plugins.handshake import HandshakePlugin
from utopia.plugins.protocol import EasyProtocolPlugin
from utopia.plugins.util import LogPlugin
from utopia import signals
from test.util import TestVarContainer, get_two_joined_clients, unique_channel


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


def test_pubmsg_targets():
    def _plugins():
        return [HandshakePlugin, LogPlugin(), EasyProtocolPlugin(pubmsg=True)]

    channel = unique_channel()
    client1, client2 = get_two_joined_clients(
        channel=channel,
        protocol_factory=_plugins
    )

    c = TestVarContainer(
        'pubmsg', 'privmsg', 'pubnotice', 'privnotice'
    )

    def check_target(expected_target, to_set):
        def callback(client, prefix, target, args):
            if expected_target == target:
                to_set.set()

        check_target._weak = getattr(check_target, '_weak', []) + [callback]
        return callback

    signals.m.on_PUBMSG.connect(
        check_target(channel, c.pubmsg), sender=client1,
    )
    signals.m.on_PRIVMSG.connect(
        check_target(client1.identity.nick, c.privmsg), sender=client1,
    )
    signals.m.on_PUBNOTICE.connect(
        check_target(channel, c.pubnotice), sender=client1
    )
    signals.m.on_PRIVNOTICE.connect(
        check_target(client1.identity.nick, c.privnotice), sender=client1
    )

    client2.privmsg(channel, 'public message')
    client2.privmsg(client1.identity.nick, 'private message')
    client2.notice(channel, 'public notice')
    client2.notice(client1.identity.nick, 'private notice')

    assert c.wait_all(timeout=2)
