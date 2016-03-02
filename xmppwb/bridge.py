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
from collections import defaultdict
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
        self.incoming_normal_mappings = defaultdict(set)
        self.incoming_muc_mappings = defaultdict(set)
        self.outgoing_mappings = defaultdict(list)
        # Mapping of MUC-JID -> Nickname
        self.mucs = dict()
        # Mapping of MUC-JID -> Password
        self.muc_passwords = dict()

        try:
            # Get the optional XMPP address (host, port) if specified
            xmpp_address = tuple()
            if 'host' in cfg['xmpp']:
                xmpp_address = (cfg['xmpp']['host'], cfg['xmpp']['port'])

            self.get_mucs(cfg)
            self.get_outgoing_mappings(cfg)
            self.get_incoming_mappings(cfg)
        except KeyError:
            raise InvalidConfigError

        # Initialize XMPP client
        self.xmpp_client = XMPPBridgeBot(cfg['xmpp']['jid'],
                                         cfg['xmpp']['password'],
                                         self)
        self.xmpp_client.connect(address=xmpp_address)

        # Initialize HTTP server if needed
        incoming_webhooks_count = (len(self.incoming_muc_mappings) +
                                   len(self.incoming_normal_mappings))
        if incoming_webhooks_count == 0:
            self.http_server = None
            logging.info("No incoming webhooks defined.")
        elif 'incoming_webhook_listener' in cfg:
            bind_address = cfg['incoming_webhook_listener']['bind_address']
            port = cfg['incoming_webhook_listener']['port']
            self.http_app = aiohttp.web.Application(loop=loop)
            self.http_app.router.add_route('POST', '/', self.handle_incoming)
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

    async def handle_outgoing(self, outgoing_webhook, msg):
        """This coroutine handles outgoing webhooks: It relays the messages
        received from XMPP and triggers external webhooks.
        """
        from_jid = msg['from']
        username = str(from_jid)
        if 'override_username' in outgoing_webhook:
            if msg['type'] == 'groupchat':
                username = outgoing_webhook['override_username'].format(
                    bare_jid=from_jid.bare,
                    full_jid=from_jid.full,
                    local_jid=from_jid.local,
                    nick=from_jid.resource,
                    jid=from_jid.full)
            else:
                username = outgoing_webhook['override_username'].format(
                    bare_jid=from_jid.bare,
                    full_jid=from_jid.full,
                    local_jid=from_jid.local,
                    nick=from_jid.local,
                    jid=from_jid.bare)

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

    async def handle_incoming(self, request):
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
        msg = payload['user_name'] + ": " + payload['text']
        for xmpp_normal_jid in self.incoming_normal_mappings[token]:
            logging.debug("<-- Sending a normal chat message to XMPP.")
            self.xmpp_client.send_message(mto=xmpp_normal_jid,
                                          mbody=msg,
                                          mtype='chat',
                                          mnick=payload['user_name'])
        for xmpp_muc_jid in self.incoming_muc_mappings[token]:
            logging.debug("<-- Sending a MUC chat message to XMPP.")
            self.xmpp_client.send_message(mto=xmpp_muc_jid,
                                          mbody=msg,
                                          mtype='groupchat',
                                          mnick=payload['user_name'])
        return aiohttp.web.Response()

    def get_mucs(self, cfg):
        """Reads the MUC definitions from the config file."""
        for muc in cfg['xmpp']['mucs']:
            jid = muc['jid']
            nickname = muc['nickname']
            self.mucs[jid] = nickname
            if 'password' in muc:
                self.muc_passwords[jid] = muc['password']

    def get_outgoing_mappings(self, cfg):
        """Reads the outgoing webhook definitions from the config file.

        This also sets up the HTTP client session for each webhook."""
        bridges = cfg['bridges']
        for bridge in bridges:
            if 'outgoing_webhooks' not in bridge:
                # No outgoing webhooks in this bridge.
                continue

            outgoing_webhooks = bridge['outgoing_webhooks']
            xmpp_endpoints = bridge['xmpp_endpoints']

            # Check whether all normal messages to this bridge should be
            # relayed.
            relay_all_normal = False
            for xmpp_endpoint in xmpp_endpoints:
                if ('relay_all_normal' in xmpp_endpoint and
                        xmpp_endpoint['relay_all_normal'] is True):
                    relay_all_normal = True
                    break

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
                    session = aiohttp.ClientSession(loop=self.loop, connector=conn)
                else:
                    session = aiohttp.ClientSession(loop=self.loop)
                # TODO: Handle ConnectionRefusedError.
                outgoing_webhook['session'] = session

                if relay_all_normal:
                    self.outgoing_mappings['all_normal'].append(
                                                outgoing_webhook)

                for xmpp_endpoint in xmpp_endpoints:
                    # Determine whether the JID corresponds to a MUC or a
                    # normal chat:
                    if 'muc' in xmpp_endpoint:
                        if xmpp_endpoint['muc'] not in self.mucs:
                            raise InvalidConfigError(
                                "Error in config file: XMPP MUC '{}' was not "
                                "defined in the xmpp.mucs section.".format(
                                    xmpp_endpoint['muc']))

                        self.outgoing_mappings[xmpp_endpoint['muc']].append(
                                                            outgoing_webhook)
                    elif 'normal' in xmpp_endpoint:
                        if relay_all_normal:
                            # Don't add normal JIDs when all normal messages
                            # are relayed anyways.
                            continue
                        self.outgoing_mappings[xmpp_endpoint['normal']].append(
                                                            outgoing_webhook)

    def get_incoming_mappings(self, cfg):
        """Reads the incoming webhook definitions from the config file."""
        bridges = cfg['bridges']
        for bridge in bridges:
            if 'incoming_webhooks' not in bridge:
                # No incoming webhooks in this bridge.
                continue

            incoming_webhooks = bridge['incoming_webhooks']
            xmpp_endpoints = bridge['xmpp_endpoints']
            for incoming_webhook in incoming_webhooks:
                if 'token' not in incoming_webhook:
                    raise InvalidConfigError("Invalid config file: "
                                             "'token' missing from outgoing "
                                             "webhook definition.")
                token = incoming_webhook['token']
                for xmpp_endpoint in xmpp_endpoints:
                    if 'muc' in xmpp_endpoint:
                        self.incoming_muc_mappings[token].add(
                                                xmpp_endpoint['muc'])
                    elif 'normal' in xmpp_endpoint:
                        self.incoming_normal_mappings[token].add(
                                                xmpp_endpoint['normal'])

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
        for outgoing_mapping in self.outgoing_mappings.values():
            for webhook in outgoing_mapping:
                webhook['session'].close()
        logging.info("Closed HTTP client sessions..")
        logging.info("Disconnecting from XMPP...")
        self.xmpp_client.disconnect()
        logging.info("Disconnected from XMPP.")


class InvalidConfigError(Exception):
    """Raised when the config file is invalid."""
    pass
