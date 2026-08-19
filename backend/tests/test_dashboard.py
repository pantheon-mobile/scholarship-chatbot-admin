from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.repositories.dashboard import DashboardRepository
from app.services.dashboard_service import DashboardError, DashboardService


def aggregate_data(**interaction_overrides):
    interactions = {
        "response_count": 4,
        "valid_answer_count": 3,
        "faq_count": 2,
        "generated_ai_count": 1,
        "no_answer_count": 1,
        "good_count": 1,
        "bad_count": 1,
        "comment_count": 2,
        "good_comment_count": 1,
        "bad_comment_count": 1,
        "response_time_average": 2.25,
        "response_time_minimum": 1.0,
        "response_time_maximum": 4.0,
        **interaction_overrides,
    }
    return {
        "access": {"access_count": 5, "access_user_count": 2},
        "sessions": {"chat_count": 3, "chat_user_count": 2},
        "interactions": interactions,
        "session_time": {0: 2, 4: 1},
        "interaction_time": {0: 3, 5: 1},
        "session_weekdays": {1: 2, 7: 1},
        "interaction_weekdays": {1: 3, 7: 1},
    }


@pytest.mark.anyio
async def test_all_metrics_formulas_jst_bounds_and_zero_bucket_completion():
    repository = AsyncMock()
    repository.aggregate.return_value = aggregate_data()
    result = await DashboardService(repository).get(date(2026, 8, 1), date(2026, 8, 10))
    basic = result.basic_metrics
    assert (basic.access_count, basic.access_user_count, basic.chat_count, basic.chat_user_count) == (5, 2, 3, 2)
    assert (basic.average_chats_per_day, basic.average_chats_per_user) == (0.3, 1.5)
    assert (basic.response_count, basic.average_responses_per_chat, basic.average_responses_per_user) == (4, 1.3, 2.0)
    assert (basic.valid_answer_count, basic.no_answer_count, basic.answer_rate) == (3, 1, 75.0)
    assert (basic.good_count, basic.bad_count, basic.unrated_count, basic.satisfaction_rate) == (1, 1, 1, 50.0)
    assert (basic.comment_count, basic.good_comment_count, basic.bad_comment_count) == (2, 1, 1)
    assert (basic.response_time.average_seconds, basic.response_time.minimum_seconds, basic.response_time.maximum_seconds) == (2.3, 1.0, 4.0)
    assert len(result.time_buckets) == 8 and len(result.weekday_buckets) == 7
    assert [item.key for item in result.time_buckets] == ["9-12", "12-15", "15-18", "18-21", "21-0", "0-3", "3-6", "6-9"]
    assert result.time_buckets[1].chat_count == 0 and result.weekday_buckets[1].response_count == 0
    start, end = repository.aggregate.await_args.args
    assert start == datetime(2026, 7, 31, 15, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)


@pytest.mark.anyio
async def test_zero_counts_return_null_averages_and_rates():
    repository = AsyncMock()
    repository.aggregate.return_value = {
        "access": {"access_count": 0, "access_user_count": 0},
        "sessions": {"chat_count": 0, "chat_user_count": 0},
        "interactions": {key: 0 for key in (
            "response_count", "valid_answer_count", "faq_count", "generated_ai_count", "no_answer_count",
            "good_count", "bad_count", "comment_count", "good_comment_count", "bad_comment_count",
        )} | {"response_time_average": None, "response_time_minimum": None, "response_time_maximum": None},
        "session_time": {}, "interaction_time": {}, "session_weekdays": {}, "interaction_weekdays": {},
    }
    result = await DashboardService(repository).get(date(2026, 8, 19), date(2026, 8, 19))
    assert result.basic_metrics.average_chats_per_user is None
    assert result.basic_metrics.answer_rate is None
    assert result.basic_metrics.satisfaction_rate is None
    assert result.answer_types.faq_rate is None


@pytest.mark.anyio
async def test_invalid_date_range_is_422_domain_error_without_query():
    repository = AsyncMock()
    with pytest.raises(DashboardError) as error:
        await DashboardService(repository).get(date(2026, 8, 20), date(2026, 8, 19))
    assert error.value.code == "INVALID_DATE_RANGE"
    repository.aggregate.assert_not_awaited()


def test_dashboard_query_count_is_constant_not_data_dependent():
    assert DashboardRepository.QUERY_COUNT == 7


@pytest.mark.anyio
@pytest.mark.parametrize("nominal_record_count", [10, 100])
async def test_repository_executes_seven_queries_regardless_of_record_count(nominal_record_count):
    class Result:
        def __init__(self, one=None, all_rows=None):
            self.one_row = one
            self.all_rows = all_rows or []

        def mappings(self):
            return self

        def one(self):
            return self.one_row

        def all(self):
            return self.all_rows

    session = AsyncMock()
    session.execute.side_effect = [
        Result({"access_count": nominal_record_count, "access_user_count": 2}),
        Result({"chat_count": nominal_record_count, "chat_user_count": 2}),
        Result(aggregate_data()["interactions"]),
        Result(all_rows=[]), Result(all_rows=[]), Result(all_rows=[]), Result(all_rows=[]),
    ]
    await DashboardRepository(session).aggregate(
        datetime(2026, 8, 1, tzinfo=timezone.utc), datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert session.execute.await_count == DashboardRepository.QUERY_COUNT == 7
