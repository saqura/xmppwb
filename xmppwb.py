#!/usr/bin/env python3
"""
xmppwb - XMPP Webhook Bridge
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A bot that bridges XMPP (chats and MUCs) with webhooks, thus making it
possible to interact with services outside the XMPP world. This can be used to
connect XMPP to other chat services that provide a webhook API to XMPP (for
example Rocket.Chat, Mattermost or Slack).

:copyright: (c) 2016 by saqura.
:license: MIT, see LICENSE for more details.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
import aiohttp
import aiohttp.web
import yaml
from slixmpp import ClientXMPP


class XMPPWebhookBridge():
    """This is the central component: It initializes and connects the
    :class:`XMPPBridgeBot` with the webhook handling part. The webhook part
    consists of an HTTP server listening for incoming webhooks (POST requests),
    and an HTTP client part for sending outgoing webhooks (POST requests).
    """
    def __init__(self, cfg, loop):
        self.loop = loop
        self.incoming_normal_mappings = defaultdict(set)
        self.incoming_muc_mappings = defaultdict(set)
        # TODO: Refactor to use frozendict+sets instead of lists.
        self.outgoing_mappings = defaultdict(list)
        # Mapping of MUC-JID -> Nickname
        self.mucs = dict()
        # Mapping of MUC-JID -> Password
        self.muc_passwords = dict()

        try:
            # Get the MUCs from the config:
            self.get_mucs(cfg)
            # Get the outgoing bridge mappings from the config:
            self.get_outgoing_mappings(cfg)
            # Get the incoming bridge mappings from the config:
            self.get_incoming_mappings(cfg)
        except KeyError:
            raise InvalidConfigError

        # Initialize HTTP client
        # TODO: Handle ConnectionRefusedError.
        self.http_client = aiohttp.ClientSession(loop=loop)

        # Initialize XMPP client
        self.xmpp_client = XMPPBridgeBot(cfg['xmpp']['jid'],
                                         cfg['xmpp']['password'],
                                         self)
        self.xmpp_client.connect()

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
            logging.info("Listening for incoming webhooks on {}:{}".format(
                                                    bind_address, port))
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
        logging.debug("Handling outgoing webhook. (from {})".format(from_jid))

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
            "text": message,
            "username": username
        }

        if 'override_channel' in outgoing_webhook:
            payload['channel'] = outgoing_webhook['override_channel']

        # Attachment formatting is useful for integrating with Rocket.Chat.
        if ('use_attachment_formatting' in outgoing_webhook and
                outgoing_webhook['use_attachment_formatting']):
            payload = {
                "attachments": [{
                    "title": "From: {}".format(username),
                    # TODO: Add an option to change the link.
                    # "title_link": "https://xmpp.org",
                    "text": message
                }]
            }

        logging.debug("Sending outgoing webhook. (from {})".format(from_jid))
        request = await self.http_client.post(
            outgoing_webhook['url'],
            data=json.dumps(payload),
            headers={'content-type': 'application/json'})
        await request.release()
        return

    async def handle_incoming(self, request):
        """This coroutine handles incoming webhooks: It receives incoming
        webhooks and relays the messages to XMPP."""
        if request.content_type == "application/json":
            payload = await request.json()
        else:
            # TODO: Handle other content types
            payload = await request.post()
        token = payload['token']
        logging.debug("Handling incoming request from token {}".format(token))
        msg = payload['user_name'] + ": " + payload['text']
        for xmpp_normal_jid in self.incoming_normal_mappings[token]:
            logging.debug("Sending a normal chat message to XMPP.")
            self.xmpp_client.send_message(mto=xmpp_normal_jid,
                                          mbody=msg,
                                          mtype="chat",
                                          mnick=payload['user_name'])
        for xmpp_muc_jid in self.incoming_muc_mappings[token]:
            logging.debug("Sending a MUC chat message to XMPP.")
            self.xmpp_client.send_message(mto=xmpp_muc_jid,
                                          mbody=msg,
                                          mtype="groupchat",
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
        """Reads the outgoing webhook definitions from the config file."""
        bridges = cfg['bridges']
        for bridge in bridges:
            if 'outgoing' not in bridge['webhooks']:
                # No outgoing webhooks in this bridge.
                continue

            outgoing_webhooks = bridge['webhooks']['outgoing']
            xmpp_endpoints = bridge['xmpp']

            # Check whether all normal messages to this bot should be relayed.
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

                if relay_all_normal:
                    self.outgoing_mappings['all_normal'].append(
                                                outgoing_webhook)

                for xmpp_endpoint in xmpp_endpoints:
                    if 'relay_all_normal' in xmpp_endpoint:
                        # This case was already handled above.
                        continue

                    # Determine whether the JID corresponds to a MUC or a
                    # normal chat:
                    elif 'muc' in xmpp_endpoint:
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
            if 'incoming' not in bridge['webhooks']:
                # No incoming webhooks in this bridge.
                continue

            incoming_webhooks = bridge['webhooks']['incoming']
            xmpp_endpoints = bridge['xmpp']
            for incoming_webhook in incoming_webhooks:
                if 'token' not in incoming_webhook:
                    raise InvalidConfigError("Invalid config file: "
                                             "'url' missing from outgoing "
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

        logging.info("Closing HTTP client session...")
        self.http_client.close()
        logging.info("Closed HTTP client session..")
        logging.info("Disconnecting from XMPP...")
        self.xmpp_client.disconnect()
        logging.info("Disconnected from XMPP.")


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
            if muc in self.main_bridge.muc_passwords:
                self.plugin['xep_0045'].joinMUC(
                    muc,
                    nickname,
                    wait=True,
                    password=self.main_bridge.muc_passwords[muc])
            else:
                self.plugin['xep_0045'].joinMUC(muc,
                                                nickname,
                                                wait=True)

        logging.info("Connected to XMPP.")

    async def message_received(self, msg):
        """This coroutine is triggered whenever a message (both normal or from
        a MUC) is received. It relays the message to the bridge.
        """
        from_jid = msg['from']
        logging.debug("Received message from XMPP. (from {})".format(from_jid))
        if msg['type'] in ('chat', 'normal'):
            out_webhooks = self.main_bridge.outgoing_mappings['all_normal']
            for outgoing_webhook in out_webhooks:
                await self.main_bridge.handle_outgoing(outgoing_webhook, msg)

        elif msg['type'] == 'groupchat':
            # TODO: Handle nickname of private message in MUCs.
            if from_jid.resource == self.main_bridge.mucs[from_jid.bare]:
                # Don't relay messages from ourselves.
                return

        else:
            # Only handle normal chats and MUCs.
            return

        out_webhooks = self.main_bridge.outgoing_mappings[from_jid.bare]
        for outgoing_webhook in out_webhooks:
            await self.main_bridge.handle_outgoing(outgoing_webhook, msg)

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


class InvalidConfigError(Exception):
    """Raised when the config file is invalid."""
    pass


def main():
    """Main entry point.

    Gathers the command line arguments, reads the config and starts the bridge.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("--config", help="set the config file",
                        default="xmppwb.conf")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    if args.verbose:
        loglevel = logging.DEBUG
        loop.set_debug(True)
    else:
        loglevel = logging.INFO
    logging.basicConfig(level=loglevel,
                        format='%(levelname)-8s %(message)s')

    config_filepath = os.path.abspath(args.config)
    logging.info("Using config file {}".format(config_filepath))
    try:
        with open(config_filepath, 'r') as config_file:
            cfg = yaml.load(config_file)
    except FileNotFoundError:
        logging.exception("Config file not found.")
        sys.exit(1)

    try:
        bridge = XMPPWebhookBridge(cfg, loop)
    except InvalidConfigError:
        logging.exception("Invalid config file.")
        sys.exit(1)

    try:
        bridge.process()
    except KeyboardInterrupt:
        print("Exiting... (keyboard interrupt)")
    finally:
        bridge.close()
    loop.close()
    logging.info("xmppwb exited.")


if __name__ == '__main__':
    main()
