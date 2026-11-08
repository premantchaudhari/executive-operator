"""Browser destination checks; enforce again at the isolated browser egress proxy."""
import ipaddress
from urllib.parse import urlsplit


def check_destination(url,allowed_hosts):
    if not isinstance(url,str) or len(url)>8192 or any(c.isspace() or ord(c)<32 for c in url):
        raise ValueError('Invalid browser URL')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Browser destination must be HTTPS without credentials')
    host=parsed.hostname.lower()
    if host.endswith('.') or '%' in host:raise ValueError('Ambiguous destination hostname')
    if not isinstance(allowed_hosts,list) or host not in allowed_hosts:
        raise ValueError('Destination is not on the reviewed hostname allowlist')
    try:address=ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or host.endswith(('.localhost','.local','.internal')):
            raise ValueError('Local destination blocked')
    else:
        if not address.is_global:raise ValueError('Non-public destination blocked')
    return host


def check_resolved_addresses(addresses):
    """Called on actual connection addresses, never only on a prior DNS lookup."""
    if not addresses:raise ValueError('No resolved destination')
    for value in addresses:
        if not ipaddress.ip_address(value).is_global:
            raise ValueError('Non-public resolved destination blocked')
