from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.v1.chat import delete_chat_session, get_chat_session_history, list_chat_sessions, update_chat_session_title
from app.schemas.chat import ChatHistoryTitleUpdate
from app.services.chat_service import ChatConfigurationError, ChatService


@pytest.mark.anyio
async def test_chat_retrieves_generates_and_returns_unique_citations(monkeypatch):
    monkeypatch.setenv("CHAT_KNOWLEDGE_BASE_ID", "KB123")
    monkeypatch.setenv("CHAT_MODEL_ARN", "arn:aws:bedrock:ap-northeast-1::foundation-model/test")
    client = Mock()
    client.retrieve_and_generate.return_value = {
        "output": {"text": "貸与奨学金の回答です。"},
        "sessionId": "bedrock-session-1",
        "citations": [{
            "generatedResponsePart": {"textResponsePart": {"text": "回答部分"}},
            "retrievedReferences": [{
                "location": {"s3Location": {"uri": "s3://bucket/guide.md"}},
                "metadata": {"source_title": "奨学金案内"},
            }],
        }],
    }

    result = await ChatService(client).answer("申請期限は？")

    assert result.answer == "貸与奨学金の回答です。"
    assert result.bedrock_session_id == "bedrock-session-1"
    assert result.citations[0].title == "奨学金案内"
    request = client.retrieve_and_generate.call_args.kwargs
    assert request["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]["knowledgeBaseId"] == "KB123"
    assert request["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]["retrievalConfiguration"]["vectorSearchConfiguration"]["overrideSearchType"] == "HYBRID"
    inference = request["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]["generationConfiguration"]["inferenceConfig"]["textInferenceConfig"]
    assert inference["temperature"] == 0
    assert "topP" not in inference


@pytest.mark.anyio
async def test_chat_requires_knowledge_base_and_model(monkeypatch):
    monkeypatch.delenv("CHAT_KNOWLEDGE_BASE_ID", raising=False)
    monkeypatch.delenv("CHAT_MODEL_ARN", raising=False)

    with pytest.raises(ChatConfigurationError):
        await ChatService(Mock()).answer("質問")


@pytest.mark.anyio
async def test_chat_accepts_configured_prompt_with_required_placeholders(monkeypatch):
    monkeypatch.setenv("CHAT_KNOWLEDGE_BASE_ID", "KB123")
    monkeypatch.setenv("CHAT_MODEL_ARN", "arn:aws:bedrock:ap-northeast-1::foundation-model/test")
    monkeypatch.setenv("CHAT_SYSTEM_PROMPT", "資料:$search_results$ 質問:$query$")
    client = Mock()
    client.retrieve_and_generate.return_value = {"output": {"text": "回答"}, "citations": []}
    await ChatService(client).answer("質問")
    prompt = client.retrieve_and_generate.call_args.kwargs["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]["generationConfiguration"]["promptTemplate"]["textPromptTemplate"]
    assert prompt == "資料:$search_results$ 質問:$query$"


def test_chat_uses_best_enabled_faq_when_similarity_reaches_threshold(monkeypatch):
    monkeypatch.setenv("CHAT_FAQ_MATCH_THRESHOLD", "0.85")
    monkeypatch.setenv("CHAT_CURRENT_ACADEMIC_YEAR", "2026")
    faq = SimpleNamespace(
        id=12,
        question="予約採用の進学届はいつ提出しますか？",
        answer="2026年度は進学後に提出します。",
        similar_questions=[SimpleNamespace(question="予約採用の進学届の提出時期は？")],
    )

    result = ChatService.answer_from_faq("予約採用の進学届の提出時期は？", [faq])

    assert result is not None
    assert result.answer_type == "FAQ"
    assert result.faq_id == 12
    assert result.answer == "2026年度は進学後に提出します。"


def test_chat_falls_back_when_faq_similarity_is_below_threshold(monkeypatch):
    monkeypatch.setenv("CHAT_FAQ_MATCH_THRESHOLD", "0.85")
    faq = SimpleNamespace(
        id=12, question="予約採用について", answer="回答", similar_questions=[],
    )

    assert ChatService.answer_from_faq("給付奨学金の家計基準を教えて", [faq]) is None


def test_chat_warns_when_matched_faq_is_from_an_older_year(monkeypatch):
    monkeypatch.setenv("CHAT_FAQ_MATCH_THRESHOLD", "0.85")
    monkeypatch.setenv("CHAT_CURRENT_ACADEMIC_YEAR", "2026")
    faq = SimpleNamespace(
        id=20,
        question="2025年度の申請期限はいつですか？",
        answer="2025年4月30日です。",
        similar_questions=[],
    )

    result = ChatService.answer_from_faq("2025年度の申請期限はいつですか？", [faq])

    assert result is not None
    assert result.answer.startswith("※この回答は2025年度以前の情報です。2026年度の最新情報ではない可能性があります。")


@pytest.mark.anyio
async def test_chat_ui_config_uses_system_settings(monkeypatch):
    monkeypatch.setenv("CHAT_UI_TITLE", "設定済みチャット")
    monkeypatch.setenv("CHAT_INPUT_PLACEHOLDER", "質問内容を入力")
    monkeypatch.setenv("CHAT_HISTORY_ENABLED", "true")
    monkeypatch.setenv("CHAT_BAD_FEEDBACK_OPTIONS", "回答が違う|情報が不足")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/config")
    assert response.status_code == 200
    assert response.json()["title"] == "設定済みチャット"
    assert response.json()["input_placeholder"] == "質問内容を入力"
    assert response.json()["history_enabled"] is True
    assert response.json()["bad_options"] == ["回答が違う", "情報が不足"]


@pytest.mark.anyio
async def test_chat_history_searches_question_and_answer_content(monkeypatch):
    monkeypatch.setenv("ANALYTICS_IDENTITY_SECRET", "test-secret")
    started_at = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=uuid4(), title=None, started_at=started_at,
        interactions=[SimpleNamespace(sequence_number=1, processing_status="COMPLETED", question_text="予約採用", answer_text="進学届を提出します", updated_at=started_at)],
    )
    result = Mock()
    result.scalars.return_value.unique.return_value.all.return_value = [row]
    session = AsyncMock()
    session.execute.return_value = result
    current_user = SimpleNamespace(site="faculty", subject="staff-001")

    histories = await list_chat_sessions(limit=100, search="進学届", current_user=current_user, session=session)

    assert histories[0].title == "予約採用"
    assert "answer_text" in str(session.execute.call_args.args[0])
    assert "processing_status" in str(session.execute.call_args.args[0])


@pytest.mark.anyio
async def test_chat_history_title_update_and_delete_are_limited_to_owner(monkeypatch):
    monkeypatch.setenv("ANALYTICS_IDENTITY_SECRET", "test-secret")
    started_at = datetime.now(timezone.utc)
    row = SimpleNamespace(id=uuid4(), title=None, started_at=started_at, interactions=[])
    result = Mock()
    result.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute.return_value = result
    current_user = SimpleNamespace(site="faculty", subject="staff-001")

    updated = await update_chat_session_title(
        row.id, ChatHistoryTitleUpdate(title=" 変更後の名前 "), current_user=current_user, session=session,
    )
    assert updated.title == "変更後の名前"
    assert "visitor_key" in str(session.execute.call_args.args[0])
    session.commit.assert_awaited_once()

    session.commit.reset_mock()
    await delete_chat_session(row.id, current_user=current_user, session=session)
    session.delete.assert_awaited_once_with(row)
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_chat_history_detail_excludes_system_error_interactions(monkeypatch):
    monkeypatch.setenv("ANALYTICS_IDENTITY_SECRET", "test-secret")
    submitted_at = datetime.now(timezone.utc)
    failed = SimpleNamespace(
        id=uuid4(), sequence_number=1, processing_status="FAILED", question_text="失敗した質問",
        answer_text=None, answer_displayed_at=None, question_submitted_at=submitted_at,
        citations=None, feedback=None, answer_type=None,
    )
    completed = SimpleNamespace(
        id=uuid4(), sequence_number=2, processing_status="COMPLETED", question_text="成功した質問",
        answer_text="成功した回答", answer_displayed_at=submitted_at, question_submitted_at=submitted_at,
        citations=[], feedback=None, answer_type="GENERATED_AI",
    )
    row = SimpleNamespace(id=uuid4(), title=None, interactions=[failed, completed])
    result = Mock()
    result.scalar_one_or_none.return_value = row
    session = AsyncMock()
    session.execute.return_value = result

    detail = await get_chat_session_history(
        row.id, current_user=SimpleNamespace(site="faculty", subject="staff-001"), session=session,
    )

    assert detail.title == "成功した質問"
    assert [message.content for message in detail.messages] == ["成功した質問", "成功した回答"]
    assert "失敗した質問" not in [message.content for message in detail.messages]
