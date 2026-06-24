from sqlalchemy import text

from app.db.session import SessionLocal


def search_federal_law(query: str, limit: int = 8) -> list[dict]:
    query = (query or "").strip()

    if not query:
        return []

    limit = max(1, min(int(limit), 12))

    prepared_query = _prepare_search_query(query)
    results = _search_by_fts(prepared_query, limit)

    if results:
        return results

    title_results = _search_by_title(query, limit)

    if title_results:
        return title_results

    fallback_query = _build_fallback_words(query)
    fallback_results = _search_by_ilike(fallback_query, limit)

    return fallback_results


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


def _search_by_fts(query: str, limit: int) -> list[dict]:
    if not query:
        return []

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '9000ms'"))

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
                'fts' AS search_method,
                (
                    ts_rank_cd(
                        to_tsvector(
                            'russian',
                            coalesce(flc.title, '') || ' ' || coalesce(flc.content, '')
                        ),
                        search_query.query,
                        32
                    )
                    + CASE WHEN fld.is_widely_used THEN 0.12 ELSE 0 END
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
            "query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _search_by_title(query: str, limit: int) -> list[dict]:
    words = _build_fallback_words(query)

    if not words:
        return []

    conditions = []
    params = {"limit": limit}

    for index, word in enumerate(words[:6]):
        key = f"word_{index}"
        conditions.append(f"""
            fld.title ILIKE :{key}
            OR fld.document_type ILIKE :{key}
            OR fld.document_number ILIKE :{key}
            OR fld.authority ILIKE :{key}
        """)
        params[key] = f"%{word}%"

    where_sql = " OR ".join(f"({condition})" for condition in conditions)

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '9000ms'"))

        rows = session.execute(text(f"""
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
                'title_fallback' AS search_method,
                (
                    CASE WHEN fld.is_widely_used THEN 0.25 ELSE 0 END
                    + 0.10
                ) AS rank
            FROM federal_law_documents fld
            JOIN federal_law_chunks flc ON flc.document_id = fld.id
            WHERE {where_sql}
            ORDER BY
                fld.is_widely_used DESC,
                fld.id DESC,
                flc.chunk_index ASC
            LIMIT :limit
        """), params).mappings().fetchall()

    return [dict(row) for row in rows]


def _search_by_ilike(words: list[str], limit: int) -> list[dict]:
    if not words:
        return []

    conditions = []
    params = {"limit": limit}

    for index, word in enumerate(words[:6]):
        key = f"word_{index}"
        conditions.append(f"""
            flc.content ILIKE :{key}
            OR flc.title ILIKE :{key}
            OR fld.title ILIKE :{key}
        """)
        params[key] = f"%{word}%"

    where_sql = " OR ".join(f"({condition})" for condition in conditions)

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '9000ms'"))

        rows = session.execute(text(f"""
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
                'ilike_fallback' AS search_method,
                (
                    CASE WHEN fld.is_widely_used THEN 0.18 ELSE 0 END
                    + 0.05
                ) AS rank
            FROM federal_law_chunks flc
            JOIN federal_law_documents fld ON fld.id = flc.document_id
            WHERE {where_sql}
            ORDER BY
                fld.is_widely_used DESC,
                flc.id DESC
            LIMIT :limit
        """), params).mappings().fetchall()

    return [dict(row) for row in rows]


def _prepare_search_query(query: str) -> str:
    cleaned = " ".join(query.replace("\n", " ").split())
    return cleaned[:500]


def _build_fallback_words(query: str) -> list[str]:
    stop_words = {
        "какие", "какой", "какая", "какое", "есть", "для", "при", "или",
        "что", "как", "может", "можно", "нужно", "надо", "если", "это",
        "этот", "эта", "эти", "который", "которая", "которые", "между",
        "после", "перед", "время", "процедуры", "порядок", "основания",
        "по", "на", "об", "о", "в", "с", "и", "а", "во", "со",
    }

    synonyms = {
        "банкротства": ["банкротств", "несостоятельности"],
        "банкротстве": ["банкротств", "несостоятельности"],
        "финансовый": ["финансов", "арбитражн"],
        "финансового": ["финансов", "арбитражн"],
        "управляющий": ["управляющ"],
        "управляющего": ["управляющ"],
        "расходы": ["расход"],
        "расходов": ["расход"],
        "контролировать": ["контрол", "провер"],
        "сделок": ["сделк"],
        "сделки": ["сделк"],
        "оспаривание": ["оспарив"],
        "оспариванию": ["оспарив"],
        "кассационное": ["кассац"],
        "кассационного": ["кассац"],
    }

    words = []

    for raw_word in query.lower().replace("?", " ").replace(",", " ").split():
        word = raw_word.strip(" .:;!()[]{}\"'«»")

        if len(word) < 4:
            continue

        if word in stop_words:
            continue

        words.append(word)

        for synonym in synonyms.get(word, []):
            words.append(synonym)

    unique_words = []

    for word in words:
        if word not in unique_words:
            unique_words.append(word)

    return unique_words[:10]