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

**Note: Python 3.5 is required. It will not work with Python 3.4 as xmppwb uses specific syntax that was introduced with Python 3.5.**

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

    $ xmppwb -c CONFIG [-h] [-v] [-l LOGFILE] [-d] [--version]

See also ``xmppwb --help``.

=============
Configuration
=============

Please see `CONFIGURATION.rst <https://github.com/saqura/xmppwb/blob/master/CONFIGURATION.rst>`_
for detailed documentation. A simple config file looks like this (the
``<placeholders>`` need to be changed):

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
        outgoing_webhooks:
          - url: <incoming-webhook-url-from-other-end>
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

============================
Integrating with Rocket.Chat
============================

An example config for bridging XMPP with `Rocket.Chat`_ is provided in
`rocketchat.example.conf <https://github.com/saqura/xmppwb/blob/master/conf/rocketchat.example.conf>`_.
It is recommended to copy it and fill out all ``<placeholders>``.

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


===========================
Integrating with Mattermost
===========================

An example config for bridging XMPP with `Mattermost`_ is provided in
`mattermost.example.conf <https://github.com/saqura/xmppwb/blob/master/conf/mattermost.example.conf>`_.
It is recommended to copy it and fill out all ``<placeholders>``.

1. To create the corresponding webhooks in Mattermost, go to
   *Account Settings->Integrations* and create a new incoming webhook.
   Here you can select the channel that you want to bridge with.
2. After saving, a webhook URL will be generated. Copy it and fill it into
   the ``<incoming-webhook-url-from-mattermost>`` placeholder in the config
   file.
3. Now create an outgoing webhook. The callback URL is of the form
   ``http://{bind_adress}:{port}/`` and depends on your settings in the
   ``incoming_webhook_listener`` section. It defaults to
   ``http://127.0.0.1:5000/``.
4. After saving, copy the token and fill it into the
   ``<outgoing-webhook-token-from-mattermost>`` placeholder.
5. After having filled out all other placeholders, the bridge is ready to run
   (see `usage`_).



.. _Rocket.Chat: https://rocket.chat/
.. _Mattermost: https://about.mattermost.com

=======
License
=======

xmppwb is released under the MIT license. Please read
`LICENSE <https://github.com/saqura/xmppwb/blob/master/LICENSE>`_ for details.
