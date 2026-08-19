from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models.analytics import AccessLog, AnalyticsVisitor, ChatFeedback, ChatInteraction, ChatSession
from app.schemas.analytics import (
    AccessCreateRequest,
    ChatSessionCreateRequest,
    FeedbackUpsertRequest,
    InteractionCompletionRequest,
    InteractionCreateRequest,
)
from app.services.analytics_service import AnalyticsError, AnalyticsService


NOW = datetime(2026, 8, 19, 1, 0, tzinfo=timezone.utc)


def identity(kind="ANONYMOUS", identifier=None):
    return {"identity_kind": kind, "identifier": identifier or str(uuid4())}


def repository():
    repo = AsyncMock()
    repo.commit.return_value = None
    repo.rollback.return_value = None
    return repo


def test_requests_reject_plaintext_messages_and_naive_datetimes():
    with pytest.raises(ValidationError):
        AccessCreateRequest(id=uuid4(), identity=identity(), accessed_at=NOW, question="保存禁止")
    with pytest.raises(ValidationError):
        AccessCreateRequest(id=uuid4(), identity=identity(), accessed_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError):
        AccessCreateRequest(id=uuid4(), identity=identity(identifier="not-a-uuid"), accessed_at=NOW)


def test_comment_is_trimmed_limited_and_empty_is_null():
    assert FeedbackUpsertRequest(rating="GOOD", comment="  コメント  ").comment == "コメント"
    assert FeedbackUpsertRequest(rating="BAD", comment="   ").comment is None
    with pytest.raises(ValidationError):
        FeedbackUpsertRequest(rating="GOOD", comment="x" * 1001)


def test_identity_hmac_is_stable_and_does_not_retain_original_identifier():
    service = AnalyticsService(repository(), identity_secret="secret")
    first = service.visitor_key("AUTHENTICATED", "student-123")
    assert first == service.visitor_key("AUTHENTICATED", "student-123")
    assert first != service.visitor_key("ANONYMOUS", "student-123")
    assert "student-123" not in first and len(first) == 64


@pytest.mark.anyio
async def test_access_records_hashed_visitor_and_is_idempotent():
    repo = repository()
    visitor_id = uuid4()
    visitor = SimpleNamespace(id=visitor_id)
    access_id = uuid4()
    payload = AccessCreateRequest(id=access_id, identity=identity(), accessed_at=NOW)
    created = SimpleNamespace(id=access_id, visitor_id=visitor_id, accessed_at=NOW)
    repo.get_or_create_visitor.return_value = visitor
    repo.get_access.side_effect = [None, created]
    repo.create_access.return_value = created
    service = AnalyticsService(repo, identity_secret="secret")

    assert await service.record_access(payload) is created
    assert await service.record_access(payload) is created
    hashed_key = repo.get_or_create_visitor.await_args_list[0].args[0]
    assert payload.identity.identifier not in hashed_key
    repo.create_access.assert_awaited_once()


@pytest.mark.anyio
async def test_access_idempotency_conflict_rolls_back():
    repo = repository()
    visitor = SimpleNamespace(id=uuid4())
    repo.get_or_create_visitor.return_value = visitor
    repo.get_access.return_value = SimpleNamespace(id=uuid4(), visitor_id=visitor.id, accessed_at=NOW + timedelta(seconds=1))
    service = AnalyticsService(repo, identity_secret="secret")
    with pytest.raises(AnalyticsError) as error:
        await service.record_access(AccessCreateRequest(id=uuid4(), identity=identity(), accessed_at=NOW))
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    repo.rollback.assert_awaited()


@pytest.mark.anyio
async def test_chat_session_and_interaction_start_follow_session_boundary():
    repo = repository()
    visitor = SimpleNamespace(id=uuid4())
    session_id = uuid4()
    session = SimpleNamespace(id=session_id, visitor_id=visitor.id, started_at=NOW, ended_at=None)
    repo.get_or_create_visitor.return_value = visitor
    repo.get_chat_session.side_effect = [None, session]
    repo.create_chat_session.return_value = session
    service = AnalyticsService(repo, identity_secret="secret")
    await service.start_chat_session(ChatSessionCreateRequest(id=session_id, identity=identity(), started_at=NOW))

    interaction_id = uuid4()
    interaction = SimpleNamespace(id=interaction_id)
    repo.get_chat_session.return_value = session
    repo.get_interaction.return_value = None
    repo.create_interaction.return_value = interaction
    result = await service.start_interaction(
        session_id,
        InteractionCreateRequest(id=interaction_id, sequence_number=1, question_submitted_at=NOW + timedelta(seconds=1)),
    )
    assert result is interaction
    repo.create_interaction.assert_awaited_once()


