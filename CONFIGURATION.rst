*********************
Configuration Options
*********************

The following is a detailed overview of all available options. The documentation
of each section begins with a simple example. Refer to the example config files
to see how these can be combined. The config file is in YAML format, which means
that tabs are not allowed.

=============
Section: xmpp
=============

.. code-block:: yaml

    xmpp:
      jid: <alice@example.com>
      password: "<bot-password>"
      mucs:
        - jid: <conference1@conference.example.com>
          nickname: <nickname>
          password: "<muc-password>"
        - jid: <conference2@conference.example.com>
          nickname: <nickname2>

+----------------------+--------------------------------------------------------+
| Name                 | Description                                            |
+======================+========================================================+
| **jid**              | The Jabber-ID the bot uses (must exist).               |
+----------------------+--------------------------------------------------------+
| **password**         | The corresponding password.                            |
+----------------------+--------------------------------------------------------+
| **mucs**             | A **list** of all MUCs that should be available to the |
|                      | bridges defined later. This section can be ommitted if |
|                      | no MUCs are used in any of the bridges.                |
+----------------------+--------------------------------------------------------+
| **host**             | **Optional:** The hostname of the XMPP server. This is |
|                      | only needed if the DNS entries of the XMPP server are  |
|                      | not set correctly.                                     |
|                      |                                                        |
|                      | If specified, the port must also be set.               |
+----------------------+--------------------------------------------------------+
| **port**             | **Optional:** The port of the XMPP server. If          |
|                      | specified, the hostname must also be set (see above).  |
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
|                      | password.                                              |
+----------------------+--------------------------------------------------------+

==================================
Section: incoming_webhook_listener
==================================

.. code-block:: yaml

    incoming_webhook_listener:
      bind_address: "127.0.0.1"
      port: 5000

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

================
Section: bridges
================

.. code-block:: yaml

    bridges:
      - xmpp_endpoints:
          - muc: <conference1@conference.example.com>
        outgoing_webhooks:
          - url: <incoming-webhook-url-from-other-end>
            override_username: "{nick}"
        incoming_webhooks:
          - token: <outgoing-webhook-token-from-other-end>

This section is a **list** of all available bridges. There can be one or
multiple bridges. Each bridge consists of an **xmpp_endpoints** section, an
**outgoing_webhooks** section and an **incoming_webhooks** section.

--------------------------------------
The xmpp_endpoints section of a bridge
--------------------------------------

This is a **list** of all XMPP endpoints that should be part of this bridge.
All incoming messages to this bridge are relayed to each of these JIDs, and all
messages from these JIDs are relayed as per the outgoing webhooks of this
bridge.

Each entry in ``xmpp_endpoints`` is **one of the following**:

+-----------------------+-------------------------------------------------------+
| Name                  | Description                                           |
+=======================+=======================================================+
| **muc: <JID>**        | This is used if a MUC should be part of this bridge.  |
|                       | The MUC must have been defined in the ``xmpp.mucs``   |
|                       | section above.                                        |
+-----------------------+-------------------------------------------------------+
| **normal: <JID>**     | This is used if a normal JID should be part of this   |
|                       | bridge.                                               |
+-----------------------+-------------------------------------------------------+
| **relay_all_normal:** | **Optional:** The bridge can also relay *all*         |
| **true**              | messages received from normal JIDs (i.e. JIDs that    |
|                       | are not MUC JIDs). Note that this will only trigger   |
|                       | outgoing webhooks. Incoming webhooks can only affect  |
|                       | MUCs and normal JIDs that are explicitly defined.     |
+-----------------------+-------------------------------------------------------+

-----------------------------------------
The outgoing_webhooks section of a bridge
-----------------------------------------

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
| **cafile: <cafile>**   | **Optional:** The path to the full certificate chain |
|                        | used for validating the other end. This certificate  |
|                        | chain should be in "PEM" format [#]_.                |
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
|                        | - ``{local_jid}``: The local part of the JID whose   |
|                        |   message is relayed.                                |
|                        |                                                      |
|                        |   Example: If the JID is ``bob@example.com`` the     |
|                        |   local part would be ``bob``.                       |
|                        |                                                      |
|                        | - ``{nick}``: When relaying from a normal chat this  |
|                        |   this is the local part. When relaying from a MUC   |
|                        |   this is the resource part.                         |
|                        |                                                      |
|                        | - ``{jid}``: When relaying from a normal chat this   |
|                        |   is the bare JID. When relaying from a MUC this is  |
|                        |   the full JID.                                      |
+------------------------+------------------------------------------------------+
| **avatar_url:**        | **Optional:** The URL that is sent in the            |
| **<string>**           | ``icon_url`` field in the outgoing webhook to set an |
|                        | avatar. It may contain the same placeholders as      |
|                        | ``override_username`` (see above).                   |
|                        |                                                      |
|                        | For Rocket.Chat, it can be set to the value          |
|                        | ``https://ROCKETCHATURL/avatar/{nick}.jpg`` where    |
|                        | ROCKETCHATURL needs to be replaced with the URL of   |
|                        | the Rocket.Chat instance.                            |
|                        |                                                      |
|                        | **WARNING:** As XMPP nicknames can be freely chosen, |
|                        | setting this option may enable impersonating other   |
|                        | people by having their avatar displayed. It is       |
|                        | therefore only recommended to use this option in     |
|                        | private setups where you trust all involved users.   |
+------------------------+------------------------------------------------------+
| **message_template:**  | **Optional:** The message that is sent as part of    |
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
| **attachment_link:**   | **Optional:** When using *attachment formatting*,    |
| **<string>**           | each message can include a link.                     |
+------------------------+------------------------------------------------------+

.. [#] See: https://docs.python.org/3/library/ssl.html#ca-certificates

-----------------------------------------
The incoming_webhooks section of a bridge
-----------------------------------------

A **list** of all incoming webhooks that should be handled in this bridge. This
section is **optional** and only needed if incoming webhooks should be
triggered. For the typical use case of relaying messages bidirectionally this
is needed.

``incoming_webhook_listener`` **needs to be defined when using incoming**
**webhooks.**

*Note: "Incoming to this bridge" means "Outgoing from the other end"*.

Each entry in ``incoming_webhooks`` has the following item:

+----------------------+--------------------------------------------------------+
| Name                 | Description                                            |
+======================+========================================================+
| **token: <string>**  | Only incoming webhooks that have a matching token will |
|                      | be considered part of this bridge.                     |
+----------------------+--------------------------------------------------------+
| **ignore_user**      | **Optional:** A **list** of users whose messages will  |
|                      | be ignored.                                            |
|                      |                                                        |
|                      | The motivation for this option is to prevent outgoing  |
|                      | messages to chat systems like Rocket.Chat from being   |
|                      | relayed back into the bridge, which would result in    |
|                      | duplicate messages. Usually, the name of the bot that  |
|                      | posts incoming messages to the chat system is listed   |
|                      | here.                                                  |
+----------------------+--------------------------------------------------------+
