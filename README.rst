****************************
xmppwb - XMPP Webhook Bridge
****************************

*Note that xmppwb is currently in early development and may contain bugs.*

A bot that bridges XMPP (chats and MUCs) with webhooks, thus making it possible
to interact with services outside the XMPP world. This can be used to connect
XMPP to other chat services that provide a webhook API (for example
`Rocket.Chat`_ or `Mattermost`_).

.. contents::
   :local:
   :depth: 2
   :backlinks: none

============
Installation
============

``xmppwb`` requires *Python 3.5+* and can be installed using pip3:

.. code-block:: bash

    $ pip3 install --upgrade xmppwb


which will automatically install the dependencies (*aiohttp*, *pyyaml* and
*slixmpp*).


=====
Usage
=====

*This bridge is meant to run on the same server as the application you are
bridging with, as it currently uses HTTP for incoming webhooks.*

To run the bridge:

.. code-block:: bash

    $ xmppwb --config configfile.conf


or:

.. code-block:: bash

    $ python3 -m xmppwb --config configfile.conf

Synopsis:

.. code-block:: bash

    $ xmppwb [-h] [-v] --config CONFIG

See also ``xmppwb --help``.

=============
Configuration
=============

A simple config file looks like this (the ``<placeholders>`` need to be
changed):

.. code-block:: yaml

    xmpp:
      # This JID must exist.
      jid: <alice@example.com>
      password: "<bot-password>"
      # Define all MUCs that should be available to the bridges defined later.
      mucs:
        - jid: <conference1@conference.example.com>
          nickname: <nickname>
          # password: "<muc-password>"
    incoming_webhook_listener:
      bind_address: "127.0.0.1"
      port: 5000
    bridges:
      - xmpp_endpoints:
          - muc: <conference1@conference.example.com>
          - relay_all_normal: true
        outgoing_webhooks:
          - url: <incoming-webhook-url-from-other-end>
            override_username: "{nick}"
        incoming_webhooks:
          - token: <outgoing-webhook-token-from-other-end>


**Note that the password is stored in cleartext, so take precautions such as
restricting file permissions. It is recommended to use a dedicated JID for
this bridge.**

The terminology ``incoming`` and ``outgoing`` in the config file refers to
webhooks from the perspective of this bridge. The webhooks must also be defined
on the other end (Rocket.Chat and Mattermost provide a UI for this, for
example). An *outgoing webhook in Rocket.Chat* must be set up in the
*incoming webhooks section in this bridge* and vice versa.

----------------------------
Integrating with Rocket.Chat
----------------------------

An example config for bridging XMPP with `Rocket.Chat`_ is provided in
``rocketchat.example.conf``. It is recommended to copy it and fill out
all ``<placeholders>``.

1. To create the corresponding webhooks in RocketChat, go to
   *Administration->Integrations* and create a new incoming webhook.
   Here you can select the channel that you want to bridge with.
2. After saving, a webhook URL will be generated. Copy it and fill it into
   the ``<incoming-webhook-url-from-rocketchat>`` placeholder in the config
   file.
3. Now create an outgoing webhook. The URL is of the form
   ``http://{bind_adress}:{port}/`` and depends on your settings in the
   ``incoming_webhook_listener`` section. It defaults to
   ``http://127.0.0.1:5000/``.
4. Copy the token and fill it into the
   ``<outgoing-webhook-token-from-rocketchat>`` placeholder.
5. After having filled out all other placeholders, the bridge is ready to run
   (see `usage`_).


=====================
Configuration Options
=====================

The following is a detailed overview of all available options. Refer to the
example config files to see how these can be combined.

-------------
Section: xmpp
-------------
+----------------------+--------------------------------------------------------+
| Name                 | Description                                            |
+======================+========================================================+
| **jid**              | The Jabber-ID the bot uses (must exist).               |
+----------------------+--------------------------------------------------------+
| **password**         | The corresponding password.                            |
+----------------------+--------------------------------------------------------+
| **mucs**             | A **list** of all MUCs that should be available to the |
|                      | bridges defined later.                                 |
+----------------------+--------------------------------------------------------+

Each entry in ``mucs`` has the following items:

+----------------------+--------------------------------------------------------+
| Name                 | Description                                            |
+======================+========================================================+
| **jid**              | The Jabber-ID of the MUC (must exist).                 |
+----------------------+--------------------------------------------------------+
| **nickname**         | The nickname the bot should use in the MUC.            |
+----------------------+--------------------------------------------------------+
| **password**         | **Optional:** Only needed if the MUC requires a        |
|                      | password                                               |
+----------------------+--------------------------------------------------------+

-----------------------------------
Section: incoming_webhook_listeners
-----------------------------------

The bridge can create a server to listen for incoming webhooks (HTTP POST
requests). This section is **optional** and only needed if the bridge should
handle incoming webhooks. For the typical use case of relaying messages
bidirectionally this is needed.

