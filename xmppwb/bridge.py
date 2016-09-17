"""
xmppwb.bridge
~~~~~~~~~~~~~

This module implements the main bridging functionality.

:copyright: (c) 2016 by saqura.
:license: MIT, see LICENSE for more details.
"""
import json
import logging
import os
import ssl
import aiohttp
import aiohttp.web

from xmppwb.xmpp import XMPPBridgeBot


class XMPPWebhookBridge:
    """This is the central component: It initializes and connects the
    :class:`XMPPBridgeBot` with the webhook handling part. The webhook part
    consists of an HTTP server listening for incoming webhooks (POST requests),
    and an HTTP client part for sending outgoing webhooks (POST requests).
    """
    def __init__(self, cfg, loop):
        self.loop = loop
        # List of bridges
        self.bridges = list()
        # Mapping of MUC-JID -> Nickname
        self.mucs = dict()
        # Mapping of MUC-JID -> Password
        self.muc_passwords = dict()

        try:
            # Get the optional XMPP address (host, port) if specified
            xmpp_address = tuple()
            if 'host' in cfg['xmpp']:
                xmpp_address = (cfg['xmpp']['host'], cfg['xmpp']['port'])
            # Parse the MUC definitions
            self.get_mucs(cfg)
            if len(self.mucs) == 0:
                logging.info("No MUCs defined.")
        except KeyError:
            raise InvalidConfigError

        # Parse the bridges from the config file
        need_incoming_webhooks = False
        for bridge_cfg in cfg['bridges']:
            bridge = SingleBridge(bridge_cfg, self)
            self.bridges.append(bridge)
            if bridge.has_incoming_webhooks():
                need_incoming_webhooks = True

        # Initialize XMPP client
        self.xmpp_client = XMPPBridgeBot(cfg['xmpp']['jid'],
                                         cfg['xmpp']['password'],
                                         self)
        self.xmpp_client.connect(address=xmpp_address)

        # Initialize HTTP server if needed
        if not need_incoming_webhooks:
            self.http_server = None
            logging.info("No incoming webhooks defined.")
        elif 'incoming_webhook_listener' in cfg:
            bind_address = cfg['incoming_webhook_listener']['bind_address']
            port = cfg['incoming_webhook_listener']['port']
            self.http_app = aiohttp.web.Application(loop=loop)
            self.http_app.router.add_route('POST',
                                           '/',
                                           self.handle_incoming_webhook)
            self.http_handler = self.http_app.make_handler()
            http_create_server = loop.create_server(
                self.http_handler,
                bind_address,
                port)
            self.http_server = loop.run_until_complete(http_create_server)
            logging.info("Listening for incoming webhooks on "
                         "http://{}:{}/".format(bind_address, port))
        else:
            self.http_server = None
            logging.warn("No 'incoming_webhook_listener' in the config even "
                         "though incoming webhooks are defined. Ignoring all "
                         "incoming webhooks.")

        if not self.http_server:
            logging.info("Not listening for incoming webhooks.")

    def process(self):
        self.loop.run_forever()

    async def send_outgoing_webhook(self, outgoing_webhook, msg):
        """This coroutine handles outgoing webhooks: It relays the messages
        received from XMPP and triggers external webhooks.
        """
        from_jid = msg['from']
        username = str(from_jid)
        if 'override_username' in outgoing_webhook:
            username = self.format_jid_string(
                outgoing_webhook['override_username'],
                from_jid,
                msg['type'] == 'groupchat')

        message = msg['body']
        if 'message_template' in outgoing_webhook:
            message = outgoing_webhook['message_template'].format(
                msg=message)

        payload = {
            'text': message,
            'username': username
        }

        if 'override_channel' in outgoing_webhook:
            payload['channel'] = outgoing_webhook['override_channel']

        if 'avatar_url' in outgoing_webhook:
            icon_url = self.format_jid_string(
                outgoing_webhook['avatar_url'],
                from_jid,
                msg['type'] == 'groupchat')
            payload['icon_url'] = icon_url

        # Attachment formatting is useful for integrating with RocketChat.
        if ('use_attachment_formatting' in outgoing_webhook and
                outgoing_webhook['use_attachment_formatting']):
            payload_attachment = {
                'title': "From: {}".format(username),
                'text': message
            }
            if 'attachment_link' in outgoing_webhook:
                payload_attachment['title_link'] = \
                                            outgoing_webhook['attachment_link']
            payload = {
                'attachments': [payload_attachment]
            }

        logging.debug("<-- Sending outgoing webhook. (from '{}')".format(
                                                            from_jid))
        request = await outgoing_webhook['session'].post(
            outgoing_webhook['url'],
            data=json.dumps(payload),
            headers={'content-type': 'application/json'})
        await request.release()
        return

    async def handle_incoming_webhook(self, request):
        """This coroutine handles incoming webhooks: It receives incoming
        webhooks and relays the messages to XMPP."""
        if request.content_type == 'application/json':
            payload = await request.json()
            # print(payload)
        else:
            # TODO: Handle other content types
            payload = await request.post()

        # Disgard empty messages
        if payload['text'] == "":
            return aiohttp.web.Response()

        token = payload['token']
        logging.debug("--> Handling incoming request from token "
                      "'{}'...".format(token))
        username = payload['user_name']
        msg = payload['text']

        for bridge in self.bridges:
            bridge.handle_incoming_webhook(token, username, msg)

        return aiohttp.web.Response()

    def get_mucs(self, cfg):
        """Reads the MUC definitions from the config file."""
        if 'mucs' not in cfg['xmpp']:
            return

        for muc in cfg['xmpp']['mucs']:
            jid = muc['jid']
            nickname = muc['nickname']
            self.mucs[jid] = nickname
            if 'password' in muc:
                self.muc_passwords[jid] = muc['password']

    def format_jid_string(self, string, jid, is_groupchat=False):
        """Formats the given string by replacing all placeholders.

        The placeholders are replaced with corresponding values from the JID.
        """
        formatted_string = ""
        if is_groupchat:
            formatted_string = string.format(
                bare_jid=jid.bare,
                full_jid=jid.full,
                local_jid=jid.local,
                nick=jid.resource,
                jid=jid.full)
        else:
            formatted_string = string.format(
                bare_jid=jid.bare,
                full_jid=jid.full,
                local_jid=jid.local,
                nick=jid.local,
                jid=jid.bare)

        return formatted_string

    def close(self):
        """Closes all open connections, servers and handlers. This is used
        when exiting the bridge.
        """
        if self.http_server:
            logging.info("Closing HTTP server...")
            self.http_server.close()
            self.loop.run_until_complete(self.http_server.wait_closed())
            self.loop.run_until_complete(self.http_handler.
                                         finish_connections(1.0))
            self.loop.run_until_complete(self.http_app.finish())
            logging.info("Closed HTTP server..")

        logging.info("Closing HTTP client sessions...")
        for bridge in self.bridges:
            for webhook in bridge.outgoing_webhooks:
                webhook['session'].close()
        logging.info("Closed HTTP client sessions..")
        logging.info("Disconnecting from XMPP...")
        self.xmpp_client.disconnect()
        logging.info("Disconnected from XMPP.")


