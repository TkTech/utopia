# -*- coding: utf-8 -*-
import utopia.parsing
from utopia import signals


class ProtocolPlugin(object):
    @classmethod
    def bind(cls, client):
        signals.on_raw_message.connect(cls.on_raw, sender=client)

        return cls

    @staticmethod
    def on_raw(client, prefix, command, args):
        getattr(signals.m, 'on_' + command).send(
            client, prefix=prefix, args=args
        )


class EasyProtocolPlugin(ProtocolPlugin):
    @staticmethod
    def on_raw(client, prefix, command, args):
        target = None

        if command in ('NOTICE', 'PRIVMSG'):
            is_priv = command == 'PRIVMSG'
            target = args[0]

            if utopia.parsing.X_DELIM in args[1]:
                normal_msgs, extended_msgs = \
                    utopia.parsing.extract_ctcp(args[1])

                if extended_msgs:
                    for tag, data in extended_msgs:
                        type_ = 'CTCP_' if is_priv else 'CTCPREPLY_'
                        getattr(signals.m, 'on_' + type_ + tag).send(
                            prefix=prefix, target=target, args=data
                        )

                if not normal_msgs:
                    return

                args[1] = ' '.join(normal_msgs)

            if utopia.parsing.is_channel(target):
                if is_priv:
                    command = 'PUBMSG'
                else:
                    command = 'PUBNOTICE'
            elif not is_priv:
                command = 'PRIVNOTICE'
        elif command in ('KICK', 'BAN', 'MODE', 'JOIN', 'PART'):
            target = args[0]
            args = args[1:]

        getattr(signals.m, 'on_' + command).send(
            client, prefix=prefix, target=target, args=args
        )
