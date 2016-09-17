"""
xmppwb.core
~~~~~~~~~~~

This module is mainly used as an entrypoint to set everything up.

:copyright: (c) 2016 by saqura.
:license: MIT, see LICENSE for more details.
"""
import argparse
import asyncio
import logging
import os
import sys
import yaml

from xmppwb.bridge import XMPPWebhookBridge, InvalidConfigError
from xmppwb import __version__


def main():
    """Main entry point.

    Gathers the command line arguments, reads the config and starts the bridge.
    """
    parser = argparse.ArgumentParser(
        description="A bot that bridges XMPP (chats and MUCs) with webhooks, "
        "thus making it possible to interact with services outside the XMPP "
        "world.")
    parser.add_argument("-c", "--config", help="set the config file",
                        required=True)
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument("-l", "--logfile", help="enable logging to a file")
    parser.add_argument("-d", "--debug", help="include debug output",
                        action="store_true")
    parser.add_argument("--version", help="show version and exit",
                        action="version", version=__version__)
    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    log_config = {
        'format': '%(asctime)s %(levelname)-8s %(message)s',
        'datefmt': '%d-%H:%M:%S'
    }

    if args.debug:
        loop.set_debug(True)
        args.verbose = True

    if args.verbose:
        log_config['level'] = logging.DEBUG
    else:
        log_config['level'] = logging.INFO

    if args.logfile:
        log_config['filename'] = args.logfile


    logging.getLogger('slixmpp').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    # logger = logging.getLogger('xmppwb')
    logging.basicConfig(**log_config)

    logging.info("Starting xmppwb version {}".format(__version__))
    config_filepath = os.path.abspath(args.config)
    logging.info("Using config file {}".format(config_filepath))
    try:
        with open(config_filepath, 'r') as config_file:
            cfg = yaml.load(config_file)
    except FileNotFoundError:
        logging.error("Config file not found. Exiting...")
        sys.exit(1)
    except yaml.scanner.ScannerError as e:
        logging.error("Error while loading config file. "
                      + "This can be caused by tabs in the config file! "
                      + "Remember to remove all tabs and uses spaces instead. "
                      + "Exiting...")
        logging.debug(e)
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
