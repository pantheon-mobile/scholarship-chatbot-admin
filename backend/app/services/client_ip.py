"""Resolve forwarded IPs only through explicitly trusted proxy networks."""
import ipaddress
import os


def client_ip(request, *, forwarded_for=None):
    peer = request.client.host if request.client else ''
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return None
    trusted = [ipaddress.ip_network(value.strip()) for value in os.getenv('TRUSTED_PROXY_CIDRS', '').split(',') if value.strip()]
    if not any(address in network for network in trusted):
        return str(address)
    forwarded = (forwarded_for if forwarded_for is not None else request.headers.get('x-forwarded-for', '')).split(',')
    # Walk from the nearest proxy towards the caller; never trust the leftmost
    # self-declared address after the first untrusted hop.
    for value in reversed(forwarded):
        if not any(address in network for network in trusted):
            break
        try:
            address = ipaddress.ip_address(value.strip())
        except ValueError:
            return str(ipaddress.ip_address(peer))
    return str(address)
