# -*- coding: utf8 -*-
__all__ = ('MessageCollector',)

import gevent
import gevent.event


class CollectorResults(object):
    def __init__(self, messages, errors):
        self.messages = messages
        self.errors = errors

    def __bool__(self):
        return not bool(self.errors)

    def __repr__(self):
        return '<{0}({1!r}, {2!r})>'.format(
            self.__class__.__name__,
            self.messages,
            self.errors
        )

    def first(self):
        if self.messages:
            return self.messages[0]
        return None

    __nonzero = __bool__


class MessageCollector(object):
    def __init__(self, client):
        self._client = client

        self._collecting = dict()
        self._waiting = dict()
        self._errors = dict()

        self._collected = []
        self._collected_errors = []
        self._ar = None

        self._collecting_recieved = gevent.event.Event()
        self._waiting_recieved = gevent.event.Event()

        client._callbacks.add(self)

    @property
    def client(self):
        return self._client

    def message_not_handled(self, message):
        """
        Called by the BasicClient as a callback when a message
        is recieved that we've asked for.
        """
        command = message.command.lower()

        if command in self._collecting:
            f = self._collecting[command]
            if f is None or f(message):
                # We want to store this until later, when `.get()`
                # is called...
                self._collected.append(message)
                # ... but we also want anything waiting on it to trigger.
                self._collecting_recieved.set()
                self._collecting_recieved.clear()

        if command in self._errors:
            f = self._errors[command]
            if f is None or f(message):
                self._collected_errors.append(message)

        if command in self._waiting:
            f = self._waiting[command]
            if f is None or f(message):
                # `wait_for()` was used with this command.
                self._waiting_recieved.set()
                self._waiting_recieved.clear()

    def wait_for(self, *message_types, **kwargs):
        """
        Waits for a message of type `message_types`. Once recieved, it
        triggers any waiting greenlets and returns the messages collected
        thus far.
        """
        f = kwargs.pop('f', None)
        message_types = [str(m).lower() for m in message_types]

        self._waiting.update((m, f) for m in message_types)

        # Create the AsyncResult which will be triggered when a
        # message being watched for is recieved.
        if self._ar is None:
            self._ar = gevent.event.AsyncResult()
            gevent.spawn(self._wait).link(self._ar)

        return self

    def collect(self, *message_types, **kwargs):
        """
        Collect all messages of type `message_types`.
        """
        f = kwargs.pop('f', None)
        self._collecting.update((str(m).lower(), f) for m in message_types)
        return self

    def errors(self, *message_types, **kwargs):
        """
        Collect all messages of type `message_types`.
        """
        f = kwargs.pop('f', None)
        self._errors.update((str(m).lower(), f) for m in message_types)
        return self

    def get(self, *args, **kwargs):
        """
        A proxy to the underlying gevent AsyncResult object.
        """
        if self._ar:
            return self._ar.get(*args, **kwargs)
        return self._get_response()

    def _wait(self):
        # Block the greenlet until one of the trigger messages
        # is recieived.
        self._waiting_recieved.wait()
        return self._get_response()

    def _get_response(self):
        results = CollectorResults(
            list(self._collected),
            list(self._collected_errors)
        )
        del self._collected[:]
        del self._collected_errors[:]
        return results

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        """
        Detaches the MessageCollector from its Client.
        """
        self.client._callbacks.discard(self)
