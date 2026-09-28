from types import SimpleNamespace
import pytest
from app.services.client_ip import client_ip


def request(peer, forwarded=''):
    return SimpleNamespace(client=SimpleNamespace(host=peer) if peer else None,
                           headers={'x-forwarded-for': forwarded})


@pytest.mark.parametrize('caller', ['10.0.2.3', '203.0.113.4', '2001:db8::123'])
def test_direct_alb_uses_only_appended_caller(monkeypatch, caller):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/16')
    assert client_ip(request('10.0.1.2', f'198.51.100.9, {caller}')) == caller


def test_signed_frontend_forwarded_value_uses_same_rule(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/16')
    req = request('10.0.1.2', '203.0.113.99')
    assert client_ip(req, forwarded_for='198.51.100.9, 10.0.2.3') == '10.0.2.3'


@pytest.mark.parametrize('forwarded', ['', '198.51.100.9, ', '198.51.100.9, invalid'])
def test_invalid_rightmost_falls_back_to_peer(monkeypatch, forwarded):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/16')
    assert client_ip(request('10.0.1.2', forwarded)) == '10.0.1.2'


@pytest.mark.parametrize('networks', ['', '10.0.0.0/16'])
def test_untrusted_peer_cannot_supply_forwarded_ip(monkeypatch, networks):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', networks)
    req = request('203.0.113.4', '198.51.100.9')
    assert client_ip(req) == '203.0.113.4'
    assert client_ip(req, forwarded_for='198.51.100.8') == '203.0.113.4'


@pytest.mark.parametrize('peer', [None, 'invalid'])
def test_missing_or_invalid_peer_cannot_supply_forwarded_ip(monkeypatch, peer):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/16')
    assert client_ip(request(peer, '198.51.100.9')) is None
