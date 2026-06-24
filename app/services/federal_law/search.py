from sqlalchemy import text

from app.db.session import SessionLocal


def search_federal_law(query: str, limit: int = 8) -> list[dict]:
    query = (query or "").strip()

    if not query:
        return []

    limit = max(1, min(int(limit), 12))

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '8000ms'"))

        rows = session.execute(text("""
            WITH search_query AS (
                SELECT websearch_to_tsquery('russian', :query) AS query
            )
            SELECT
                flc.id AS chunk_id,
                flc.content,
                fld.title,
                fld.document_type,
                fld.authority,
                fld.document_number,
                fld.document_date,
                fld.status,
                fld.is_widely_used,
                fld.source,
                fld.source_url,
                (
                    ts_rank_cd(
                        to_tsvector(
                            'russian',
                            coalesce(flc.title, '') || ' ' || coalesce(flc.content, '')
                        ),
                        search_query.query,
                        32
                    )
                    + CASE WHEN fld.is_widely_used THEN 0.08 ELSE 0 END
                ) AS rank
            FROM federal_law_chunks flc
            JOIN federal_law_documents fld ON fld.id = flc.document_id
            CROSS JOIN search_query
            WHERE
                search_query.query <> ''::tsquery
                AND to_tsvector(
                    'russian',
                    coalesce(flc.title, '') || ' ' || coalesce(flc.content, '')
                ) @@ search_query.query
            ORDER BY
                rank DESC,
                fld.is_widely_used DESC,
                flc.id DESC
            LIMIT :limit
        """), {
            "query": _prepare_search_query(query),
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
Ранг поиска: {round(float(item.get("rank") or 0), 4)}

Фрагмент:
{item.get("content")}
""".strip())

    return "\n\n---\n\n".join(blocks)


def _prepare_search_query(query: str) -> str:
    cleaned = " ".join(query.replace("\n", " ").split())

    if len(cleaned) > 500:
        cleaned = cleaned[:500]

    return cleaned