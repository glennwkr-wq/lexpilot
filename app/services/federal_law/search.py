from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.federal_law.schema import ensure_federal_law_tables


def search_federal_law(query: str, limit: int = 8) -> list[dict]:
    query = (query or "").strip()

    if not query:
        return []

    ensure_federal_law_tables()

    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT
                flc.id AS chunk_id,
                flc.content,
                fld.title,
                fld.document_type,
                fld.authority,
                fld.document_number,
                fld.document_date,
                fld.status,
                fld.source,
                fld.source_url,
                ts_rank(
                    to_tsvector('russian', coalesce(flc.title, '') || ' ' || coalesce(flc.content, '')),
                    plainto_tsquery('russian', :query)
                ) AS rank
            FROM federal_law_chunks flc
            JOIN federal_law_documents fld ON fld.id = flc.document_id
            WHERE
                to_tsvector('russian', coalesce(flc.title, '') || ' ' || coalesce(flc.content, ''))
                @@ plainto_tsquery('russian', :query)
            ORDER BY
                fld.is_widely_used DESC,
                rank DESC,
                flc.id DESC
            LIMIT :limit
        """), {
            "query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def build_federal_law_context(results: list[dict]) -> str:
    if not results:
        return ""

    blocks = []

    for index, item in enumerate(results, start=1):
        blocks.append(f"""
[Федеральный источник {index}]
Название: {item.get("title")}
Тип: {item.get("document_type") or "Не указан"}
Орган: {item.get("authority") or "Не указан"}
Дата: {item.get("document_date") or "Не указана"}
Номер: {item.get("document_number") or "Не указан"}
Статус в корпусе: {item.get("status") or "Не указан"}
Источник: {item.get("source_url")}

Фрагмент:
{item.get("content")}
""".strip())

    return "\n\n---\n\n".join(blocks)