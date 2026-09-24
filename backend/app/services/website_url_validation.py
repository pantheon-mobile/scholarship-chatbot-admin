import ipaddress
from urllib.parse import urlsplit


MAX_WEBSITE_URL_LENGTH = 500


class WebsiteUrlValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_website_url(value: str) -> str:
    url = value.strip()
    if not url:
        raise WebsiteUrlValidationError("URL_REQUIRED", "URLを入力してください。")
    if len(url) > MAX_WEBSITE_URL_LENGTH or any(character.isspace() for character in url):
        raise WebsiteUrlValidationError("INVALID_URL", "正しいURLを入力してください。")
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc) and bool(parsed.hostname)
        parsed.port
    except ValueError:
        valid = False
    if valid:
        valid = not parsed.username and not parsed.password
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            valid = valid and parsed.hostname.lower().rstrip('.') != 'localhost' and not parsed.hostname.lower().rstrip('.').endswith('.localhost')
        else:
            valid = valid and address.is_global and not address.is_multicast and not address.is_reserved
    if not valid:
        raise WebsiteUrlValidationError("INVALID_URL", "正しいURLを入力してください。")
    return url
