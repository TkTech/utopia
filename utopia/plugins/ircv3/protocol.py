# coding: utf-8
from itertools import izip_longest

from utopia import signals
from utopia.parsing import Message, pack_prefix

TAG_START = '@'
TAG_DIVIDER = ';'
TAG_VALUE_DIVIDER = '='

CAPABILITY_DISABLED_PREFIX = '-'
CAPABILITY_ACK_REQUIRED_PREFIX = '~'
CAPABILITY_STICKY_PREFIX = '='
CAPABILITY_MODIFIERS = (
    CAPABILITY_DISABLED_PREFIX +
    CAPABILITY_ACK_REQUIRED_PREFIX +
    CAPABILITY_STICKY_PREFIX
)
CAPABILITY_VALUE_DIVIDER = '='


def normalize_capability(capability,
                         modifiers=CAPABILITY_MODIFIERS,
                         divider=CAPABILITY_VALUE_DIVIDER):
    capability = capability.lstrip(modifiers).lower()
    if divider in capability:
        return capability.split(divider, 1)
    return capability, None


class TaggedMessage(Message):
    @classmethod
    def parse(cls, line):
        # TODO: task escaping
        tags = dict()

        message = line
        if line.startswith(TAG_START):
            line = line[len(TAG_START):]
            raw_tags, message = line.split(None, 1)

            for tag in raw_tags.split(TAG_DIVIDER):
                value = None
                if TAG_VALUE_DIVIDER in tag:
                    tag, value = tag.split(TAG_VALUE_DIVIDER, 1)
                tags[tag] = value

        # 'message' was stripped from tags
        message = Message.parse(message)
        return TaggedMessage(_raw=line, tags=tags, **message.as_dict())

    def __repr__(self):
        tags = ';'.join('{}={}'.format(k,v) for k,v in self.tags.items())
        tags = '@' + tags if tags else ''

        return '{tags} {prefix} {command} {args}'.format(
            prefix=pack_prefix(self.prefix),
            command=self.command,
            args=self.args,
            tags=tags
        )


class Negotiation(object):
    DONE = 1
    IN_PROGRESS = 2
    FAILED = 3


class Capability(object):
    def __init__(self):
        pass

    @property
    def name(self):
        raise NotImplementedError

    def is_available(self, value=None):
        raise NotImplementedError

    def enable(self, client, value=None):
        raise NotImplementedError

    def disable(self, client, value=None):
        raise NotImplementedError


class SimpleCapability(Capability):
    def __init__(self, name):
        Capability.__init__(self)

        self._name = name

    @property
    def name(self):
        return self._name

    def is_available(self, value=None):
        return True

    def enable(self, client, value=None):
        return Negotiation.DONE

    def disable(self, client, value=None):
        return Negotiation.DONE