class InvalidConfigError(Exception):
    """Raised when the config file is invalid."""
    pass


class SingleBridge:
    def __init__(self, bridge_cfg, main_bridge):
        """Parses a bridge section of the config file and creates a new
        bridge.
        """
        self.main_bridge = main_bridge
        self.xmpp_muc_endpoints = list()
        self.xmpp_normal_endpoints = list()
        self.xmpp_relay_all_normal = False

        self.incoming_webhooks = list()

        self.outgoing_webhooks = list()

        self._parse_xmpp_endpoints(bridge_cfg)
        self._parse_incoming_webhooks(bridge_cfg)
        self._parse_outgoing_webhooks(bridge_cfg)

    def has_incoming_webhooks(self):
        """Returns True if this bridge contains incoming webhooks."""
        return (len(self.incoming_webhooks) != 0)

    def handle_incoming_webhook(self, token, username, msg):
        """Handles an incoming webhook with the given token, username
        and message.
        """
        for incoming_webhook in self.incoming_webhooks:
            if incoming_webhook['token'] != token:
                # This webhook is not handled by this bridge.
                continue

            if username in incoming_webhook['ignore_user']:
                # Messages from this user are ignored.
                continue

            self.send_to_all_xmpp_endpoints(username, msg)

    def send_to_all_xmpp_endpoints(self, username, msg, skip=list()):
        """Send the given message from the given user to all XMPP endpoints
        of this bridge, except for the JIDs in the `skip`-list.
        """
        msg = "{}: {}".format(username, msg)
        for xmpp_normal_jid in self.xmpp_normal_endpoints:
            if xmpp_normal_jid in skip:
                continue

            logging.debug("<-- Sending a normal chat message to XMPP.")
            self.main_bridge.xmpp_client.send_message(
                mto=xmpp_normal_jid,
                mbody=msg,
                mtype='chat',
                mnick=username)

        for xmpp_muc_jid in self.xmpp_muc_endpoints:
            if xmpp_muc_jid in skip:
                continue

            logging.debug("<-- Sending a MUC chat message to XMPP.")
            self.main_bridge.xmpp_client.send_message(
                mto=xmpp_muc_jid,
                mbody=msg,
                mtype='groupchat',
                mnick=username)

    async def handle_incoming_xmpp(self, msg):
        """Handles an incoming XMPP message, from either a normal chat or
        a MUC."""
        # Outgoing webhooks to trigger
        out_webhooks = list()
        from_jid = msg['from']

        if msg['type'] in ('chat', 'normal'):
            if from_jid.bare in self.xmpp_normal_endpoints:
                out_webhooks = self.outgoing_webhooks

                # Relay this message to the other XMPP endpoints of this bridge
                self.send_to_all_xmpp_endpoints(from_jid.local,
                                                msg['body'],
                                                skip=[from_jid.bare])

            elif self.xmpp_relay_all_normal:
                out_webhooks = self.outgoing_webhooks

        elif msg['type'] == 'groupchat':
            # TODO: Handle nickname of private message in MUCs.
            if from_jid.resource == self.main_bridge.mucs[from_jid.bare]:
                # Don't relay messages from ourselves.
                return
            elif from_jid.bare in self.xmpp_muc_endpoints:
                out_webhooks = self.outgoing_webhooks

                # Relay this message to the other XMPP endpoints of this bridge
                self.send_to_all_xmpp_endpoints(from_jid.resource,
                                                msg['body'],
                                                skip=[from_jid.bare])

        else:
            # Only handle normal chats and MUCs.
            return

        # Forward the messages to the outgoing webhooks
        for outgoing_webhook in out_webhooks:
            await self.main_bridge.send_outgoing_webhook(outgoing_webhook, msg)

    def _parse_incoming_webhooks(self, bridge_cfg):
        """Parses the `incoming_webhooks` from this bridge's config file
        section."""
        if 'incoming_webhooks' not in bridge_cfg:
            # No incoming webhooks in this bridge.
            return

        incoming_webhooks = bridge_cfg['incoming_webhooks']
        for incoming_webhook in incoming_webhooks:
            if 'token' not in incoming_webhook:
                raise InvalidConfigError("Invalid config file: "
                                         "'token' missing from outgoing "
                                         "webhook definition.")
            if 'ignore_user' not in incoming_webhook:
                incoming_webhook['ignore_user'] = list()
            self.incoming_webhooks.append(incoming_webhook)

    def _parse_outgoing_webhooks(self, bridge_cfg):
        """Parses the `outgoing webhooks` from this bridge's config file
        section.

        This also sets up the HTTP client session for each webhook."""
        if 'outgoing_webhooks' not in bridge_cfg:
            # No outgoing webhooks in this bridge.
            return

        outgoing_webhooks = bridge_cfg['outgoing_webhooks']

        for outgoing_webhook in outgoing_webhooks:
            if 'url' not in outgoing_webhook:
                raise InvalidConfigError("Error in config file: "
                                         "'url' is missing from an "
                                         "outgoing webhook definition.")

            # Set up SSL context for certificate pinning.
            if 'cafile' in outgoing_webhook:
                cafile = os.path.abspath(outgoing_webhook['cafile'])
                sslcontext = ssl.create_default_context(cafile=cafile)
                conn = aiohttp.TCPConnector(ssl_context=sslcontext)
                session = aiohttp.ClientSession(loop=self.main_bridge.loop,
                                                connector=conn)
            else:
                session = aiohttp.ClientSession(loop=self.main_bridge.loop)
            # TODO: Handle ConnectionRefusedError.
            outgoing_webhook['session'] = session

            self.outgoing_webhooks.append(outgoing_webhook)

    def _parse_xmpp_endpoints(self, bridge_cfg):
        """Parses the `xmpp_endpoints` from this bridge's config file
        section."""
        if 'xmpp_endpoints' not in bridge_cfg:
            raise InvalidConfigError("Error in config file: "
                                     "'xmpp_endpoints' section is missing "
                                     "from a bridge definition.")

        xmpp_endpoints = bridge_cfg['xmpp_endpoints']
        for xmpp_endpoint in xmpp_endpoints:
            # Determine whether the JID corresponds to a MUC or a
            # normal chat:
            if 'muc' in xmpp_endpoint:
                muc_endpoint = xmpp_endpoint['muc']
                if muc_endpoint not in self.main_bridge.mucs:
                    raise InvalidConfigError(
                        "Error in config file: XMPP MUC '{}' was not "
                        "defined in the xmpp.mucs section.".format(
                            muc_endpoint))
                self.xmpp_muc_endpoints.append(muc_endpoint)

            elif 'normal' in xmpp_endpoint:
                normal_endpoint = xmpp_endpoint['normal']
                self.xmpp_normal_endpoints.append(normal_endpoint)

            elif 'relay_all_normal' in xmpp_endpoint:
                if xmpp_endpoint['relay_all_normal'] is True:
                    self.xmpp_relay_all_normal = True

            else:
                raise InvalidConfigError("Error in config file: "
                                         "'xmpp_endpoints' section contains "
                                         "invalid entry. Must be either of "
                                         "type 'muc', 'normal' or "
                                         "'relay_all_normal'.")
