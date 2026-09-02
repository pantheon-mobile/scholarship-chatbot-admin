from unittest.mock import Mock

import pytest

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


@pytest.mark.anyio
async def test_chat_requires_knowledge_base_and_model(monkeypatch):
    monkeypatch.delenv("CHAT_KNOWLEDGE_BASE_ID", raising=False)
    monkeypatch.delenv("CHAT_MODEL_ARN", raising=False)

    with pytest.raises(ChatConfigurationError):
        await ChatService(Mock()).answer("質問")
