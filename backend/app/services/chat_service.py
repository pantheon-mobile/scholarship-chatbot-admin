from __future__ import annotations

import asyncio
import logging
import os
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import boto3

from app.schemas.chat import ChatCitation, ChatMessageResponse


logger = logging.getLogger(__name__)

DEFAULT_CHAT_PROMPT = (
    "あなたは大学の奨学金案内チャットボットです。"
    "検索結果に記載された事実だけを使い、日本語で簡潔かつ正確に回答してください。"
    "情報が不足する場合は推測せず、確認先または不足している情報を案内してください。"
    "検索結果:\n$search_results$\n\n質問:$query$"
)


class ChatConfigurationError(Exception):
    pass


class ChatGenerationError(Exception):
    pass


class ChatService:
    PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    def __init__(self, client=None) -> None:
        self.region = os.getenv("AWS_REGION", "ap-northeast-1")
        self.knowledge_base_id = os.getenv("CHAT_KNOWLEDGE_BASE_ID", "").strip()
        self.model_arn = os.getenv("CHAT_MODEL_ARN", "").strip()
        self.prompt = os.getenv("CHAT_SYSTEM_PROMPT", DEFAULT_CHAT_PROMPT).strip() or DEFAULT_CHAT_PROMPT
        self.client = client

    @staticmethod
    def _normalize_question(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return "".join(character for character in normalized if character.isalnum())

    @classmethod
    def _similarity(cls, left: str, right: str) -> float:
        normalized_left = cls._normalize_question(left)
        normalized_right = cls._normalize_question(right)
        if not normalized_left or not normalized_right:
            return 0.0
        return SequenceMatcher(None, normalized_left, normalized_right).ratio()

    @staticmethod
    def _faq_threshold() -> float:
        try:
            return max(0.0, min(float(os.getenv("CHAT_FAQ_MATCH_THRESHOLD", "0.85")), 1.0))
        except ValueError:
            return 0.85

    @staticmethod
    def _current_academic_year() -> int:
        try:
            return int(os.getenv("CHAT_CURRENT_ACADEMIC_YEAR", ""))
        except ValueError:
            return datetime.now(ZoneInfo("Asia/Tokyo")).year

    @classmethod
    def answer_from_faq(cls, question: str, faqs: list) -> ChatMessageResponse | None:
        best_faq = None
        best_score = 0.0
        for faq in faqs:
            candidate_questions = [faq.question, *(item.question for item in faq.similar_questions)]
            score = max((cls._similarity(question, candidate) for candidate in candidate_questions), default=0.0)
            if score > best_score:
                best_faq = faq
                best_score = score
        if best_faq is None or best_score < cls._faq_threshold():
            return None

        answer = str(best_faq.answer).strip()
        current_year = cls._current_academic_year()
        years = [int(value) for value in re.findall(r"(?<!\d)(20\d{2})(?:年度|年)?", f"{best_faq.question}\n{answer}")]
        if years and max(years) < current_year:
            answer = (
                f"※この回答は{max(years)}年度以前の情報です。"
                f"{current_year}年度の最新情報ではない可能性があります。\n\n{answer}"
            )
        return ChatMessageResponse(
            answer=answer,
            answer_type="FAQ",
            faq_id=int(best_faq.id),
            citations=[],
        )

    async def answer(
        self, question: str, bedrock_session_id: str | None = None
    ) -> ChatMessageResponse:
        if not self.knowledge_base_id or not self.model_arn:
            raise ChatConfigurationError("CHAT_KNOWLEDGE_BASE_ID and CHAT_MODEL_ARN are required")
        if len(self.prompt) > 5000 or "$search_results$" not in self.prompt or "$query$" not in self.prompt:
            raise ChatConfigurationError("CHAT_SYSTEM_PROMPT must be within 5000 characters and contain required placeholders")
        try:
            response = await asyncio.to_thread(
                self._retrieve_and_generate, question.strip(), bedrock_session_id
            )
        except ChatConfigurationError:
            raise
        except Exception as error:
            logger.exception("Bedrock chat response failed")
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
        selected_priority = self._select_priority(client, question)
        vector_config: dict = {
            "numberOfResults": int(os.getenv("CHAT_NUMBER_OF_RESULTS", "5")),
            "overrideSearchType": os.getenv("CHAT_SEARCH_TYPE", "HYBRID"),
            "filter": self._answer_source_filter(selected_priority),
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
                            }
                        },
                        "promptTemplate": {
                            "textPromptTemplate": self.prompt
                        },
                    },
                },
            },
        }
        if bedrock_session_id:
            request["sessionId"] = bedrock_session_id
        return client.retrieve_and_generate(**request)

    @staticmethod
    def _answer_source_filter(priority: str | None = None) -> dict:
        enabled = {"equals": {"key": "answer_source_enabled", "value": True}}
        if priority is None:
            return enabled
        return {"andAll": [
            enabled,
            {"equals": {"key": "answer_priority", "value": priority}},
        ]}

    def _select_priority(self, client, question: str) -> str | None:
        """Prefer priority when candidates are close, without hiding a clearly better result."""
        response = client.retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={"text": question},
            retrievalConfiguration={"vectorSearchConfiguration": {
                "numberOfResults": int(os.getenv("CHAT_PRIORITY_CANDIDATE_COUNT", "20")),
                "overrideSearchType": os.getenv("CHAT_SEARCH_TYPE", "HYBRID"),
                "filter": self._answer_source_filter(),
            }},
        )
        candidates: list[tuple[float, str]] = []
        for item in response.get("retrievalResults", []) or []:
            priority = str((item.get("metadata") or {}).get("answer_priority", "")).upper()
            if priority not in self.PRIORITY_ORDER:
                continue
            try:
                score = float(item.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0
            candidates.append((score, priority))
        if not candidates:
            return None
        best_score = max(score for score, _priority in candidates)
        try:
            tolerance = max(0.0, float(os.getenv("CHAT_PRIORITY_SCORE_TOLERANCE", "0.05")))
        except ValueError:
            tolerance = 0.05
        near_best = {
            priority for score, priority in candidates
            if score >= best_score - tolerance
        }
        return min(near_best, key=self.PRIORITY_ORDER.__getitem__)

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
