# -*- coding: utf-8 -*-
from utopia.client import CoreClient, Identity


def test_connect_success():
    identity = Identity('testbot', password='password')
    client = CoreClient(identity, 'localhost')
    result = client.connect()
    assert(result.get() is True)
