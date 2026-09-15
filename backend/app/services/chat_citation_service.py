from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.data_source import DataSource
from app.schemas.chat import ChatCitation


def web_uri(uri: str | None) -> str | None:
    parsed = urlparse(uri or "")
    return uri if parsed.scheme in {"http", "https"} and parsed.netloc else None


async def resolve_chat_citations(session, citations: list[ChatCitation]) -> list[ChatCitation]:
    """Use current management settings and original files for actual cited sources."""
    ids = {citation.data_source_id for citation in citations if citation.data_source_id}
    rows = []
    if ids:
        rows = (await session.execute(
            select(DataSource).where(DataSource.id.in_(ids))
            .options(selectinload(DataSource.file), selectinload(DataSource.website))
        )).scalars().all()
    by_id = {row.id: row for row in rows}
    resolved = []
    seen = set()
    for citation in citations:
        if citation.data_source_id:
            row = by_id.get(citation.data_source_id)
            if row is None or not row.reference_link_visible or not row.answer_source_enabled:
                continue
            if row.source_type == "FILE" and row.file and row.file.storage_key:
                uri = f"/api/v1/chat/sources/{row.id}/download"
            elif row.source_type == "WEB" and row.website:
                uri = web_uri(citation.uri) or web_uri(row.website.url)
            else:
                uri = None
            citation = citation.model_copy(update={"title": row.title, "uri": uri})
        else:
            citation = citation.model_copy(update={"uri": web_uri(citation.uri)})
        key = (citation.data_source_id or citation.title, citation.uri)
        if key not in seen:
            seen.add(key)
            resolved.append(citation)
    return resolved
