# -*- coding: utf-8 -*-
from utopia.client import IRCClient, Identity


def test_connect_success():
    identity = Identity('testbot', password='password')
    client = IRCClient(identity, 'localhost')
    result = client.connect()
    assert(result.get() is True)