class IRCv31ProtocolPlugin(object):
    # TODO: multi-prefix support.
    # TODO: SASL support.
    def __init__(self, capabilities_to_request=None):
        self.capabilities_to_request = dict()
        for capability in (capabilities_to_request or []):
            if not isinstance(capability, Capability):
                capability = SimpleCapability(capability)
            self.capabilities_to_request[capability.name] = capability

        self._requested_capabilities = set()
        self._negotiating_capabilities = set()
        # A 'False' value indicates the capability is disabled,
        # Anything else means it is enabled, if the value is not 'True'
        # It is the value which was sent with CAP ACK.
        self._capabilities = dict()

    def bind(self, client):
        signals.on_connect.connect(self.have_connected, sender=client)
        signals.on_negotiation_done.connect(self.on_negotiation_done, sender=client)

        signals.m.on_CAP.connect(self.on_cap, sender=client)
        signals.m.on_CAP_LS.connect(self.on_cap_ls, sender=client)
        signals.m.on_CAP_LIST.connect(self.on_cap_list, sender=client)
        signals.m.on_CAP_ACK.connect(self.on_cap_ack, sender=client)
        signals.m.on_CAP_NACK.connect(self.on_cap_nack, sender=client)
        signals.m.on_410.connect(self.on_410, sender=client)
        return self

    def have_connected(self, client):
        # TODO: figure out if this should be done in IRCv3Handshake.
        client.send('CAP', 'LS')

    def on_negotiation_done(self, client, capability):
        # TODO: figure out if we need to be smart about sendinc CAP END.
        self._negotiating_capabilities.discard(capability)
        self._send_cap_end_if_required(client)

    def _send_cap_end_if_required(self, client):
        if (not self._requested_capabilities
                and not self._negotiating_capabilities):
            # All capabilities done
            client.send('CAP', 'END')

    def on_cap(self, client, message):
        target, sub_command = message.args[:2]
        args = message.args[2:]

        getattr(signals.m, 'on_CAP_' + sub_command).send(
            client, args=args
        )

    def on_cap_ls(self, client, args):
        to_request = set()

        for capability in args[0].split():
            # Some 'hidden' IRCv3.2 support (value).
            capability, value = normalize_capability(capability)

            if capability in self._capabilities:
                # We already have that one
                continue

            do_request = False
            if capability in self.capabilities_to_request:
                co = self.capabilities_to_request[capability]
                # For IRCv3.1 value will always be None
                # Still check, since this might happen in IRCv3.2.
                do_request = co.is_available(value)

            if do_request:
                to_request.add(capability)

        if to_request:
            client.send('CAP', 'REQ', ' '.join(to_request))
        else:
            # We are done, no capabilities wanted.
            client.send('CAP', 'END')

        self._requested_capabilities = to_request

    def on_cap_list(self, client, args):
        # Disable all
        for capability in self._capabilities:
            self._capabilities[capability] = False

        # Enable only the enabled.
        for capability in args[0].split():
            capability, value = normalize_capability(capability)
            self._capabilities[capability] = value or True

    def on_cap_ack(self, client, args):
        for orig_capability in args[0].split():
            capability, value = normalize_capability(orig_capability)
            self._requested_capabilities.discard(capability)

            if orig_capability.startswith(CAPABILITY_DISABLED_PREFIX):
                self._capabilities[capability] = False
                func = self.capabilities_to_request[capability].disable
            elif orig_capability.startswith(CAPABILITY_STICKY_PREFIX):
                # TODO: Ignored for now, figure out a better way to handle this
                #       if there is a better way.
                continue
            else:
                self._capabilities[capability] = value or True
                func = self.capabilities_to_request[capability].enable

            if orig_capability.startswith(CAPABILITY_ACK_REQUIRED_PREFIX):
                client.send('CAP', 'ACK', capability)

            status = func(client, value)
            if status == Negotiation.IN_PROGRESS:
                self._negotiating_capabilities.add(capability)
            elif status == Negotiation.FAILED:
                # Negotiation failed, disable the capability.
                client.send('CAP', 'REQ', '-' + capability)
                # TODO: figure out if the capability should be
                #       re-added to _requested_capabilities.

        self._send_cap_end_if_required(client)

    def on_cap_nack(self, client, args):
        for capability in args[0].split():
            capability, value = normalize_capability(capability)
            self._capabilities[capability] = False
            self._requested_capabilities.discard(capability)

        self._send_cap_end_if_required(client)

    def on_410(self, client, message):
        self._negotiating_capabilities = set()
        self._requested_capabilities = set()
        client.send('CAP', 'END')

    # Here would be time to filter non existent CAP commands.
    # def on_421(self, client, message):
    #     pass

    # def on_451(self, client, message):
    #     pass


class IRCv32ProtocolPlugin(IRCv31ProtocolPlugin):
    # Capabilities with values is already implemented in IRCv31ProtocolPlugin.
    # TODO: multiline responses.
    # TODO: metadata
    # TODO: monitor
    def __init__(self, *args, **kwargs):
        IRCv31ProtocolPlugin.__init__(self, *args, **kwargs)

    def bind(self, client):
        IRCv31ProtocolPlugin.bind(self, client)

        client._message_cls = TaggedMessage

        return self

    def have_connected(self, client):
        client.send('CAP', 'LS', '302')
