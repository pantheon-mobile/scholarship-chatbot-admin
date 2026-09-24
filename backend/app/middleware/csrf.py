"""Reject cross-origin writes using the session cookie (CORS is not CSRF protection)."""
import os
from starlette.datastructures import Headers
from starlette.responses import JSONResponse


class CsrfMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope['method'] in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            headers = Headers(scope=scope)
            origin = headers.get('origin')
            allowed = {s.strip().rstrip('/') for s in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if s.strip()}
            cookie_authenticated = 'scholarship_session=' in headers.get('cookie', '')
            if (origin is not None and origin not in allowed) or (cookie_authenticated and origin is None):
                return await JSONResponse(status_code=403, content={'detail': '送信元を確認できません。画面を再読み込みして再度お試しください。'})(scope, receive, send)
        return await self.app(scope, receive, send)
