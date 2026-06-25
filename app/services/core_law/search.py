from sqlalchemy import text

from app.db.session import SessionLocal


def search_core_law(
    query: str,
    limit: int = 8,
    expanded_queries: list[str] | None = None,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    query = (query or "").strip()

    if not query:
        return []

    limit = max(1, min(int(limit), 30))
    queries = _build_query_list(query, expanded_queries)

    collected = {}

    if query_embedding:
        for item in _search_core_articles_vector(
            query_embedding=query_embedding,
            limit=max(limit * 3, 20),
        ):
            _merge_article(collected, item)

    for index, item_query in enumerate(queries):
        query_weight = 1.0 - min(index * 0.08, 0.35)

        for item in _search_core_articles_fts(item_query, limit=max(limit * 3, 20)):
            item = dict(item)
            item["rank"] = float(item.get("rank") or 0) * query_weight
            _merge_article(collected, item)

    results = list(collected.values())
    results.sort(key=lambda item: float(item.get("rank") or 0), reverse=True)

    return results[:limit]


def build_core_law_context(results: list[dict]) -> str:
    if not results:
        return ""

    blocks = []

    for index, item in enumerate(results, start=1):
        blocks.append(f"""
[Статья кодекса {index}]
Кодекс: {item.get("codex")}
Статья: {item.get("article_num")}
Название статьи: {item.get("article_title") or "Не указано"}
Глава / раздел: {item.get("chapter") or "Не указано"}
Источник: {item.get("source_url") or item.get("url") or "Не указан"}
Способ поиска: {item.get("search_method") or "core_law_search"}
Ранг поиска: {round(float(item.get("rank") or 0), 4)}

Текст статьи:
{(item.get("content") or "")[:1800]}
""".strip())

    return "\n\n---\n\n".join(blocks)


def is_core_law_sufficient(results: list[dict]) -> bool:
    if not results:
        return False

    top_rank = float(results[0].get("rank") or 0)

    if top_rank >= 0.55:
        return True

    if len(results) >= 3 and top_rank >= 0.35:
        return True

    return False


def _search_core_articles_vector(
    query_embedding: list[float],
    limit: int,
) -> list[dict]:
    if not query_embedding:
        return []

    embedding_text = _format_embedding(query_embedding)

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '7000ms'"))

        rows = session.execute(text("""
            SELECT
                cla.id AS article_id,
                cla.codex,
                cla.codex_id,
                cla.chapter,
                cla.article_num,
                cla.article_title,
                cla.content,
                cla.url,
                cla.url AS source_url,
                'Статья кодекса' AS document_type,
                cla.codex AS title,
                NULL AS authority,
                cla.article_num AS document_number,
                NULL AS document_date,
                'Актуальность требует проверки по официальному источнику' AS status,
                'core_law_vector' AS search_method,
                (
                    1 - (cla.embedding <=> CAST(:embedding AS vector))
                ) AS rank
            FROM core_law_articles cla
            WHERE cla.embedding IS NOT NULL
            ORDER BY cla.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """), {
            "embedding": embedding_text,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _search_core_articles_fts(query: str, limit: int) -> list[dict]:
    query = _prepare_search_query(query)

    if not query:
        return []

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '5000ms'"))

        rows = session.execute(text("""
            WITH search_query AS (
                SELECT websearch_to_tsquery('russian', :query) AS query
            )
            SELECT
                cla.id AS article_id,
                cla.codex,
                cla.codex_id,
                cla.chapter,
                cla.article_num,
                cla.article_title,
                cla.content,
                cla.url,
                cla.url AS source_url,
                'Статья кодекса' AS document_type,
                cla.codex AS title,
                NULL AS authority,
                cla.article_num AS document_number,
                NULL AS document_date,
                'Актуальность требует проверки по официальному источнику' AS status,
                'core_law_fts' AS search_method,
                (
                    ts_rank_cd(cla.search_vector, search_query.query, 32) * 12.0
                    + CASE
                        WHEN cla.article_title ILIKE '%' || :plain_query || '%' THEN 4.0
                        ELSE 0
                      END
                    + CASE
                        WHEN cla.codex ILIKE '%' || :plain_query || '%' THEN 2.0
                        ELSE 0
                      END
                    + CASE
                        WHEN ('статья ' || cla.article_num) ILIKE '%' || :plain_query || '%' THEN 3.0
                        ELSE 0
                      END
                    + CASE
                        WHEN cla.content ILIKE '%' || :plain_query || '%' THEN 0.8
                        ELSE 0
                      END
                ) AS rank
            FROM core_law_articles cla
            CROSS JOIN search_query
            WHERE
                search_query.query <> ''::tsquery
                AND cla.search_vector @@ search_query.query
            ORDER BY rank DESC, cla.id ASC
            LIMIT :limit
        """), {
            "query": query,
            "plain_query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _merge_article(collected: dict, item: dict) -> None:
    key = f"{item.get('codex_id')}:{item.get('article_num')}"

    item = dict(item)

    if item.get("search_method") == "core_law_vector":
        item["rank"] = float(item.get("rank") or 0)
    else:
        item["rank"] = min(float(item.get("rank") or 0) / 10.0, 0.95)

    existing = collected.get(key)

    if not existing or float(item.get("rank") or 0) > float(existing.get("rank") or 0):
        collected[key] = item


def _build_query_list(query: str, expanded_queries: list[str] | None) -> list[str]:
    queries = [query]

    if expanded_queries:
        queries.extend(expanded_queries)

    unique = []

    for item in queries:
        cleaned = _prepare_search_query(item)

        if cleaned and cleaned not in unique:
            unique.append(cleaned)

    return unique[:8]


def _prepare_search_query(query: str) -> str:
    return " ".join((query or "").replace("\n", " ").split())[:500]


def _format_embedding(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"