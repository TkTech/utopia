# -*- coding: utf-8 -*-
from itertools import repeat

from nose.tools import timed

from utopia.parsing import unpack_message
from utopia.parsing import unpack_005


def test_parse_full_prefix():
    """
    Ensure we can parse a message with full prefix (nick, user, host).
    """
    prefix, command, args = unpack_message(
        ':TestNick!TestUsername@test.host JOIN :#test\r\n'
    )

    assert(prefix == ('TestNick', 'TestUsername', 'test.host'))
    assert(prefix.nick == 'TestNick')
    assert(prefix.user == 'TestUsername')
    assert(prefix.host == 'test.host')
    assert(command == 'JOIN')
    assert(len(args) == 1)
    assert(args[0] == '#test')


def test_parse_performance():
    """
    Ensure unpacking a simple, best case message never takes longer than
    0.10s.

    Realistically, unpack_message should always take less than 0.01s on
    even an archaic machine.
    """
    @timed(0.10)
    def _timed_parse():
        prefix, command, args = unpack_message(
            ':TestNick!TestUsername@test.host JOIN :#test\r\n'
        )

    for _ in repeat(None, 1000):
        _timed_parse()


def test_parse_server_prefix():
    """
    Ensure we can parse a message with a server-origin prefix.
    """
    prefix, command, args = unpack_message(
        ':irc.test.host 001 TestNick :Welcome to the test server!\r\n'
    )

    assert(prefix == ('irc.test.host', None, None))
    assert(prefix.nick == 'irc.test.host')
    assert(prefix.user is None)
    assert(prefix.host is None)
    assert(command == '001')
    assert(len(args) == 2)
    assert(args[0] == 'TestNick')
    assert(args[1] == 'Welcome to the test server!')


def test_parse_no_prefix():
    """
    Ensure we can parse a message that has no prefix.
    """
    prefix, command, args = unpack_message(
        'ERROR :Closing Link: failed to pass the test.\r\n'
    )

    assert(prefix is None)
    assert(command == 'ERROR')
    assert(len(args) == 1)
    assert(args[0] == 'Closing Link: failed to pass the test.')


def test_parse_005():
    """
    Ensure we can parse a 005 message and unpack it correctly.
    """
    prefix, command, args = unpack_message(
        ':rajaniemi.freenode.net 005 utopiatestbot123 CHANTYPES=# EXCEPTS '
        'INVEX CHANMODES=eIbq,k,flj,CFLMPQScgimnprstz CHANLIMIT=#:120 '
        'PREFIX=(ov)@+ MAXLIST=bqeI:100 MODES=4 NETWORK=freenode KNOCK '
        'STATUSMSG=@+ CALLERID=g :are supported by this server'
    )

    assert(prefix == ('rajaniemi.freenode.net', None, None))
    assert(prefix.nick == 'rajaniemi.freenode.net')
    assert(prefix.user is None)
    assert(prefix.host is None)
    assert(command == '005')
    assert(args == [
        'utopiatestbot123', 'CHANTYPES=#', 'EXCEPTS', 'INVEX',
        'CHANMODES=eIbq,k,flj,CFLMPQScgimnprstz', 'CHANLIMIT=#:120',
        'PREFIX=(ov)@+', 'MAXLIST=bqeI:100', 'MODES=4', 'NETWORK=freenode',
        'KNOCK', 'STATUSMSG=@+', 'CALLERID=g', 'are supported by this server'
    ])

    r, p = unpack_005(args)
    assert(r == ['EXCEPTS', 'INVEX', 'KNOCK'])
    assert(p == {
        'CALLERID': 'g',
        'CHANLIMIT': {'#': 120},
        'CHANMODES': ('eIbq', 'k', 'flj', 'CFLMPQScgimnprstz'),
        'CHANTYPES': ('#',),
        'MAXLIST': {'bqeI': 100},
        'MODES': 4,
        'NETWORK': 'freenode',
        'PREFIX': {'o': '@', 'v': '+'},
        'STATUSMSG': ('@', '+')
    })
