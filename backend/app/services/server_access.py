"""Authenticated frontend-to-backend page request logging."""
import hashlib
import hmac
import os

from fastapi import HTTPException

ADMIN_ROOTS = {'data-sources', 'data-source-types', 'categories', 'faqs', 'faq-classifications', 'chat-history', 'usage'}


def page_surface(path: str) -> str | None:
    if path == '/chat' or path.startswith('/chat/'):
        return 'CHAT'
    root = path.split('/')[1] if path.startswith('/') else ''
    if path == '/' or root in ADMIN_ROOTS:
        return 'ADMIN'
    return None


async def verify_page_request(request, cookie: str | None) -> str:
    secret = os.getenv('ACCESS_LOG_SIGNING_SECRET', '')
    path = request.headers.get('x-access-page', '')
    supplied = request.headers.get('x-access-signature', '')
    surface = page_surface(path)
    if not secret or not cookie or not surface or len(supplied) != 64:
        raise HTTPException(status_code=403, detail='アクセス記録の送信元を確認できません。')
    body = await request.body()
    message = b'v1\n' + cookie.encode() + b'\n' + path.encode() + b'\n' + body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail='アクセス記録の送信元を確認できません。')
    return surface
