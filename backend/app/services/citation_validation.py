"""Only navigable web URLs and our source-download path are valid citations."""
import re
from urllib.parse import urlsplit


def safe_citation_uri(value: str | None) -> str | None:
    if not value or any(ord(c) < 33 for c in value) or '\\' in value:
        return None
    if re.fullmatch(r'/api/v1/chat/sources/[1-9][0-9]*/download', value):
        return value
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {'http', 'https'} and parsed.hostname and not parsed.username and not parsed.password:
            parsed.port
            return value
    except ValueError:
        pass
    return None
