"""Crawler-only transport: validate and pin every TCP connection to a public IP."""
import ipaddress
import socket

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError
from urllib3.util.connection import create_connection


def is_public_address(value):
    address = ipaddress.ip_address(value)
    return address.is_global and not address.is_multicast and not address.is_reserved


def public_addresses(host, port):
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    if not addresses or any(not is_public_address(address) for address in addresses):
        raise ValueError('内部ネットワーク宛てのURLは取得できません。')
    return addresses


class PublicConnectionMixin:
    def _new_conn(self):
        try:
            addresses = public_addresses(self.host, self.port)
            # Use the checked numeric IP for the socket; retain the original host
            # on the HTTPS connection for SNI and certificate hostname verification.
            return create_connection((addresses[0], self.port), self.timeout,
                                     source_address=self.source_address, socket_options=self.socket_options)
        except (OSError, ValueError) as error:
            raise NewConnectionError(self, '公開Webサイトへの接続に失敗しました。') from error


class PublicHTTPConnection(PublicConnectionMixin, HTTPConnection):
    pass


class PublicHTTPSConnection(PublicConnectionMixin, HTTPSConnection):
    pass


class PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = PublicHTTPConnection


class PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = PublicHTTPSConnection


class PublicHTTPAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {'http': PublicHTTPPool, 'https': PublicHTTPSPool}


def public_session():
    session = requests.Session()
    session.trust_env = False
    session.mount('http://', PublicHTTPAdapter())
    session.mount('https://', PublicHTTPAdapter())
    return session
