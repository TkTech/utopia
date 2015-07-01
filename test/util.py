# -*- coding: utf-8 -*-
from utopia.client import ProtocolClient, Identity
from utopia.plugins.handshake import HandshakePlugin
from utopia.plugins.protocol import ProtocolPlugin
from utopia.plugins.util import LogPlugin
from utopia import signals
from gevent.event import Event
import itertools

_next_unique_identity = itertools.count().next
_next_unique_channel = itertools.count().next


def unique_identity(password='password'):
    return Identity(
        'testbot{0}'.format(_next_unique_identity()),
        password=password
    )


def unique_channel():
    return '#unique{0}'.format(_next_unique_channel())


class TestVarContainer(object):
    def __init__(self, *args):
        self._vars = dict()
        for arg in args:
            self._vars[arg] = Event()

        # Adds support for blinker weak references.
        # As long as we keep a reference of the callback the signal will
        # arrive. Once the container dies, the callbacks will as well
        self._dumpster = set()

    def set_callback(self, attr):
        def func(*args, **kwargs):
            self.__getattr__(attr).set()

        self._dumpster.add(func)
        return func

    def all_set(self):
        return all(value for attr, value in self.__dict__.iteritems())

    def wait_all(self, timeout=None):
        return all(
            event.wait(timeout=timeout) for attr, event in self._vars.items()
        )

    def __getattr__(self, item):
        if item not in self._vars:
            self._vars[item] = Event()

        return self._vars[item]


def _default_plugins():
    return [HandshakePlugin, LogPlugin(), ProtocolPlugin()]


def get_two_joined_clients(channel=None, protocol_factory=_default_plugins):
    if channel is None:
        channel = unique_channel()

    client1 = ProtocolClient(
        unique_identity(), 'localhost', plugins=protocol_factory()
    )

    client2 = ProtocolClient(
        unique_identity(), 'localhost', plugins=protocol_factory()
    )

    client1._test_joined = Event()
    client2._test_joined = Event()

    def on_376(client, prefix, target, args):
        client.join_channel(channel)

    def on_join(client, prefix, target, args):
        if target == channel and client.identity.nick == prefix[0]:
            client._test_joined.set()

    signals.m.on_376.connect(on_376, sender=client1)
    signals.m.on_376.connect(on_376, sender=client2)
    signals.m.on_JOIN.connect(on_join, sender=client1)
    signals.m.on_JOIN.connect(on_join, sender=client2)

    assert(client1.connect().get() is True)
    assert(client2.connect().get() is True)

    assert client1._test_joined.wait(timeout=5)
    assert client2._test_joined.wait(timeout=5)

    return client1, client2