@pytest.mark.anyio
async def test_interaction_missing_session_and_duplicate_sequence_errors():
    repo = repository()
    service = AnalyticsService(repo, identity_secret="secret")
    repo.get_chat_session.return_value = None
    with pytest.raises(AnalyticsError) as missing:
        await service.start_interaction(uuid4(), InteractionCreateRequest(id=uuid4(), sequence_number=1, question_submitted_at=NOW))
    assert missing.value.code == "CHAT_SESSION_NOT_FOUND"

    repo.get_chat_session.return_value = SimpleNamespace(started_at=NOW)
    repo.get_interaction.return_value = None
    repo.create_interaction.side_effect = IntegrityError("insert", {}, Exception("unique"))
    with pytest.raises(AnalyticsError) as conflict:
        await service.start_interaction(uuid4(), InteractionCreateRequest(id=uuid4(), sequence_number=1, question_submitted_at=NOW))
    assert conflict.value.code == "INTERACTION_SEQUENCE_CONFLICT"


@pytest.mark.anyio
@pytest.mark.parametrize("answer_type,faq_id", [("FAQ", 1), ("GENERATED_AI", None), ("NO_ANSWER", None)])
async def test_completion_supports_all_answer_types(answer_type, faq_id):
    repo = repository()
    row = SimpleNamespace(
        processing_status="PROCESSING", answer_type=None, answer_displayed_at=None, faq_id=None,
        question_submitted_at=NOW, updated_at=NOW,
    )
    repo.get_interaction.return_value = row
    repo.faq_exists.return_value = True
    payload = InteractionCompletionRequest(
        processing_status="COMPLETED", answer_type=answer_type,
        answer_displayed_at=NOW + timedelta(seconds=2), faq_id=faq_id,
    )
    result = await AnalyticsService(repo, "secret").complete_interaction(uuid4(), payload)
    assert result.processing_status == "COMPLETED" and result.answer_type == answer_type
    if answer_type == "FAQ":
        repo.faq_exists.assert_awaited_once_with(1)


@pytest.mark.anyio
async def test_failed_completion_has_no_answer_and_is_idempotent():
    repo = repository()
    row = SimpleNamespace(
        processing_status="PROCESSING", answer_type=None, answer_displayed_at=None, faq_id=None,
        question_submitted_at=NOW, updated_at=NOW,
    )
    repo.get_interaction.return_value = row
    service = AnalyticsService(repo, "secret")
    payload = InteractionCompletionRequest(processing_status="FAILED")
    await service.complete_interaction(uuid4(), payload)
    await service.complete_interaction(uuid4(), payload)
    assert row.processing_status == "FAILED" and row.answer_type is None and row.answer_displayed_at is None


@pytest.mark.anyio
async def test_feedback_upsert_allows_good_to_bad_and_rejects_no_answer():
    repo = repository()
    interaction_id = uuid4()
    interaction = SimpleNamespace(processing_status="COMPLETED", answer_type="FAQ")
    feedback = SimpleNamespace(interaction_id=interaction_id, rating="GOOD", comment=None, updated_at=NOW)
    repo.get_interaction.return_value = interaction
    repo.get_feedback.side_effect = [None, feedback]
    repo.create_feedback.return_value = feedback
    service = AnalyticsService(repo, "secret")
    await service.upsert_feedback(interaction_id, FeedbackUpsertRequest(rating="GOOD", comment="良い"))
    updated = await service.upsert_feedback(interaction_id, FeedbackUpsertRequest(rating="BAD", comment="改善希望"))
    assert updated.rating == "BAD" and updated.comment == "改善希望"

    interaction.answer_type = "NO_ANSWER"
    with pytest.raises(AnalyticsError) as error:
        await service.upsert_feedback(interaction_id, FeedbackUpsertRequest(rating="BAD"))
    assert error.value.code == "FEEDBACK_NOT_ALLOWED"


def test_model_constraints_fks_and_indexes_match_migration_contract():
    assert {index.name for index in AccessLog.__table__.indexes} == {
        "ix_access_logs_accessed_at", "ix_access_logs_visitor_accessed_at",
    }
    assert "ix_chat_sessions_visitor_started_at" in {index.name for index in ChatSession.__table__.indexes}
    assert "ix_chat_interactions_answer_type_question_submitted_at" in {index.name for index in ChatInteraction.__table__.indexes}
    assert next(iter(ChatFeedback.__table__.c.interaction_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(ChatInteraction.__table__.c.faq_id.foreign_keys)).ondelete == "SET NULL"
    assert AnalyticsVisitor.__table__.c.visitor_key.unique is None  # named table-level UNIQUE is used
