from sqlalchemy import text

from app.db.session import SessionLocal


def search_federal_law(
    query: str,
    limit: int = 8,
    expanded_queries: list[str] | None = None,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    query = (query or "").strip()

    if not query:
        return []

    limit = max(1, min(int(limit), 40))
    queries = _build_query_list(query, expanded_queries)

    document_candidates = _collect_document_candidates(queries, limit=80)
    collected = {}

    if document_candidates:
        for item in _search_chunks_inside_documents(
            queries=queries,
            document_candidates=document_candidates,
            limit=80,
        ):
            _merge_result(collected, item)

    if query_embedding:
        for item in _search_vector_chunks(
            query_embedding=query_embedding,
            document_candidates=document_candidates,
            limit=80,
        ):
            _merge_result(collected, item)

    if len(collected) < limit:
        for item in _fallback_global_chunk_search(queries[:3], limit=40):
            _merge_result(collected, item)

    results = []

    for item in collected.values():
        item = dict(item)
        item["rank"] = _apply_query_aware_rank(
            user_query=query,
            item=item,
            current_rank=float(item.get("rank") or 0),
        )
        results.append(item)

    results.sort(key=lambda item: float(item.get("rank") or 0), reverse=True)

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


def _collect_document_candidates(queries: list[str], limit: int = 80) -> list[dict]:
    collected = {}

    for index, query in enumerate(queries):
        query_weight = 1.0 - min(index * 0.06, 0.30)

        for item in _search_documents(query, limit=limit):
            document_id = item.get("document_id")

            if not document_id:
                continue

            item = dict(item)
            item["rank"] = float(item.get("rank") or 0) * query_weight

            existing = collected.get(document_id)

            if not existing or item["rank"] > float(existing.get("rank") or 0):
                collected[document_id] = item

    results = list(collected.values())
    results.sort(key=lambda item: float(item.get("rank") or 0), reverse=True)

    return results[:limit]


def _search_documents(query: str, limit: int) -> list[dict]:
    query = _prepare_search_query(query)

    if not query:
        return []

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '6000ms'"))

        rows = session.execute(text("""
            WITH search_query AS (
                SELECT websearch_to_tsquery('russian', :query) AS query
            )
            SELECT
                fld.id AS document_id,
                fld.title,
                fld.document_type,
                fld.authority,
                fld.document_number,
                fld.document_date,
                fld.status,
                fld.is_widely_used,
                fld.is_base_law,
                fld.is_change_law,
                fld.is_project_law,
                fld.legal_rank,
                fld.source,
                fld.source_url,
                'document_fts' AS search_method,
                (
                    ts_rank_cd(fld.search_vector, search_query.query, 32)
                    + fld.legal_rank
                    + CASE
                        WHEN lower(fld.title) = lower(:plain_query) THEN 4.00
                        WHEN fld.title ILIKE '%' || :plain_query || '%' THEN 2.50
                        ELSE 0
                      END
                    - LEAST(length(fld.title)::float / 8000.0, 0.40)
                    + CASE WHEN fld.is_base_law THEN 0.80 ELSE 0 END
                    - CASE WHEN fld.is_change_law THEN 1.50 ELSE 0 END
                    - CASE WHEN fld.is_project_law THEN 2.50 ELSE 0 END
                ) AS rank
            FROM federal_law_documents fld
            CROSS JOIN search_query
            WHERE
                search_query.query <> ''::tsquery
                AND fld.search_vector @@ search_query.query
            ORDER BY rank DESC, fld.id DESC
            LIMIT :limit
        """), {
            "query": query,
            "plain_query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _search_chunks_inside_documents(
    queries: list[str],
    document_candidates: list[dict],
    limit: int,
) -> list[dict]:
    document_ids = [
        int(item["document_id"])
        for item in document_candidates
        if item.get("document_id")
    ]

    if not document_ids:
        return []

    document_rank_map = {
        int(item["document_id"]): float(item.get("rank") or 0)
        for item in document_candidates
        if item.get("document_id")
    }

    collected = {}

    for index, query in enumerate(queries[:4]):
        query_weight = 1.0 - min(index * 0.06, 0.30)

        try:
            chunk_rows = _search_chunks_by_document_ids(
                query=query,
                document_ids=document_ids,
                limit=max(limit, 40),
            )
        except Exception:
            chunk_rows = []

        for item in chunk_rows:
            document_id = int(item.get("document_id") or 0)
            base_document_rank = document_rank_map.get(document_id, 0)

            item = dict(item)
            item["rank"] = (
                base_document_rank * 0.75
                + float(item.get("chunk_rank") or 0) * 1.25
                + float(item.get("legal_rank") or 0) * 0.35
            ) * query_weight

            _merge_result(collected, item)

    results = list(collected.values())
    results.sort(key=lambda item: float(item.get("rank") or 0), reverse=True)

    return results[:limit]


def _search_chunks_by_document_ids(
    query: str,
    document_ids: list[int],
    limit: int,
) -> list[dict]:
    query = _prepare_search_query(query)

    if not query or not document_ids:
        return []

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '6000ms'"))

        rows = session.execute(text("""
            WITH search_query AS (
                SELECT websearch_to_tsquery('russian', :query) AS query
            )
            SELECT
                flc.id AS chunk_id,
                flc.document_id,
                left(flc.content, 2600) AS content,
                fld.title,
                fld.document_type,
                fld.authority,
                fld.document_number,
                fld.document_date,
                fld.status,
                fld.is_widely_used,
                fld.is_base_law,
                fld.is_change_law,
                fld.is_project_law,
                fld.legal_rank,
                fld.source,
                fld.source_url,
                'document_then_chunk_fts' AS search_method,
                ts_rank_cd(flc.search_vector, search_query.query, 32) AS chunk_rank
            FROM federal_law_chunks flc
            JOIN federal_law_documents fld ON fld.id = flc.document_id
            CROSS JOIN search_query
            WHERE
                flc.document_id = ANY(:document_ids)
                AND search_query.query <> ''::tsquery
                AND flc.search_vector @@ search_query.query
            ORDER BY
                chunk_rank DESC,
                fld.legal_rank DESC,
                flc.chunk_index ASC
            LIMIT :limit
        """), {
            "query": query,
            "document_ids": document_ids,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _search_vector_chunks(
    query_embedding: list[float],
    document_candidates: list[dict],
    limit: int,
) -> list[dict]:
    if not query_embedding:
        return []

    document_ids = [
        int(item["document_id"])
        for item in document_candidates
        if item.get("document_id")
    ]

    embedding_text = _format_embedding(query_embedding)

    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '7000ms'"))

        if document_ids:
            rows = session.execute(text("""
                SELECT
                    flc.id AS chunk_id,
                    flc.document_id,
                    left(flc.content, 2600) AS content,
                    fld.title,
                    fld.document_type,
                    fld.authority,
                    fld.document_number,
                    fld.document_date,
                    fld.status,
                    fld.is_widely_used,
                    fld.is_base_law,
                    fld.is_change_law,
                    fld.is_project_law,
                    fld.legal_rank,
                    fld.source,
                    fld.source_url,
                    'vector_inside_documents' AS search_method,
                    (
                        (1 - (flc.embedding <=> CAST(:embedding AS vector))) * 2.00
                        + fld.legal_rank * 0.35
                    ) AS rank
                FROM federal_law_chunks flc
                JOIN federal_law_documents fld ON fld.id = flc.document_id
                WHERE
                    flc.embedding IS NOT NULL
                    AND flc.document_id = ANY(:document_ids)
                ORDER BY flc.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """), {
                "embedding": embedding_text,
                "document_ids": document_ids,
                "limit": limit,
            }).mappings().fetchall()
        else:
            rows = session.execute(text("""
                SELECT
                    flc.id AS chunk_id,
                    flc.document_id,
                    left(flc.content, 2600) AS content,
                    fld.title,
                    fld.document_type,
                    fld.authority,
                    fld.document_number,
                    fld.document_date,
                    fld.status,
                    fld.is_widely_used,
                    fld.is_base_law,
                    fld.is_change_law,
                    fld.is_project_law,
                    fld.legal_rank,
                    fld.source,
                    fld.source_url,
                    'vector_global' AS search_method,
                    (
                        (1 - (flc.embedding <=> CAST(:embedding AS vector))) * 2.00
                        + fld.legal_rank * 0.35
                    ) AS rank
                FROM federal_law_chunks flc
                JOIN federal_law_documents fld ON fld.id = flc.document_id
                WHERE flc.embedding IS NOT NULL
                ORDER BY flc.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """), {
                "embedding": embedding_text,
                "limit": limit,
            }).mappings().fetchall()

    return [dict(row) for row in rows]


def _fallback_global_chunk_search(queries: list[str], limit: int) -> list[dict]:
    collected = {}

    for index, query in enumerate(queries):
        query_weight = 1.0 - min(index * 0.06, 0.30)

        try:
            rows = _search_global_chunks(query, limit=max(limit, 24))
        except Exception:
            rows = []

        for item in rows:
            item = dict(item)
            item["rank"] = float(item.get("rank") or 0) * query_weight
            _merge_result(collected, item)

    results = list(collected.values())
    results.sort(key=lambda item: float(item.get("rank") or 0), reverse=True)

    return results[:limit]


def _search_global_chunks(query: str, limit: int) -> list[dict]:
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
                flc.document_id,
                left(flc.content, 2600) AS content,
                fld.title,
                fld.document_type,
                fld.authority,
                fld.document_number,
                fld.document_date,
                fld.status,
                fld.is_widely_used,
                fld.is_base_law,
                fld.is_change_law,
                fld.is_project_law,
                fld.legal_rank,
                fld.source,
                fld.source_url,
                'global_chunk_fts' AS search_method,
                (
                    ts_rank_cd(flc.search_vector, search_query.query, 32)
                    + fld.legal_rank * 0.35
                ) AS rank
            FROM federal_law_chunks flc
            JOIN federal_law_documents fld ON fld.id = flc.document_id
            CROSS JOIN search_query
            WHERE
                search_query.query <> ''::tsquery
                AND flc.search_vector @@ search_query.query
            ORDER BY rank DESC
            LIMIT :limit
        """), {
            "query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]

def _apply_query_aware_rank(
    user_query: str,
    item: dict,
    current_rank: float,
) -> float:
    query = _normalize_text(user_query)

    title = _normalize_text(item.get("title"))
    document_type = _normalize_text(item.get("document_type"))
    number = _normalize_text(item.get("document_number"))
    status = _normalize_text(item.get("status"))
    authority = _normalize_text(item.get("authority"))

    rank = float(current_rank or 0)

    rank += _primary_source_boost(
        query=query,
        title=title,
        document_type=document_type,
        number=number,
    )

    rank += _document_quality_boost(
        title=title,
        document_type=document_type,
        number=number,
        status=status,
        authority=authority,
        is_base_law=bool(item.get("is_base_law")),
        is_change_law=bool(item.get("is_change_law")),
        is_project_law=bool(item.get("is_project_law")),
    )

    return rank


def _primary_source_boost(
    query: str,
    title: str,
    document_type: str,
    number: str,
) -> float:
    boost = 0.0

    is_code = "кодекс" in document_type or "кодекс" in title

    if _has_any(query, [
        "договор",
        "подряд",
        "неустойк",
        "незаключ",
        "убыт",
        "обязательств",
        "исполнени",
        "займ",
        "оказани услуг",
        "односторонний отказ",
        "заказчик",
        "подрядчик",
    ]):
        if "гражданский кодекс российской федерации" in title:
            boost += 9.0
        elif is_code and "гражданский" in title:
            boost += 6.0

    if _has_any(query, [
        "банкрот",
        "несостоятельн",
        "субсидиарн",
        "контролирующ",
        "должник",
        "кредитор",
        "финансовый управляющий",
        "арбитражный управляющий",
        "оспаривание сдел",
        "очередность удовлетворения",
    ]):
        if "127-фз" in number and "несостоятельности" in title:
            boost += 10.0
        elif "о несостоятельности" in title and "банкротстве" in title:
            boost += 9.0

        if "154-фз" in number and ("крым" in title or "севастопол" in title):
            boost -= 7.0

    if _has_any(query, [
        "гпк",
        "гражданск процесс",
        "кассацион",
        "апелляцион",
        "исковое заявление",
        "оставление искового заявления",
        "восстановление срока",
        "процессуальн",
    ]):
        if "гражданский процессуальный кодекс российской федерации" in title:
            boost += 10.0
        elif is_code and "процессуальный" in title:
            boost += 7.0

    if _has_any(query, [
        "труд",
        "увольнен",
        "работник",
        "работодатель",
        "заработн",
        "прогул",
        "сокращени",
        "восстановление на работе",
    ]):
        if "трудовой кодекс российской федерации" in title:
            boost += 9.0

    if _has_any(query, [
        "супруг",
        "алименты",
        "ребен",
        "ребён",
        "развод",
        "брак",
        "раздел имущества",
        "место жительства ребенка",
        "место жительства ребёнка",
    ]):
        if "семейный кодекс российской федерации" in title:
            boost += 9.0

    if _has_any(query, [
        "апк",
        "арбитражн процесс",
        "арбитражный суд",
    ]):
        if "арбитражный процессуальный кодекс российской федерации" in title:
            boost += 9.0

    if _has_any(query, [
        "коап",
        "административн правонаруш",
        "административная ответственность",
    ]):
        if "кодекс российской федерации об административных правонарушениях" in title:
            boost += 9.0

    if _has_any(query, [
        "ук",
        "уголовн",
        "преступлен",
        "наказани",
    ]):
        if "уголовный кодекс российской федерации" in title:
            boost += 9.0

    if _has_any(query, [
        "упк",
        "уголовн процесс",
        "следователь",
        "дознание",
        "обвиняем",
        "подозреваем",
    ]):
        if "уголовно-процессуальный кодекс российской федерации" in title:
            boost += 9.0

    if _has_any(query, [
        "налог",
        "ндфл",
        "ндс",
        "налоговая",
        "налоговый",
    ]):
        if "налоговый кодекс российской федерации" in title:
            boost += 9.0

    return boost


def _document_quality_boost(
    title: str,
    document_type: str,
    number: str,
    status: str,
    authority: str,
    is_base_law: bool,
    is_change_law: bool,
    is_project_law: bool,
) -> float:
    boost = 0.0

    if is_base_law:
        boost += 1.5

    if "действует" in status:
        boost += 1.0

    if "кодекс" in document_type or "кодекс" in title:
        boost += 1.2

    if number:
        boost += 0.2

    if is_change_law:
        boost -= 3.5

    if is_project_law:
        boost -= 5.0

    if _has_any(title, [
        "о внесении изменений",
        "о внесении изменения",
        "о признании утратившими силу",
        "о признании утратившим силу",
        "о проекте федерального закона",
        "проект федерального закона",
        "о федеральном законе",
    ]):
        boost -= 4.0

    if _has_any(title, [
        "рсфср",
        "ссср",
        "совета министров",
        "верховного совета",
    ]):
        boost -= 4.5

    if _has_any(title, [
        "крым",
        "севастопол",
    ]):
        boost -= 1.0

    if "конституционный суд" in authority:
        boost -= 0.4

    return boost


def _has_any(text_value: str, needles: list[str]) -> bool:
    return any(needle in text_value for needle in needles)


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").lower().replace("ё", "е").split())

def _merge_result(collected: dict, item: dict) -> None:
    document_key = _build_document_key(item)

    if not document_key:
        return

    existing = collected.get(document_key)

    if not existing or float(item.get("rank") or 0) > float(existing.get("rank") or 0):
        collected[document_key] = item


def _build_document_key(item: dict) -> str:
    title = (item.get("title") or "").strip().lower()
    number = (item.get("document_number") or "").strip().lower()
    date = (item.get("document_date") or "").strip().lower()

    if title or number or date:
        return f"{title}|{number}|{date}"

    return str(item.get("source_url") or item.get("chunk_id") or "")


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


def _format_embedding(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"