+----------------------+--------------------------------------------------------+
| Name                 | Description                                            |
+======================+========================================================+
| **bind_address**     | The address the server should bind to. If the bridge   |
|                      | should only listen locally, use ``127.0.0.1``. If it   |
|                      | should bind to all available addresses, use            |
|                      | ``0.0.0.0``.                                           |
+----------------------+--------------------------------------------------------+
| **port**             | The port the server should listen to.                  |
+----------------------+--------------------------------------------------------+

----------------
Section: bridges
----------------

This section is a **list** of all available bridges. There can be one or
multiple bridges. Each bridge consists of an **xmpp_endpoints section**, an
**outgoing_webhooks section** and an **incoming_webhooks section**.

**The xmpp_endpoints section of a bridge:**
This is a **list** of all XMPP endpoints that should be part of this bridge.
All incoming messages of this bridge are relayed to each of these JIDs, and all
messages from these JIDs are relayed as per the outgoing webhooks of this
bridge.

Each entry in ``xmpp_endpoints`` is one of the following:

+----------------------+--------------------------------------------------------+
| Name                 | Description                                            |
+======================+========================================================+
| **muc: <JID>**       | This is used if a MUC should be part of this bridge.   |
|                      | The MUC must have been defined in the ``xmpp.mucs``    |
|                      | section above.                                         |
+----------------------+--------------------------------------------------------+
| **normal: <JID>**    | This is used if a normal JID should be part of this    |
|                      | bridge.                                                |
+----------------------+--------------------------------------------------------+
| **relay_all_**       | **Optional:** The bridge can also relay all messages   |
| **normal: true**     | received from normal JIDs. Note that this will only    |
|                      | trigger outgoing webhooks. Incoming webhooks can only  |
|                      | affect MUCs and normal JIDs that are explicitly        |
|                      | defined.                                               |
+----------------------+--------------------------------------------------------+

**The outgoing_webhooks section of a bridge**

A **list** of all outgoing webhooks that should be triggered when receiving XMPP
messages. This section is **optional** and only needed if outgoing webhooks
should be triggered. For the typical use case of relaying messages
bidirectionally this is needed.


*Note: "Outgoing from this bridge" means "Incoming to the other end"*.

Each entry in ``outgoing_webhooks`` has the following items:

+------------------------+------------------------------------------------------+
| Name                   | Description                                          |
+========================+======================================================+
| **url: <url>**         | The URL of the webhook that should be triggered.     |
+------------------------+------------------------------------------------------+
| **override_username:** | **Optional:** The username that is sent as part of   |
| **<string>**           | the outgoing webhook can be overridden with this     |
|                        | string. It may contain the following placeholders:   |
|                        |                                                      |
|                        | - ``{bare_jid}``: The bare JID whose message is      |
|                        |   relayed.                                           |
|                        |                                                      |
|                        |   Example: ``bob@example.com``                       |
|                        |                                                      |
|                        | - ``{full_jid}``: The full JID whose message is      |
|                        |   relayed.                                           |
|                        |                                                      |
|                        |   Example: ``bob@example.com/Resource``              |
|                        |                                                      |
|                        | - ``local_jid``: The local part of the JID whose     |
|                        |   message is relayed.                                |
|                        |                                                      |
|                        |   Example: If the JID is ``bob@example.com`` the     |
|                        |            local part would be ``bob``.              |
|                        |                                                      |
|                        | - ``{nick}``: When relaying from a normal chat this  |
|                        |   this is the local part. When relaying from a MUC   |
|                        |   this is the resource part.                         |
|                        |                                                      |
|                        | - ``{jid}``: When relaying from a normal chat this   |
|                        |   is the bare JID. When relaying from a MUC this is  |
|                        |   the full JID.                                      |
+------------------------+------------------------------------------------------+
| **message_template**   | **Optional:** The message that is sent as part of    |
| **<string>**           | the outgoing webhook can be overwritten. The         |
|                        | folowing placeholders may be used:                   |
|                        |                                                      |
|                        | - ``{msg}``: The original message as received from   |
|                        |   XMPP.                                              |
+------------------------+------------------------------------------------------+  
| **use_attachment_**    | **Optional:** The message can be sent using          |
| **formatting: true**   | *attachment formatting*. This is the preferred way   |
|                        | of integrating with RocketChat.                      |
+------------------------+------------------------------------------------------+

**The incoming_webhooks section of a bridge**

A **list** of all incoming webhooks that should be handled in this bridge. This
section is **optional** and only needed if incoming webhooks should be
triggered. For the typical use case of relaying messages bidirectionally this
is needed. ``incoming_webhook_listener`` **needs to be defined when using**
**incoming webhooks.**

*Note: "Incoming to this bridge" means "Outgoing from the other end"*.

Each entry in ``incoming_webhooks`` has the following item:
+----------------------+--------------------------------------------------------+
| Name                 | Description                                            |
+======================+========================================================+
| **token: <string>**  | Only incoming webhooks that have a matching token will |
|                      | be considered part of this bridge.                     |
+----------------------+--------------------------------------------------------+


.. _Rocket.Chat: https://rocket.chat/
.. _Mattermost: https://about.mattermost.com
