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
    # Direct ALB append mode: only the rightmost value was added by the ALB.
    # A private caller address must not make earlier caller-supplied values trusted.
    try:
        return str(ipaddress.ip_address(forwarded[-1].strip()))
    except ValueError:
        return str(address)
