# -*- coding: utf-8 -*-
__all__ = ('unpack_prefix', 'unpack_message')


def unpack_prefix(prefix):
    """
    Unpacks an IRC message prefix.
    """
    host = None
    user = None

    if '@' in prefix:
        prefix, host = prefix.split('@', 1)

    if '!' in prefix:
        prefix, user = prefix.split('!', 1)

    return prefix, user, host


def unpack_message(line):
    """
    Unpacks a complete, RFC compliant IRC message, returning the
    [optional] prefix, command, and parameters.

    :param line: An RFC compliant IRC message.
    """
    prefix = None
    args = []

    # Make sure there's no trailing \r\n.
    line = line.rstrip()

    # Lines beginning with ':' include a true-origin prefix.
    if line[0] == ':':
        prefix, line = line[1:].split(' ', 1)
        prefix = unpack_prefix(prefix)

    if line.find(' :') != -1:
        line, trailing = line.split(' :', 1)
        args = line.split()
        args.append(trailing)
    else:
        args = line.split()

    return prefix, args.pop(0).upper(), args
