# -*- coding: utf8 -*-
__all__ = ('MessageCollector',)

import gevent
import gevent.event


class MessageCollector(object):
    def __init__(self, client):
        self._client = client
        self._collecting = set()
        self._waiting = set()
        self._collected = []
        self._ar = None

        self._collecting_recieved = gevent.event.Event()
        self._waiting_recieved = gevent.event.Event()

    @property
    def client(self):
        return self._client

    def collect(self, message_types):
        """
        Collect all messages of type `message_types`.
        """
        message_types = [str(m).lower() for m in message_types]
        self._collecting.update(message_types)
        self._register_for(message_types)

    def __call__(self, client, message):
        """
        Called by the BasicClient as a callback when a message
        is recieved that we've asked for.
        """
        command = message.command.lower()

        if command in self._collecting:
            # We want to store this until later, when `.get()` is called...
            self._collected.append(message)
            # ... but we also want anything waiting on it to trigger.
            self._collecting_recieved.set()
            self._collecting_recieved.clear()

        if command in self._waiting:
            # `wait_for()` was used with this command.
            self._waiting_recieved.set()
            self._waiting_recieved.clear()

    def wait_for(self, *message_types):
        """
        Waits for a message of type `message_types`. Once recieved, it
        triggers any waiting greenlets and returns the messages collected
        thus far.
        """
        message_types = [str(m).lower() for m in message_types]
        self._waiting.update(message_types)
        self._register_for(message_types)

        self._ar = gevent.event.AsyncResult()
        gevent.spawn(self._wait).link(self._ar)
        return self

    def get(self, *args, **kwargs):
        """
        A proxy to the underlying gevent AsyncResult object.
        """
        return self._ar.get(*args, **kwargs)

    def _wait(self):
        self._waiting_recieved.wait()
        collected = list(self._collected)
        del self._collected[:]
        return collected

    def _register_for(self, message_types):
        """
        Ask the client to trigger us any time it recieves any of the
        messages in `message_types`.
        """
        for message_type in message_types:
            self.client._callbacks[message_type].add(self)

    def _unregister_for(self, message_types):
        """
        Stop asking the client to trigger us for messages of types in
        `message_types`.
        """
        for message_type in message_types:
            self.client._callbacks[message_type].discard(self)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        """
        Detaches the MessageCollector from its Client.
        """
        self._unregister_for(self._waiting)
        self._unregister_for(self._collecting)
