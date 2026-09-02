from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AuthSession, CpfUsedJti
from app.services.auth_token import session_token_hash


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session_once(
        self, *, jti: UUID, jwt_expire_at: datetime, session: AuthSession
    ) -> bool:
        now = datetime.now(jwt_expire_at.tzinfo)
        await self.session.execute(delete(CpfUsedJti).where(CpfUsedJti.expire_at < now))
        result = await self.session.execute(
            insert(CpfUsedJti)
            .values(jti=jti, expire_at=jwt_expire_at, consumed_at=now)
            .on_conflict_do_nothing(index_elements=[CpfUsedJti.jti])
            .returning(CpfUsedJti.jti)
        )
        if result.scalar_one_or_none() is None:
            await self.session.rollback()
            return False
        self.session.add(session)
        await self.session.commit()
        return True

    async def get_session(self, token_hash: str, now: datetime) -> AuthSession | None:
        row = (await self.session.execute(
            select(AuthSession).where(AuthSession.token_hash == token_hash)
        )).scalar_one_or_none()
        if row is None:
            return None
        if row.expire_at <= now:
            await self.session.delete(row)
            await self.session.commit()
            return None
        row.last_seen_at = now
        await self.session.commit()
        return row

    async def get_session_row(self, raw_session_token: str) -> AuthSession | None:
        return await self.get_session(
            session_token_hash(raw_session_token), datetime.now(timezone.utc)
        )

    async def delete_session(self, token_hash: str) -> None:
        await self.session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))
        await self.session.commit()
