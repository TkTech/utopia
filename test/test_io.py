# -*- coding: utf-8 -*-
from utopia.client import IRCClient


def test_connect_success():
    client = IRCClient('localhost')
    result = client.connect()
    assert(result.get() is True)
