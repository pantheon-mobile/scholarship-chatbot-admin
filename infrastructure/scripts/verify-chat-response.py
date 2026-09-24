"""Exercise the authenticated, server-recorded chat flow with an existing cookie jar."""
import http.cookiejar
import json
import sys
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4

cookie_path, host = sys.argv[1:]
jar = http.cookiejar.MozillaCookieJar(cookie_path)
jar.load(ignore_discard=True, ignore_expires=False)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def call(path, payload=None, method='POST'):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(host.rstrip('/') + '/api/v1' + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json', 'Origin': host.rstrip('/')})
    with opener.open(request, timeout=180) as response:
        body = response.read()
        return json.loads(body) if body else None

at = datetime.now(timezone.utc).isoformat()
session_id, interaction_id = str(uuid4()), str(uuid4())
question = '登録資料に情報がない場合の動作確認です'
call('/analytics/chat-sessions', {'id': session_id, 'identity': {'identity_kind': 'AUTHENTICATED', 'identifier': 'smoke-test'}, 'started_at': at})
try:
    call(f'/analytics/chat-sessions/{session_id}/interactions', {'id': interaction_id, 'sequence_number': 1, 'question_submitted_at': at, 'question_text': question})
    answer = call('/chat/messages', {'question': question, 'chat_session_id': session_id, 'interaction_id': interaction_id})
    assert isinstance(answer.get('answer'), str) and answer['answer']
    history = call(f'/chat/sessions/{session_id}', method='GET')
    assert history['messages'][-1]['content'] == answer['answer']
    print('Chat response and server-saved history verified')
finally:
    call(f'/chat/sessions/{session_id}', method='DELETE')
