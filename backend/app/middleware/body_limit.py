"""Bound request bodies before FastAPI parses them or resolves dependencies."""
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

MIB = 1024 * 1024
DEFAULT_BODY_LIMIT = 10 * MIB
IMPORT_BODY_LIMIT = 11 * MIB  # Existing 10 MiB workbook limit plus multipart headers.
UPLOAD_BODY_LIMIT = 501 * MIB  # Existing 500 MiB total file limit plus form fields.


def body_limit(path: str, method: str) -> int:
    path = path.rstrip('/')
    if method == 'POST' and path == '/api/v1/data-sources/files':
        return UPLOAD_BODY_LIMIT
    if method == 'POST' and path in {
        '/api/v1/faqs/import', '/api/v1/data-sources/import',
        '/api/v1/data-sources/websites/import',
    }:
        return IMPORT_BODY_LIMIT
    return DEFAULT_BODY_LIMIT


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        limit = body_limit(scope['path'], scope['method'])
        response = JSONResponse(status_code=413, content={'detail': {
            'code': 'REQUEST_BODY_TOO_LARGE',
            'message': '送信データのサイズが上限を超えています。ファイルのサイズや件数を減らして再度お試しください。',
        }})
        lengths = [v for k, v in scope.get('headers', []) if k.lower() == b'content-length']
        for value in lengths:
            try:
                length = int(value)
            except ValueError:
                length = -1
            if length < 0 or len(lengths) > 1:
                return await JSONResponse(status_code=400, content={'detail': 'Invalid Content-Length'})(scope, receive, send)
            if length > limit:
                return await response(scope, receive, send)
        consumed = 0
        exceeded = False
        replaced = False

        async def limited_receive():
            nonlocal consumed, exceeded
            if exceeded:
                raise MultiPartException('Request body too large')
            message = await receive()
            if message['type'] == 'http.request':
                consumed += len(message.get('body', b''))
                if consumed > limit:
                    exceeded = True
                    # Starlette closes spooled temporary files on this exception.
                    raise MultiPartException('Request body too large')
            return message

        async def limited_send(message):
            nonlocal replaced
            if exceeded:
                if not replaced:
                    replaced = True
                    await response(scope, receive, send)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except MultiPartException:
            if not exceeded:
                raise
            if not replaced:
                await response(scope, receive, send)
