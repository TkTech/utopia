# -*- coding: utf-8 -*-
import blinker

namespace = blinker.Namespace()
signal = namespace.signal


class LazySignalProxy(object):
    def __init__(self):
        self.signals = {}

    def __getattr__(self, name):
        if name not in self.signals:
            self.signals[name] = signal(name)

        return self.signals[name]


on_connect = signal('on-connect', """
Triggered when the client connects to the server, but before any
messages are sent.

:param client: The client connecting.
""")

on_disconnect = signal('on-disconnect', """
Triggered when the client disconnects from a server.

:param client: The client disconnecting.
""")

on_raw_message = signal('on-raw-message', doc="""
Triggered whenever a message is received from the server.

:param client: The client receiving this message.
:param message: An IRC message object.
""")

on_registered = signal('on-registered', doc="""
Triggered when registration with the server is completed.
This typically means the client has received RPL_WELCOME.

:param client: The client receiving this message.
""")

on_negotiation_done = signal('on-negotiation-done', doc="""
This needs to be triggered if an IRCv3 negotiation is completed.
This is only required if the capability set its status to
'Negotiation.IN_PROGRESS' previously.

:param client: The client which was part of the negotiation.
:param capability: The name of the capability which was negotiated.
""")

m = LazySignalProxy()
