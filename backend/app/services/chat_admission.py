"""Cross-process admission: PostgreSQL transaction locks and a rolling minute."""
from contextlib import asynccontextmanager
import hashlib
import math

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.analytics import ChatRequestLimit
from app.services.resource_limits import positive_setting


def lock_key(visitor_key, slot):
    return int.from_bytes(hashlib.sha256(f"chat-admission:{visitor_key}:{slot}".encode()).digest()[:8], "big", signed=True)


async def record_request(engine, visitor_key, maximum):
    # Separate short transaction: timestamps survive generation errors/restarts.
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(insert(ChatRequestLimit).values(visitor_key=visitor_key, accepted_at=[])
                              .on_conflict_do_nothing(index_elements=["visitor_key"]))
        row = (await session.execute(select(ChatRequestLimit).where(
            ChatRequestLimit.visitor_key == visitor_key).with_for_update())).scalar_one()
        now = float(await session.scalar(text("SELECT extract(epoch FROM clock_timestamp())")))
        recent = [stamp for stamp in row.accepted_at if stamp > now - 60]
        if len(recent) >= maximum:
            seconds = max(1, math.ceil(min(recent) + 60 - now))
            raise HTTPException(429, f"質問は1分間に{maximum}回まで送信できます。{seconds}秒ほど待ってから、もう一度送信してください。",
                                headers={"Retry-After": str(seconds)})
        row.accepted_at = recent + [now]


@asynccontextmanager
async def admit_chat(engine, visitor_key):
    concurrent = positive_setting("CHAT_MAX_CONCURRENT_REQUESTS", 1)
    per_minute = positive_setting("CHAT_REQUESTS_PER_MINUTE", 10)
    # A transaction-scoped lock is released on success, exception, cancellation,
    # or disconnected worker. It cannot leak into a pooled connection.
    # Keep the long-lived advisory lock outside the application's query pool.
    # Otherwise parallel guards can occupy every pooled connection while each
    # waits for a second connection to record the rate window or answer.
    guard_engine = create_async_engine(engine.url, poolclass=NullPool)
    try:
        async with AsyncSession(guard_engine) as guard, guard.begin():
            for slot in range(concurrent):
                if await guard.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"),
                                      {"key": lock_key(visitor_key, slot)}):
                    break
            else:
                raise HTTPException(429, f"同時に回答を待てる質問は{concurrent}件までです。他のタブを含め、回答が完了してからもう一度送信してください。")
            await record_request(guard_engine, visitor_key, per_minute)
            yield
    finally:
        await guard_engine.dispose()
