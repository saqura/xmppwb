from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the version
with open(path.join(here, 'xmppwb', 'version.py')) as f:
    vf = {}
    exec(f.read(), vf)
    version = vf['__version__']

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='xmppwb',
    version=version,
    description='XMPP Webhook Bridge',
    long_description=long_description,
    url='https://github.com/saqura/xmppwb',
    author='saqura',
    author_email='saqura@saqura.xyz',
    license='MIT',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: Communications :: Chat',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
    ],
    keywords=['jabber', 'xmpp', 'bridge', 'bot', 'webhook', 'webhooks'],
    packages=find_packages(),
    install_requires=['aiohttp', 'pyyaml', 'slixmpp'],
    entry_points={
        'console_scripts': [
            'xmppwb=xmppwb.core:main',
        ],
    },
)
