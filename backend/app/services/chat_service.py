from __future__ import annotations

import asyncio
import os
from pathlib import PurePosixPath
from urllib.parse import urlparse

import boto3

from app.schemas.chat import ChatCitation, ChatMessageResponse


class ChatConfigurationError(Exception):
    pass


class ChatGenerationError(Exception):
    pass


class ChatService:
    def __init__(self, client=None) -> None:
        self.region = os.getenv("AWS_REGION", "ap-northeast-1")
        self.knowledge_base_id = os.getenv("CHAT_KNOWLEDGE_BASE_ID", "").strip()
        self.model_arn = os.getenv("CHAT_MODEL_ARN", "").strip()
        self.client = client

    async def answer(
        self, question: str, bedrock_session_id: str | None = None
    ) -> ChatMessageResponse:
        if not self.knowledge_base_id or not self.model_arn:
            raise ChatConfigurationError("CHAT_KNOWLEDGE_BASE_ID and CHAT_MODEL_ARN are required")
        try:
            response = await asyncio.to_thread(
                self._retrieve_and_generate, question.strip(), bedrock_session_id
            )
        except ChatConfigurationError:
            raise
        except Exception as error:
            raise ChatGenerationError("Bedrock response failed") from error
        answer = str(response.get("output", {}).get("text", "")).strip()
        if not answer:
            raise ChatGenerationError("Bedrock returned an empty answer")
        return ChatMessageResponse(
            answer=answer,
            answer_type="GENERATED_AI",
            bedrock_session_id=response.get("sessionId"),
            citations=self._citations(response),
        )

    def _retrieve_and_generate(self, question: str, bedrock_session_id: str | None):
        client = self.client or boto3.client("bedrock-agent-runtime", region_name=self.region)
        vector_config: dict = {
            "numberOfResults": int(os.getenv("CHAT_NUMBER_OF_RESULTS", "5")),
            "overrideSearchType": os.getenv("CHAT_SEARCH_TYPE", "HYBRID"),
        }
        request = {
            "input": {"text": question},
            "retrieveAndGenerateConfiguration": {
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": self.knowledge_base_id,
                    "modelArn": self.model_arn,
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": vector_config,
                    },
                    "generationConfiguration": {
                        "inferenceConfig": {
                            "textInferenceConfig": {
                                "maxTokens": int(os.getenv("CHAT_MAX_TOKENS", "1200")),
                                "temperature": 0,
                                "topP": 1,
                            }
                        },
                        "promptTemplate": {
                            "textPromptTemplate": (
                                "あなたは大学の奨学金案内チャットボットです。"
                                "検索結果に記載された事実だけを使い、日本語で簡潔かつ正確に回答してください。"
                                "情報が不足する場合は推測せず、確認先または不足している情報を案内してください。"
                                "検索結果:\n$search_results$\n\n質問:$query$"
                            )
                        },
                    },
                },
            },
        }
        if bedrock_session_id:
            request["sessionId"] = bedrock_session_id
        return client.retrieve_and_generate(**request)

    @staticmethod
    def _citations(response: dict) -> list[ChatCitation]:
        citations: list[ChatCitation] = []
        seen: set[tuple[str, str | None]] = set()
        for citation in response.get("citations", []) or []:
            excerpt = citation.get("generatedResponsePart", {}).get("textResponsePart", {}).get("text")
            for reference in citation.get("retrievedReferences", []) or []:
                location = reference.get("location", {}) or {}
                uri = None
                for value in location.values():
                    if isinstance(value, dict):
                        uri = value.get("uri") or value.get("url") or uri
                metadata = reference.get("metadata", {}) or {}
                uri = uri or metadata.get("source_url") or metadata.get("x-amz-bedrock-kb-source-uri")
                title = str(metadata.get("source_title") or metadata.get("source_file_name") or "参照資料")
                if title == "参照資料" and uri:
                    title = PurePosixPath(urlparse(str(uri)).path).name or title
                key = (title, str(uri) if uri else None)
                if key in seen:
                    continue
                seen.add(key)
                citations.append(ChatCitation(
                    title=title,
                    uri=str(uri) if uri else None,
                    excerpt=str(excerpt).strip()[:500] if excerpt else None,
                ))
        return citations
