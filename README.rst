=============================
xmppwb - XMPP Webhook Bridge
=============================
*Note that xmppwb is currently in early development and may contain bugs.*

A bot that bridges XMPP (chats and MUCs) with webhooks, thus making it possible to interact with services outside the XMPP world. This can be used to connect XMPP to other chat services that provide a webhook API (for example Rocket.Chat, Mattermost or Slack).

Install
-------
It is recommended to install ``xmppwb`` into a virtualenv. It requires *Python 3.4+* and can be installed using pip3::

  pip3 install xmppwb

which will automatically install the dependencies (*aiohttp*, *pyyaml* and *slixmpp*).

Configuration
-------------
A documented example config is provided in ``example.conf``. A simple config file looks like this::

    xmpp:
      jid: alice@example.com
      password: "<bot-password>"
      # Define all MUCs that should be available to the bridges defined later.
      mucs:
        - jid: conference1@conference.example.com
          nickname: WebhookBridge
          password: "<muc-password>"
    incoming_webhook_listener:
      bind_address: "127.0.0.1"
      port: 5000
    bridges:
      - xmpp:
          - muc: conference1@conference.example.com
          - relay_all_normal: true
        webhooks:
          outgoing:
            - url: http://127.0.0.1:8065/hooks/<yourtoken>
              override_username: "{nick}"
          incoming:
            - token: <your-token2>

**Note that the password is stored in cleartext, so take precautions such as restricting file permissions. It is recommended to use a dedicated JID for this bridge.**

The terminology ``incoming`` and ``outgoing`` in the config file refers to webhooks from the perspective of this bridge. The webhooks must also be defined on the other end (Rocket.Chat and Mattermost provide a UI for this, for example). An *outgoing webhook in Rocket.Chat* must be set up in the *incoming webhooks section in this bridge* and vice versa.

Usage
-----
*This bridge is meant to run on the same server as the application you are bridging with, as it currently uses HTTP for incoming webhooks.*

To run the bridge::

    xmppwb --config configfile.conf

or::

    python3 -m xmppwb --config configfile.conf
