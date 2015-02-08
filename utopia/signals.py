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
Triggered whenever a message is recieved from the server.

:param client: The client recieving this message.
:param prefix: The IRC message prefix.
:param command: The IRC command received (ex: PING)
:param args: The command arguments recevied.
""")

on_registered = signal('on-registered', doc="""
Triggered when registration with the server is completed.
This typically means the client has recieved RPL_WELCOME.

:param client: The client recieving this message.
""")

m = LazySignalProxy()
