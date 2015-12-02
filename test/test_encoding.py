# -*- coding: utf-8 -*-
from utopia.client import ProtocolClient, Identity
from utopia.plugins.handshake import HandshakePlugin
from utopia.plugins.protocol import ProtocolPlugin
from utopia.plugins.util import RecPlugin, LogPlugin
from utopia import signals
from test.util import unique_identity


def test_unicode_privmsg():
    """
    Ensure the client can send unicode and also receives unicode.
    """
    TEST_STRING = u'± äöü @ o ↑↑↓↓←→←→BA コナミコマンド'

    client1 = ProtocolClient(
        unique_identity(), 'localhost', plugins=[
            HandshakePlugin,
            LogPlugin(),
            ProtocolPlugin()
        ]
    )

    client2 = ProtocolClient(
        unique_identity(), 'localhost', plugins=[
            HandshakePlugin,
            LogPlugin(),
            ProtocolPlugin()
        ]
    )

    class Container(object):
        pass
    got_message = Container()
    got_message.value = False

    def on_376(client, message):
        client.join_channel('#test')

    def on_join(client, message):
        client.privmsg('#test', TEST_STRING)

    def on_privmsg(client, message):
        got_message.value = (message.args[0] == TEST_STRING)
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
