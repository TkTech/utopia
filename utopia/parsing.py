# -*- coding: utf-8 -*-
import textwrap
from collections import namedtuple

# TODO proper documentation


Prefix = namedtuple('Prefix', ['nick', 'user', 'host'])


class RFC1459Message(object):
    def __init__(self, prefix, command, args, _raw=None, **kwargs):
        self.__dict__['prefix'] = prefix
        self.__dict__['command'] = command.upper()
        self.__dict__['args'] = args
        self.__dict__['_raw'] = _raw
        self.__dict__.update(kwargs)

    @classmethod
    def parse(cls, line):
        return cls(*unpack_message(line), raw=line)

    # TODO: build() method

    def as_dict(self):
        return self.__dict__.copy()

    def copy(self):
        return self.__class__(**self.__dict__)

    def __repr__(self):
        return '({self.prefix}, {self.command}, {self.args})'.format(self=self)


def unpack_message(line):
    """
    Unpacks a complete, RFC compliant IRC message, returning the
    [optional] prefix, command, and parameters.

    :param line: An RFC compliant IRC message.
    """
    prefix = None
    trailing = []

    line = line.rstrip()

    if line[0] == ':':
        prefix, line = line[1:].split(' ', 1)
        prefix = unpack_prefix(prefix)
    if ' :' in line:
        line, trailing = line.split(' :', 1)
        args = line.split()
        args.append(trailing)
    else:
        args = line.split()

    try:
        command = args.pop(0)
    except IndexError:
        command = ''

    return prefix, command.upper(), args


def _005_prefix(v):
    v = list(v.replace('(', '').replace(')', ''))
    hlv = int(len(v) / 2)
    return dict([v[i::hlv] for i in range(hlv)])

_005_DATA = [
    (('PREFIX',), _005_prefix),
    (('CHANTYPES', 'STATUSMSG'), tuple),
    (
        ('CHANMODES', 'CMDS', 'STD'),
        lambda v: tuple(map(get_type, v.split(',')))
    ),
    (
        ('MODES', 'MAXCHANNELS', 'NICKLEN', 'MAXBANS',
         'TOPICLEN', 'KICKLEN', 'CHANNELLEN', 'CHIDLEN',
         'SILENCE', 'AWAYLEN', 'WATCH'),
        int
    ),
    (
        ('CHANLIMIT', 'MAXLIST', 'IDCHAN', 'TARGMAX'),
        lambda v: dict(map(lambda x: (x[0], get_type(x[1])),
                           [d.split(':') for d in v.split(',')]))
    )
]


def unpack_005(args):
    """
    Unpacks a complete, RFC compilant 005 (ISUPPORT) IRC message,
    returning a tuple of all unparsed parts of the message and a
    dictionary of all parsed parts.

    :param args: Parameters of an RFC compilant IRC message, as
    returned by `unpack_message`.
    """
    relevant = args[1:-1]
    parsed = dict()
    rest = list()
    for d in relevant:
        if '=' in d:
            k, v = d.split('=', 1)
            k = k.upper()

            # identity function
            fun = lambda v: v

            for keys, f in _005_DATA:
                if k in keys:
                    fun = f
                    break

            parsed[k] = fun(v)
        else:
            rest.append(d)
    return rest, parsed


# ctcp stuff - http://www.irchelp.org/irchelp/rfc/ctcpspec.html
NUL = chr(0)  # null
LF = chr(0o12)  # newline
NL = LF
CR = chr(0o15)  # carriage return
SPC = chr(0o40)  # space

M_QUOTE = chr(0o20)

# everything has to be escaped with M_QUOTE, even M_QUOTE
M_QUOTE_TABLE = {
    NUL: M_QUOTE + '0',
    NL: M_QUOTE + 'n',
    CR: M_QUOTE + 'r',
    M_QUOTE: M_QUOTE * 2
}
# of course we also need to dequote it
# M_QUOTE
M_DEQUOTE_TABLE = dict([(v, k) for k, v in M_QUOTE_TABLE.items()])


def low_quote(s):
    """
    Performs low level quoting on a string (CTCPSPEC).
    """
    for c in M_QUOTE_TABLE:
        s = s.replace(c, M_QUOTE_TABLE[c])
    return s


def low_dequote(s):
    """
    Performs low level dequoting on a string (CTCPSPEC).
    """
    s = iter(s)
    d_s = ''
    for c in s:
        if c == M_QUOTE:
            n = s.next()
            c = M_DEQUOTE_TABLE.get(c+n, n)  # maybe raise an error
        d_s += c
    return d_s

STX = chr(1)  # ctcp marker
X_DELIM = STX

BS = chr(0o134)  # backslash
X_QUOTE = BS

X_QUOTE_TABLE = {
    X_DELIM: X_QUOTE + 'a',
    X_QUOTE: X_QUOTE * 2
}
X_DEQUOTE_TABLE = dict([(v, k) for k, v in X_QUOTE_TABLE.items()])


def ctcp_quote(s):
    """
    Performs ctcp quoting on a string (CTCPSPEC).
    """
    for c in (X_QUOTE, X_DELIM):
        s = s.replace(c, X_QUOTE_TABLE[c])
    return s


def ctcp_dequote(s):
    """
    Performs ctcp dequoting on a string (CTCPSPEC).
    """
    s = iter(s)
    d_s = ''
    for c in s:
        if c == X_QUOTE:
            n = s.next()
            c = X_DEQUOTE_TABLE.get(c+n, n)  # maybe raise an error
        d_s += c
    return d_s


def extract_ctcp(s):
    """
    returns a tuple, (normal_msgs, extended_msgs)

    normal_msgs is a list of strings which were not between 2 ctcp delimiter
    extended_msgs is a list of (tag, data) tuples
    """
    messages = s.split(X_DELIM)

    normal_msgs = list(filter(None, messages[::2]))
    extended_msgs = list()

    # messages[1::2] = extended_msgs
    # but first let's parse them...
    for e_msg in map(ctcp_dequote, filter(None, messages[1::2])):
        tag = e_msg
        data = None
        if SPC in e_msg:
            tag, data = e_msg.split(SPC, 1)
        extended_msgs.append((tag.upper(), data))

    return normal_msgs, extended_msgs


def make_ctcp_string(messages):
    """
    messages is a list containing (tag, data) tuples, data may be None.
    """
    msg_buf = list()

    for tag, data in messages:
        if data is not None:
            s = '{0} {1}'.format(tag.upper(), data)
        else:
            s = tag.upper()
        msg_buf.append(''.join([X_DELIM, ctcp_quote(s), X_DELIM]))

    return ''.join(msg_buf)


def is_channel(target, channel_prefixes='!&#+'):
    """
    Returns True if the target is a valid IRC channel.

    :param target: String to check.
    :param channel_prefixes: A list or string of valid chantypes.
    """
    return len(target) > 1 and target[0] in channel_prefixes


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

    return Prefix(prefix, user, host)


def ssplit(str_, length=420):
    """
    Splits a into multiple lines with a maximum length, without
    breaking words.

    :param str_: The string to split.
    :param length: Maximum line length.
    """
    buf = list()
    for line in str_.split('\n'):
        buf.extend(textwrap.wrap(line.rstrip('\r'), length))
    return buf


def get_type(val, *types):
    if not types:
        types = (int, float, str)
    for f in types:
        try:
            return f(val)
        except ValueError:
            pass
    return val
