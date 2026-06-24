from sqlalchemy import text

from app.db.session import SessionLocal


def search_federal_law(
    query: str,
    limit: int = 8,
    expanded_queries: list[str] | None = None,
) -> list[dict]:
    query = (query or "").strip()

    if not query:
        return []

    limit = max(1, min(int(limit), 12))

    queries = _build_query_list(query, expanded_queries)
    collected = {}

    for index, search_query in enumerate(queries):
        query_weight = 1.0 - min(index * 0.08, 0.35)

        for item in _search_by_document_metadata(search_query, limit=10):
            _merge_result(collected, item, query_weight)

        if len(collected) >= limit:
            break

    if len(collected) < limit:
        for index, search_query in enumerate(queries[:3]):
            query_weight = 1.0 - min(index * 0.08, 0.35)

            try:
                chunk_results = _search_by_chunk_fts(search_query, limit=12)
            except Exception:
                chunk_results = []

            for item in chunk_results:
                _merge_result(collected, item, query_weight)

            if len(collected) >= limit:
                break

    results = list(collected.values())

    results.sort(
        key=lambda item: (
            float(item.get("rank") or 0),
            bool(item.get("is_widely_used")),
        ),
        reverse=True,
    )

    return results[:limit]


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
Способ поиска: {item.get("search_method") or "fts"}
Ранг поиска: {round(float(item.get("rank") or 0), 4)}

Фрагмент:
{item.get("content")}
""".strip())

    return "\n\n---\n\n".join(blocks)


def _search_by_document_metadata(query: str, limit: int) -> list[dict]:
    query = _prepare_search_query(query)

    if not query:
        return []

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '9000ms'"))

        rows = session.execute(text("""
            WITH search_query AS (
                SELECT websearch_to_tsquery('russian', :query) AS query
            ),
            matched_documents AS (
                SELECT
                    fld.id,
                    ts_rank_cd(fld.search_vector, search_query.query, 32) AS document_rank
                FROM federal_law_documents fld
                CROSS JOIN search_query
                WHERE
                    search_query.query <> ''::tsquery
                    AND fld.search_vector @@ search_query.query
                ORDER BY
                    document_rank DESC,
                    fld.is_widely_used DESC,
                    fld.id DESC
                LIMIT :limit
            )
            SELECT
                flc.id AS chunk_id,
                left(flc.content, 2600) AS content,
                fld.title,
                fld.document_type,
                fld.authority,
                fld.document_number,
                fld.document_date,
                fld.status,
                fld.is_widely_used,
                fld.source,
                fld.source_url,
                'document_metadata' AS search_method,
                (
                    matched_documents.document_rank
                    + CASE WHEN fld.is_widely_used THEN 0.20 ELSE 0 END
                    + 0.15
                ) AS rank
            FROM matched_documents
            JOIN federal_law_documents fld ON fld.id = matched_documents.id
            JOIN federal_law_chunks flc ON flc.document_id = fld.id
            WHERE flc.chunk_index = 0
            ORDER BY rank DESC
        """), {
            "query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _search_by_chunk_fts(query: str, limit: int) -> list[dict]:
    query = _prepare_search_query(query)

    if not query:
        return []

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '4000ms'"))

        rows = session.execute(text("""
            WITH search_query AS (
                SELECT websearch_to_tsquery('russian', :query) AS query
            )
            SELECT
                flc.id AS chunk_id,
                left(flc.content, 2600) AS content,
                fld.title,
                fld.document_type,
                fld.authority,
                fld.document_number,
                fld.document_date,
                fld.status,
                fld.is_widely_used,
                fld.source,
                fld.source_url,
                'chunk_fts' AS search_method,
                (
                    ts_rank_cd(flc.search_vector, search_query.query, 32)
                    + CASE WHEN fld.is_widely_used THEN 0.12 ELSE 0 END
                ) AS rank
            FROM federal_law_chunks flc
            JOIN federal_law_documents fld ON fld.id = flc.document_id
            CROSS JOIN search_query
            WHERE
                search_query.query <> ''::tsquery
                AND flc.search_vector @@ search_query.query
            ORDER BY
                rank DESC,
                fld.is_widely_used DESC,
                flc.id DESC
            LIMIT :limit
        """), {
            "query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _merge_result(collected: dict, item: dict, query_weight: float) -> None:
    chunk_id = item.get("chunk_id")
    document_key = item.get("source_url") or item.get("title") or chunk_id

    if not document_key:
        return

    item = dict(item)
    item["rank"] = float(item.get("rank") or 0) * query_weight

    existing = collected.get(document_key)

    if not existing or item["rank"] > float(existing.get("rank") or 0):
        collected[document_key] = item


def _build_query_list(query: str, expanded_queries: list[str] | None) -> list[str]:
    queries = [query]

    if expanded_queries:
        queries.extend(expanded_queries)

    unique = []

    for item in queries:
        cleaned = _prepare_search_query(item)

        if cleaned and cleaned not in unique:
            unique.append(cleaned)

    return unique[:6]


def _prepare_search_query(query: str) -> str:
    cleaned = " ".join((query or "").replace("\n", " ").split())
    return cleaned[:500]