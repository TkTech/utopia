# -*- coding: utf-8 -*-
from utopia.client import ProtocolClient, Identity
from utopia.plugins.handshake import HandshakePlugin
from utopia.plugins.protocol import ProtocolPlugin
from utopia.plugins.util import RecPlugin, LogPlugin
from utopia import signals


def test_unicode_privmsg():
    """
    Ensure the client can send unicode and also receives unicode.
    """
    TEST_STRING = u'± äöü @ o ↑↑↓↓←→←→BA コナミコマンド'

    client1 = ProtocolClient(
        Identity('testbot2', password='password'), 'localhost', plugins=[
            HandshakePlugin,
            LogPlugin(),
            ProtocolPlugin()
        ]
    )

    client2 = ProtocolClient(
        Identity('testbot3', password='password'), 'localhost', plugins=[
            HandshakePlugin,
            LogPlugin(),
            ProtocolPlugin()
        ]
    )

    class Container(object):
        pass
    got_message = Container()
    got_message.value = False

    def on_376(client, prefix, target, args):
        client.join_channel('#test')

    def on_join(client, prefix, target, args):
        client.privmsg('#test', TEST_STRING)

    def on_privmsg(client, prefix, target, args):
        got_message.value = (args[0] == TEST_STRING)
        client1.terminate()
        client2.terminate()

    signals.m.on_376.connect(on_376, sender=client1)
    signals.m.on_376.connect(on_376, sender=client2)
    signals.m.on_JOIN.connect(on_join, sender=client1)
    signals.m.on_PRIVMSG.connect(on_privmsg, sender=client2)

    assert(client1.connect().get() is True)
    assert(client2.connect().get() is True)

    client1._io_workers.join(timeout=5)
    client2._io_workers.join(timeout=5)

    assert(got_message.value)
