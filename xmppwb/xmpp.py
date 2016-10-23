"""
xmppwb.xmpp
~~~~~~~~~~~

This module implements the XMPP specific parts of the bridge.

:copyright: (c) 2016 by saqura.
:license: MIT, see LICENSE for more details.
"""
import logging
from slixmpp import ClientXMPP


class XMPPBridgeBot(ClientXMPP):
    """The XMPP part of the bridge. It is a bot that connects to all specified
    MUCs, listens to incoming messages (from both MUCs and normal chats) and
    sends messages.
    """
    def __init__(self, jid, password, main_bridge):
        ClientXMPP.__init__(self, jid, password)

        self.main_bridge = main_bridge

        self.add_event_handler("session_start", self.session_started)
        self.add_event_handler("message", self.message_received)
        self.add_event_handler("connection_failed", self.connection_failed)
        self.add_event_handler("failed_auth", self.auth_failed)

        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping

    def session_started(self, event):
        """This sets up the XMPP bot once successfully connected. It connects
        to all specified MUCs.
        """
        self.send_presence()
        self.get_roster()

        for muc, nickname in self.main_bridge.mucs.items():
            logging.debug("Joining MUC '{}' using nickname '{}'.".format(
                                                                muc, nickname))
            if muc in self.main_bridge.muc_passwords:
                self.plugin['xep_0045'].join_muc(
                    muc,
                    nickname,
                    wait=True,
                    password=self.main_bridge.muc_passwords[muc])
            else:
                self.plugin['xep_0045'].join_muc(muc,
                                                 nickname,
                                                 wait=True)

        logging.info("Connected to XMPP.")

    async def message_received(self, msg):
        """This coroutine is triggered whenever a message (both normal or from
        a MUC) is received. It relays the message to the bridge.
        """
        logging.debug("--> Received message from XMPP by {}: {}".format(
            msg['from'], msg['body']))

        for bridge in self.main_bridge.bridges:
            await bridge.handle_incoming_xmpp(msg)

    async def connection_failed(self, error):
        """This coroutine is triggered when the connection to the XMPP server
        failed.
        """
        logging.error("Connection to XMPP failed.")

    async def auth_failed(self, error):
        """This coroutine is triggered when the XMPP server has rejected the
        login credentials.
        """
        logging.error("Authetication with XMPP failed.")
