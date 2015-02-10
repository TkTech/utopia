# -*- coding: utf-8 -*-
import utopia.parsing
from utopia import signals


class ProtocolPlugin(object):
    def __init__(self):
        """
        A plugin, which handles firing of protocol events. E.g.
        if the client receives a `JOIN` command, this plugin will
        fire a `on_JOIN` event.
        """
        pass

    def bind(self, client):
        signals.on_raw_message.connect(self.on_raw, sender=client)

        return self

    def on_raw(self, client, prefix, command, args):
        getattr(signals.m, 'on_' + command).send(
            client, prefix=prefix, args=args
        )


class EasyProtocolPlugin(ProtocolPlugin):
    def __init__(self, pubmsg=True):
        """
        A plugin to improve protocol events and make them easier to use.
        This plugin adds CTCP events and adds a target keyword argument
        to each event, containing the target the message was sent to.

        :param pubmsg: If True there will be different events for NOTICE
                       and PRIVMSG commands, depending if the command was
                       sent to a channel or directly to the user.
                       PRIVMSG/PRIVNOTICE indicate it was sent to the user,
                       PUBMSG/PUBNOTICE indicate it was sent to a channel.
        """
        ProtocolPlugin.__init__(self)

        self.pubmsg = pubmsg

        self._isupport = (set(), dict())

    def bind(self, client):
        ProtocolPlugin.bind(self, client)
        signals.m.on_005.connect(self.on_005, sender=client)

        return self

    def on_005(self, client, prefix, args):
        r, p = utopia.parsing.unpack_005(args)
        self._isupport[0].update(r)
        self._isupport[1].update(p)

    def on_raw(self, client, prefix, command, args):
        target = None

        if command in ('NOTICE', 'PRIVMSG'):
            target = args[0]

            if utopia.parsing.X_DELIM in args[1]:
                normal_msgs, extended_msgs = \
                    utopia.parsing.extract_ctcp(args[1])

                if extended_msgs:
                    is_priv = command == 'PRIVMSG'

                    for tag, data in extended_msgs:
                        type_ = 'CTCP_' if is_priv else 'CTCPREPLY_'
                        getattr(signals.m, 'on_' + type_ + tag).send(
                            prefix=prefix, target=target, args=data
                        )

                if not normal_msgs:
                    return

                args[1] = ' '.join(normal_msgs)

            if self.pubmsg:
                is_chan = utopia.parsing.is_channel(
                    target, self._isupport[1].get('CHANTYPES', '!&#+')
                )

                # PRIVNOTICE -> user notice
                # PUBNOTICE -> channel notice
                # PRIVMSG -> user message
                # PUBMSG -> channel message
                command = command.lstrip('PRIV')
                pf = 'PUB' if is_chan else 'PRIV'
                command = pf + command
        elif command in ('KICK', 'BAN', 'MODE', 'JOIN', 'PART'):
            target = args[0]
            args = args[1:]

        getattr(signals.m, 'on_' + command).send(
            client, prefix=prefix, target=target, args=args
        )
