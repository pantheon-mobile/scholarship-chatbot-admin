from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DashboardRepository:
    QUERY_COUNT = 7

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def aggregate(self, start_utc: datetime, end_utc: datetime) -> dict:
        parameters = {"start_at": start_utc, "end_at": end_utc}
        access = (await self.session.execute(text("""
            SELECT COUNT(*)::bigint AS access_count,
                   COUNT(DISTINCT visitor_id)::bigint AS access_user_count
            FROM access_logs
            WHERE accessed_at >= :start_at AND accessed_at < :end_at
        """), parameters)).mappings().one()

        sessions = (await self.session.execute(text("""
            SELECT COUNT(*)::bigint AS chat_count,
                   COUNT(DISTINCT visitor_id)::bigint AS chat_user_count
            FROM chat_sessions
            WHERE started_at >= :start_at AND started_at < :end_at
        """), parameters)).mappings().one()

        interactions = (await self.session.execute(text("""
            SELECT
                COUNT(*)::bigint AS response_count,
                COUNT(*) FILTER (WHERE i.answer_type IN ('FAQ', 'GENERATED_AI'))::bigint AS valid_answer_count,
                COUNT(*) FILTER (WHERE i.answer_type = 'FAQ')::bigint AS faq_count,
                COUNT(*) FILTER (WHERE i.answer_type = 'GENERATED_AI')::bigint AS generated_ai_count,
                COUNT(*) FILTER (WHERE i.answer_type = 'NO_ANSWER')::bigint AS no_answer_count,
                COUNT(*) FILTER (
                    WHERE i.answer_type IN ('FAQ', 'GENERATED_AI') AND f.rating = 'GOOD'
                )::bigint AS good_count,
                COUNT(*) FILTER (
                    WHERE i.answer_type IN ('FAQ', 'GENERATED_AI') AND f.rating = 'BAD'
                )::bigint AS bad_count,
                COUNT(*) FILTER (WHERE f.comment IS NOT NULL)::bigint AS comment_count,
                COUNT(*) FILTER (WHERE f.rating = 'GOOD' AND f.comment IS NOT NULL)::bigint AS good_comment_count,
                COUNT(*) FILTER (WHERE f.rating = 'BAD' AND f.comment IS NOT NULL)::bigint AS bad_comment_count,
                AVG(EXTRACT(EPOCH FROM (i.answer_displayed_at - i.question_submitted_at))) AS response_time_average,
                MIN(EXTRACT(EPOCH FROM (i.answer_displayed_at - i.question_submitted_at))) AS response_time_minimum,
                MAX(EXTRACT(EPOCH FROM (i.answer_displayed_at - i.question_submitted_at))) AS response_time_maximum
            FROM chat_interactions i
            LEFT JOIN chat_feedback f ON f.interaction_id = i.id
            WHERE i.processing_status = 'COMPLETED'
              AND i.question_submitted_at >= :start_at AND i.question_submitted_at < :end_at
        """), parameters)).mappings().one()

        session_time = await self._bucket_counts("chat_sessions", "started_at", start_utc, end_utc, time_bucket=True)
        interaction_time = await self._bucket_counts(
            "chat_interactions", "question_submitted_at", start_utc, end_utc, time_bucket=True, completed_only=True,
        )
        session_weekdays = await self._bucket_counts("chat_sessions", "started_at", start_utc, end_utc, time_bucket=False)
        interaction_weekdays = await self._bucket_counts(
            "chat_interactions", "question_submitted_at", start_utc, end_utc, time_bucket=False, completed_only=True,
        )
        return {
            "access": dict(access),
            "sessions": dict(sessions),
            "interactions": dict(interactions),
            "session_time": session_time,
            "interaction_time": interaction_time,
            "session_weekdays": session_weekdays,
            "interaction_weekdays": interaction_weekdays,
        }

    async def _bucket_counts(
        self,
        table_name: str,
        timestamp_column: str,
        start_utc: datetime,
        end_utc: datetime,
        *,
        time_bucket: bool,
        completed_only: bool = False,
    ) -> dict[int, int]:
        # table and column names are fixed internal constants, never request parameters.
        local_timestamp = f"timezone('Asia/Tokyo', {timestamp_column})"
        if time_bucket:
            hour = f"EXTRACT(HOUR FROM {local_timestamp})::integer"
            bucket = (
                f"CASE WHEN {hour} >= 9 THEN (({hour} - 9) / 3)::integer "
                f"ELSE (5 + ({hour} / 3)::integer) END"
            )
        else:
            bucket = f"EXTRACT(ISODOW FROM {local_timestamp})::integer"
        status = " AND processing_status = 'COMPLETED'" if completed_only else ""
        statement = text(f"""
            SELECT {bucket} AS bucket, COUNT(*)::bigint AS count
            FROM {table_name}
            WHERE {timestamp_column} >= :start_at AND {timestamp_column} < :end_at{status}
            GROUP BY bucket
        """)
        rows = (await self.session.execute(statement, {"start_at": start_utc, "end_at": end_utc})).mappings().all()
        return {int(row["bucket"]): int(row["count"]) for row in rows}
