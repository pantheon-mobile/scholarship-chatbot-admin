from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1.chat import _generate_message
from app.repositories.analytics import AnalyticsRepository
from app.schemas.chat import ChatMessageRequest
from app.services.chat_context_service import ChatContextService
from app.services.chat_service import ChatService
from app.services.dashboard_service import DashboardService
from app.services.faq_classification_service import FaqClassificationError, FaqClassificationService
from tests.test_approved_security_limits import db, limit_engine, seed_chat


@pytest.mark.anyio
@pytest.mark.parametrize("similar", [False, True])
async def test_original_exact_faq_bypasses_context_and_model(monkeypatch, similar):
    monkeypatch.setenv("ANALYTICS_IDENTITY_SECRET", "test")
    question = "長万部に送らないとダメですか？この窓口への提出ではダメですか？"
    faq = SimpleNamespace(id=13, question="別の質問" if similar else question,
                          similar_questions=[SimpleNamespace(question=question)] if similar else [], answer="FAQの回答",
                          classification_assignments=[SimpleNamespace(
                              classification_type=SimpleNamespace(type_code="FAQ_TYPE_3"),
                              classification_value=SimpleNamespace(value_name="2021"))])
    session = AsyncMock()
    result = Mock()
    result.scalars.return_value.unique.return_value.all.return_value = [faq]
    session.execute.return_value = result
    session_id, interaction_id = uuid4(), uuid4()
    row = SimpleNamespace(chat_session_id=session_id, question_text=question, processing_status="PROCESSING")
    monkeypatch.setattr(AnalyticsRepository, "get_owned_interaction", AsyncMock(return_value=row))
    context = AsyncMock(side_effect=AssertionError("Exact FAQ must not resolve context"))
    monkeypatch.setattr(ChatContextService, "resolve", context)
    service = Mock()
    response = await _generate_message(
        ChatMessageRequest(question=question, chat_session_id=session_id, interaction_id=interaction_id),
        SimpleNamespace(site="faculty", subject="test"), service, session,
    )
    assert response.answer_type == "FAQ" and response.faq_id == 13
    assert row.answer_text == "FAQの回答\n\n【FAQ回答】登録年度：2021"
    assert row.answer_text == response.answer and row.processing_status == "COMPLETED"
    context.assert_not_awaited()
    service.answer.assert_not_called()
    session.commit.assert_awaited_once()


def test_exact_check_does_not_accept_partial_question_or_normalize_distinct_text():
    faq = SimpleNamespace(id=1, question="必要ですか？", similar_questions=[], answer="回答")
    assert ChatService.answer_from_faq("必要ですか", [faq], exact_only=True) is None
    assert ChatService.answer_from_faq("必要ですか？", [faq], exact_only=True).faq_id == 1


@pytest.mark.anyio
async def test_used_classification_returns_business_error_and_rolls_back():
    repository = AsyncMock()
    repository.get_type.return_value = SimpleNamespace(id=1)
    repository.get_value.return_value = SimpleNamespace(id=2, classification_type_id=1)
    original = Exception("foreign key violation")
    original.sqlstate = "23503"
    repository.delete_value.side_effect = IntegrityError("delete", {}, original)
    with pytest.raises(FaqClassificationError) as caught:
        await FaqClassificationService(repository).delete_value(1, 2, 1)
    assert caught.value.code == "FAQ_CLASSIFICATION_VALUE_IN_USE"
    assert "FAQで使用中" in caught.value.message
    repository.rollback.assert_awaited_once()
    repository.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_ng_feedback_counts_in_rating_and_satisfaction():
    from tests.test_dashboard import aggregate_data
    repository = AsyncMock()
    repository.aggregate.return_value = aggregate_data(good_count=1, bad_count=2)
    result = await DashboardService(repository).get(date(2026, 10, 1), date(2026, 10, 6))
    metrics = result.basic_metrics
    assert metrics.good_count + metrics.bad_count + metrics.unrated_count == metrics.response_count
    assert metrics.unrated_count == 1
    assert metrics.satisfaction_rate == 33.3
    assert metrics.valid_answer_count == 3 and metrics.no_answer_count == 1


@pytest.mark.anyio
async def test_database_aggregation_includes_ng_feedback(db):
    from datetime import datetime, timedelta, timezone
    from app.repositories.dashboard import DashboardRepository
    from app.models.analytics import ChatFeedback
    _, interaction, _ = await seed_chat(db, "ng-rating-issue-32", kind="NO_ANSWER")
    _, good_interaction, _ = await seed_chat(db, "good-rating-issue-32", kind="GENERATED_AI")
    feedback = await db.get(ChatFeedback, good_interaction.id)
    feedback.rating = "GOOD"
    await db.flush()
    now = datetime.now(timezone.utc)
    data = await DashboardRepository(db).aggregate(now - timedelta(days=1), now + timedelta(days=1))
    counts = data["interactions"]
    assert counts["no_answer_count"] == 1
    assert counts["valid_answer_count"] == 1
    assert counts["good_count"] == 1 and counts["bad_count"] == 1


@pytest.mark.anyio
async def test_real_foreign_key_error_is_reported_as_classification_in_use(db):
    from app.models.faq import Faq, FaqClassificationAssignment
    from app.models.faq_classification import FaqClassificationType, FaqClassificationValue
    from app.repositories.faq_classification import FaqClassificationRepository
    kind = FaqClassificationType(type_code="issue35", fixed_name="区分", display_label="区分", display_order=1)
    faq = Faq(question="質問", answer="回答", chat_enabled=True)
    db.add_all([kind, faq])
    await db.flush()
    value = FaqClassificationValue(classification_type_id=kind.id, value_name="使用中", display_order=1)
    db.add(value)
    await db.flush()
    db.add(FaqClassificationAssignment(faq_id=faq.id, classification_type_id=kind.id, classification_value_id=value.id))
    await db.commit()
    kind_id, value_id, version = kind.id, value.id, value.version
    with pytest.raises(FaqClassificationError) as caught:
        await FaqClassificationService(FaqClassificationRepository(db)).delete_value(kind_id, value_id, version)
    assert caught.value.code == "FAQ_CLASSIFICATION_VALUE_IN_USE"
    assert await db.get(FaqClassificationValue, value_id) is not None
