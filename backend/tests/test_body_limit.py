from io import BytesIO
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.v1.auth import require_authenticated_session
from app.middleware import body_limit as limits
from app.services.file_upload_validation import _validate_content, FileUploadValidationError
from starlette.datastructures import UploadFile


@pytest.mark.anyio
@pytest.mark.parametrize('kind', ['json', 'file', 'field', 'urlencoded'])
@pytest.mark.parametrize('declared', [False, True])
async def test_over_limit_rejected_before_auth_and_before_remaining_body(monkeypatch, kind, declared):
    monkeypatch.setattr(limits, 'DEFAULT_BODY_LIMIT', 128)
    monkeypatch.setattr(limits, 'IMPORT_BODY_LIMIT', 128)
    auth = Mock(side_effect=HTTPException(401))
    app.dependency_overrides[require_authenticated_session] = auth
    consumed = []
    path = '/api/v1/faqs' if kind == 'json' else '/api/v1/faqs/import'
    if kind == 'json':
        content_type, first = 'application/json', b'{"question":"'
    elif kind == 'urlencoded':
        content_type, first = 'application/x-www-form-urlencoded', b'field='
    else:
        filename = b'; filename="a.txt"' if kind == 'file' else b''
        first = b'--boundary\r\nContent-Disposition: form-data; name="file"' + filename + b'\r\n\r\n'
        content_type = 'multipart/form-data; boundary=boundary'
    async def stream():
        for part in [first, b'a' * 129, b'b' * 129]:
            consumed.append(part)
            yield part
    headers = {'content-type': content_type}
    if declared:
        headers['content-length'] = '1024'
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post(path, headers=headers, content=stream())
    assert response.status_code == 413
    assert response.json()['detail']['code'] == 'REQUEST_BODY_TOO_LARGE'
    auth.assert_not_called()
    assert len(consumed) == (0 if declared else 2)


@pytest.mark.anyio
@pytest.mark.parametrize('content_type,body', [
    ('multipart/form-data; boundary=b', b'--b\r\nContent-Disposition: form-data; name="field"\r\n\r\n' + b'a' * (1024 * 1024 + 1) + b'\r\n--b--\r\n'),
    ('application/x-www-form-urlencoded', b'field=' + b'a' * (1024 * 1024 + 1)),
])
async def test_patched_parser_rejects_large_text_fields(content_type, body):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/v1/faqs/import', content=body, headers={'content-type': content_type})
    assert response.status_code == 400


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'cp932'])
def test_text_validation_is_incremental_and_handles_split_characters(encoding):
    class BoundedReader(BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 64 * 1024
            return super().read(size)
    stream = BoundedReader(('a' * 65534 + '日本語' * 100).encode(encoding))
    _validate_content(UploadFile(stream, filename='test.txt'), 'txt', 'text/plain')
    assert stream.tell() == 0


def test_text_validation_rejects_incomplete_multibyte_character():
    with pytest.raises(FileUploadValidationError):
        _validate_content(UploadFile(BytesIO(b'a' * 65536 + b'\x81'), filename='test.txt'), 'txt', 'text/plain')


@pytest.mark.anyio
async def test_partial_upload_is_closed_on_stream_limit(monkeypatch):
    from tempfile import SpooledTemporaryFile
    from starlette import formparsers
    opened = []
    def tracked(*args, **kwargs):
        file = SpooledTemporaryFile(*args, **kwargs)
        opened.append(file)
        return file
    monkeypatch.setattr(formparsers, 'SpooledTemporaryFile', tracked)
    monkeypatch.setattr(limits, 'IMPORT_BODY_LIMIT', 128)
    async def stream():
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\n\r\n'
        yield b'x' * 129
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/v1/faqs/import', content=stream(), headers={'content-type': 'multipart/form-data; boundary=b'})
    assert response.status_code == 413
    assert opened and all(file.closed for file in opened)


@pytest.mark.anyio
@pytest.mark.parametrize('size,status', [(128, 200), (129, 413)])
async def test_exact_body_boundary(monkeypatch, size, status):
    from fastapi import FastAPI, Request
    monkeypatch.setattr(limits, 'DEFAULT_BODY_LIMIT', 128)
    probe = FastAPI()
    @probe.post('/probe')
    async def echo(request: Request):
        return {'size': len(await request.body())}
    probe.add_middleware(limits.BodyLimitMiddleware)
    async with AsyncClient(transport=ASGITransport(app=probe), base_url='http://test') as client:
        response = await client.post('/probe', content=b'x' * size)
    assert response.status_code == status
