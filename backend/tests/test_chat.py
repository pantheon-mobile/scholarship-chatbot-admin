from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
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


@pytest.mark.anyio
async def test_chat_ui_config_uses_system_settings(monkeypatch):
    monkeypatch.setenv("CHAT_UI_TITLE", "設定済みチャット")
    monkeypatch.setenv("CHAT_HISTORY_ENABLED", "true")
    monkeypatch.setenv("CHAT_BAD_FEEDBACK_OPTIONS", "回答が違う|情報が不足")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/config")
    assert response.status_code == 200
    assert response.json()["title"] == "設定済みチャット"
    assert response.json()["history_enabled"] is True
    assert response.json()["bad_options"] == ["回答が違う", "情報が不足"]
