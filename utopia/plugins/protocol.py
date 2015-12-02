# -*- coding: utf-8 -*-
import utopia.parsing
from utopia import signals


class ProtocolPlugin(object):
    def __init__(self):
        """
        A plugin, which handles firing of protocol events. E.g.
        if the client receives a `JOIN` command, this plugin will
        fire a `on_JOIN` event. Every on-event also has a new target
        parameter containing the user/channel the command was sent to,
        for global events this parameter is None.
        """
        self._target_commands = (
            'NOTICE', 'PRIVMSG', 'KICK', 'BAN', 'MODE', 'JOIN', 'PART'
        )

    def bind(self, client):
        signals.on_raw_message.connect(self.on_raw, sender=client)
        signals.m.on_001.connect(self.on_001, sender=client)
        signals.m.on_PING.connect(self.on_ping, sender=client)

        return self

    def on_raw(self, client, message):
        new_message = message.copy()

        new_message.target = None
        if message.command in self._target_commands:
            new_message.target, new_message.args = \
                message.args[0], message.args[1:]

        getattr(signals.m, 'on_' + message.command).send(
            client, message=new_message
        )

    def on_001(self, client, message):
        # We're only interested in the RPL_WELCOME event once,
        # after registration.
        signals.m.on_001.disconnect(self.on_001, sender=client)
        signals.on_registered.send(client)

        # Now set the nick the server gave us
        client.identity._nick = message.args[0]

    def on_ping(self, client, message):
        client.sendraw('PONG {0}'.format(' '.join(message.args[:2])))


class EasyProtocolPlugin(ProtocolPlugin):
    def __init__(self, pubmsg=True):
        """
        A plugin to improve protocol events and make them easier to use
        (e.g. CTCP events).

        :param pubmsg: If True there will be different events for NOTICE
                       and PRIVMSG commands, depending if the command was
                       sent to a channel or directly to the user.
                       PRIVMSG/PRIVNOTICE indicate it was sent to the user,
                       PUBMSG/PUBNOTICE indicate it was sent to a channel.
        """
        ProtocolPlugin.__init__(self)

        self.pubmsg = pubmsg
        self._target_commands = (
            # default values
            'NOTICE', 'PRIVMSG', 'KICK', 'BAN', 'MODE', 'JOIN', 'PART',
            # pubmsg values
            'PRIVNOTICE', 'PUBNOTICE', 'PUBMSG'
        )

        self._isupport = (set(), dict())

    @property
    def isupport(self):
        return self._isupport

    def bind(self, client):
        ProtocolPlugin.bind(self, client)
        signals.m.on_005.connect(self.on_005, sender=client)

        return self

    def on_005(self, client, message):
        r, p = utopia.parsing.unpack_005(message.args)
        self._isupport[0].update(r)
        self._isupport[1].update(p)

    def on_raw(self, client, message):
        message = message.copy()

        if message.command in ('NOTICE', 'PRIVMSG'):
            target = message.args[0]

            if utopia.parsing.X_DELIM in message.args[1]:
                normal_msgs, extended_msgs = \
                    utopia.parsing.extract_ctcp(message.args[1])

                if extended_msgs:
                    is_priv = message.command == 'PRIVMSG'

                    for tag, data in extended_msgs:
                        type_ = 'CTCP' if is_priv else 'CTCPREPLY'

                        # generic on_CTCP or on_CTCPREPLY event
                        generic = message.copy()
                        generic.tag = tag
                        generic.args = data
                        getattr(signals.m, 'on_' + type_).send(
                            client, message=generic
                        )

                        # specific CTCP or CTCPREPLY event, e.g. on_CTCP_VERSION
                        specific = message.copy()
                        specific.tag = tag
                        specific.args = data
                        getattr(signals.m, 'on_{0}_{1}'.format(type_, tag)).send(
                            client, message=specific
                        )

                if not normal_msgs:
                    return

                message.args[1] = ' '.join(normal_msgs)

            if self.pubmsg:
                is_chan = utopia.parsing.is_channel(
                    target, self._isupport[1].get('CHANTYPES', '!&#+')
                )

                # PRIVNOTICE -> user notice
                # PUBNOTICE -> channel notice
                # PRIVMSG -> user message
                # PUBMSG -> channel message
                command = message.command.lstrip('PRIV')
                pf = 'PUB' if is_chan else 'PRIV'
                message.command = pf + command

        ProtocolPlugin.on_raw(self, client, message)


class ISupportPlugin(object):
    def __init__(self, callback=None):
        """
        A plugin to automatically unpack IRC isupport messages.

        :param callback: function which gets called after every 005
                         (isupport) message with the unpacked information
                         (see `utopia.parsing.unpack_005` for datatype).
        """
        self._callback = callback
        self._isupport = (set(), dict())

    @property
    def isupport(self):
        """
        Unpacked isupport.
        """
        return self._isupport

    def __getitem__(self, index):
        return self._isupport[index]

    def bind(self, client):
        signals.m.on_005.connect(self.on_005, sender=client)

        return self

    def on_005(self, client, message):
        r, p = utopia.parsing.unpack_005(message.args)
        self._isupport[0].update(r)
        self._isupport[1].update(p)

        if self._callback is not None:
            self._callback(self._isupport)

