from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ReportingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def chat_histories(
        self,
        start_at: datetime,
        end_at: datetime,
        *,
        visitor_key: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict]]:
        filters = "AND v.visitor_key = :visitor_key" if visitor_key else ""
        parameters = {
            "start_at": start_at,
            "end_at": end_at,
            "visitor_key": visitor_key,
            "limit": limit,
            "offset": offset,
        }
        total = (await self.session.execute(text(f"""
            SELECT COUNT(*)::bigint
            FROM chat_sessions s
            JOIN analytics_visitors v ON v.id = s.visitor_id
            WHERE s.started_at >= :start_at AND s.started_at < :end_at {filters}
        """), parameters)).scalar_one()
        rows = (await self.session.execute(text(f"""
            SELECT s.id AS session_id,
                   v.visitor_key,
                   v.subject,
                   v.display_name,
                   v.role,
                   v.site,
                   s.started_at,
                   s.ended_at,
                   COUNT(i.id)::bigint AS response_count,
                   COUNT(i.id) FILTER (WHERE i.processing_status = 'COMPLETED')::bigint AS completed_count,
                   COUNT(i.id) FILTER (WHERE i.processing_status = 'FAILED')::bigint AS failed_count,
                   COUNT(i.id) FILTER (WHERE i.answer_type = 'FAQ')::bigint AS faq_count,
                   COUNT(i.id) FILTER (WHERE i.answer_type = 'GENERATED_AI')::bigint AS generated_ai_count,
                   COUNT(i.id) FILTER (WHERE i.answer_type = 'NO_ANSWER')::bigint AS no_answer_count,
                   COUNT(f.interaction_id) FILTER (WHERE f.rating = 'GOOD')::bigint AS good_count,
                   COUNT(f.interaction_id) FILTER (WHERE f.rating = 'BAD')::bigint AS bad_count
            FROM chat_sessions s
            JOIN analytics_visitors v ON v.id = s.visitor_id
            LEFT JOIN chat_interactions i ON i.chat_session_id = s.id
            LEFT JOIN chat_feedback f ON f.interaction_id = i.id
            WHERE s.started_at >= :start_at AND s.started_at < :end_at {filters}
            GROUP BY s.id, v.visitor_key, v.subject, v.display_name, v.role, v.site,
                     s.started_at, s.ended_at
            ORDER BY s.started_at DESC, s.id DESC
            LIMIT :limit OFFSET :offset
        """), parameters)).mappings().all()
        return int(total), [dict(row) for row in rows]

    async def chat_history_export(self, start_at: datetime, end_at: datetime, *, visitor_key: str | None = None, answer_type: str | None = None, rating: str | None = None, comment: str | None = None, role: str | None = None, user_ids: list[str] | None = None) -> list[dict]:
        filters = ["i.question_submitted_at >= :start_at", "i.question_submitted_at < :end_at", "i.processing_status = 'COMPLETED'"]
        params: dict = {"start_at": start_at, "end_at": end_at, "visitor_key": visitor_key, "answer_type": answer_type, "rating": rating, "role": role, "user_ids": user_ids}
        if visitor_key: filters.append("v.visitor_key = :visitor_key")
        if answer_type: filters.append("i.answer_type = :answer_type")
        if rating == "RATED": filters.append("f.rating IS NOT NULL")
        elif rating == "NONE": filters.append("f.rating IS NULL")
        elif rating: filters.append("f.rating = :rating")
        if comment == "WITH": filters.append("NULLIF(BTRIM(f.comment), '') IS NOT NULL")
        elif comment == "WITHOUT": filters.append("NULLIF(BTRIM(f.comment), '') IS NULL")
        if role: filters.append("v.role = :role")
        if user_ids: filters.append("v.subject = ANY(:user_ids)")
        rows = (await self.session.execute(text(f"""
            SELECT s.id AS session_id, i.sequence_number, v.subject, v.display_name, v.role, v.site,
                   i.question_submitted_at, i.answer_displayed_at, i.answer_type,
                   i.question_text, i.answer_text, f.rating, f.comment
            FROM chat_interactions i
            JOIN chat_sessions s ON s.id = i.chat_session_id
            JOIN analytics_visitors v ON v.id = s.visitor_id
            LEFT JOIN chat_feedback f ON f.interaction_id = i.id
            WHERE {' AND '.join(filters)}
            ORDER BY i.question_submitted_at DESC, s.id DESC, i.sequence_number
        """), params)).mappings().all()
        return [dict(row) for row in rows]

    async def usage_users(self, start_at: datetime, end_at: datetime, *, role: str | None = None) -> list[dict]:
        role_filter = "AND v.role = :role" if role else ""
        rows = (await self.session.execute(text(f"""
            SELECT v.visitor_key, v.identity_kind, v.subject, v.display_name, v.role, v.site,
                   v.created_at, v.last_seen_at,
                   COUNT(DISTINCT a.id)::bigint AS access_count,
                   COUNT(DISTINCT s.id)::bigint AS chat_count
            FROM analytics_visitors v
            LEFT JOIN access_logs a ON a.visitor_id = v.id AND a.accessed_at >= :start_at AND a.accessed_at < :end_at
            LEFT JOIN chat_sessions s ON s.visitor_id = v.id AND s.started_at >= :start_at AND s.started_at < :end_at
            WHERE (a.id IS NOT NULL OR s.id IS NOT NULL) {role_filter}
            GROUP BY v.id, v.visitor_key, v.identity_kind, v.subject, v.display_name, v.role, v.site,
                     v.created_at, v.last_seen_at
            ORDER BY v.last_seen_at DESC
        """), {"start_at": start_at, "end_at": end_at, "role": role})).mappings().all()
        return [dict(row) for row in rows]

    async def access_logs(self, start_at: datetime, end_at: datetime, *, surface: str | None = None, role: str | None = None, user_ids: list[str] | None = None) -> list[dict]:
        filters = []
        parameters: dict = {"start_at": start_at, "end_at": end_at, "surface": surface, "role": role, "user_ids": user_ids}
        if surface:
            filters.append("a.surface = :surface")
        if role:
            filters.append("v.role = :role")
        if user_ids:
            filters.append("v.subject = ANY(:user_ids)")
        where_extra = " AND " + " AND ".join(filters) if filters else ""
        rows = (await self.session.execute(text(f"""
            SELECT a.id, v.visitor_key, v.identity_kind, v.subject, v.display_name, v.role, v.site,
                   a.surface, a.accessed_at, a.recorded_at
            FROM access_logs a
            JOIN analytics_visitors v ON v.id = a.visitor_id
            WHERE a.accessed_at >= :start_at AND a.accessed_at < :end_at {where_extra}
            ORDER BY a.accessed_at DESC, a.id DESC
        """), parameters)).mappings().all()
        return [dict(row) for row in rows]

    async def operation_logs(self, start_at: datetime, end_at: datetime, *, role: str | None = None, user_ids: list[str] | None = None) -> list[dict]:
        filters = []
        parameters: dict = {"start_at": start_at, "end_at": end_at, "role": role, "user_ids": user_ids}
        if role:
            filters.append("operator_role = :role")
        if user_ids:
            filters.append("operator_subject = ANY(:user_ids)")
        where_extra = " AND " + " AND ".join(filters) if filters else ""
        rows = (await self.session.execute(text(f"""
            SELECT id, operator_key, operator_subject, operator_display_name, operator_role,
                   operator_site, http_method, request_path, status_code, operated_at
            FROM admin_operation_logs
            WHERE operated_at >= :start_at AND operated_at < :end_at {where_extra}
            ORDER BY operated_at DESC, id DESC
        """), parameters)).mappings().all()
        return [dict(row) for row in rows]
