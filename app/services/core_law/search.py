from sqlalchemy import text

from app.db.session import SessionLocal


RRF_K = 60


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

    ranking_pool = {}

    if query_embedding:
        vector_rows = _search_core_articles_vector(
            query_embedding=query_embedding,
            limit=max(limit * 5, 40),
        )
        _add_ranked_rows(
            pool=ranking_pool,
            rows=vector_rows,
            source_name="vector",
            weight=1.35,
            user_query=query,
        )

    for index, item_query in enumerate(queries[:5]):
        query_weight = 1.0 - min(index * 0.08, 0.35)
        fts_rows = _search_core_articles_fts(
            query=item_query,
            limit=max(limit * 5, 40),
        )
        _add_ranked_rows(
            pool=ranking_pool,
            rows=fts_rows,
            source_name=f"fts_{index}",
            weight=1.0 * query_weight,
            user_query=query,
        )

    results = list(ranking_pool.values())

    for item in results:
        item["rank"] = _final_core_rank(query, item)

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
Способ поиска: {item.get("search_method") or "core_law_hybrid"}
Ранг поиска: {round(float(item.get("rank") or 0), 4)}

Текст статьи:
{(item.get("content") or "")[:1800]}
""".strip())

    return "\n\n---\n\n".join(blocks)


def is_core_law_sufficient(results: list[dict]) -> bool:
    if not results:
        return False

    top_rank = float(results[0].get("rank") or 0)

    if top_rank >= 1.15:
        return True

    if len(results) >= 3 and top_rank >= 0.85:
        return True

    return False


def _search_core_articles_vector(
    query_embedding: list[float],
    limit: int,
) -> list[dict]:
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
                1 - (cla.embedding <=> CAST(:embedding AS vector)) AS raw_rank
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
                        WHEN cla.content ILIKE '%' || :plain_query || '%' THEN 0.8
                        ELSE 0
                      END
                ) AS raw_rank
            FROM core_law_articles cla
            CROSS JOIN search_query
            WHERE
                search_query.query <> ''::tsquery
                AND cla.search_vector @@ search_query.query
            ORDER BY raw_rank DESC, cla.id ASC
            LIMIT :limit
        """), {
            "query": query,
            "plain_query": query,
            "limit": limit,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _add_ranked_rows(
    pool: dict,
    rows: list[dict],
    source_name: str,
    weight: float,
    user_query: str,
) -> None:
    for position, row in enumerate(rows, start=1):
        item = dict(row)
        key = f"{item.get('codex_id')}:{item.get('article_num')}"

        rrf_score = weight * (1.0 / (RRF_K + position))
        raw_rank = float(item.get("raw_rank") or 0)
        normalized_raw = min(max(raw_rank, 0.0), 1.0)

        existing = pool.get(key)

        if not existing:
            item["rank"] = 0.0
            item["rrf_score"] = 0.0
            item["raw_score"] = 0.0
            item["search_methods"] = []
            existing = item
            pool[key] = existing

        existing["rrf_score"] = float(existing.get("rrf_score") or 0) + rrf_score
        existing["raw_score"] = max(float(existing.get("raw_score") or 0), normalized_raw)

        methods = existing.get("search_methods") or []
        if source_name not in methods:
            methods.append(source_name)

        existing["search_methods"] = methods
        existing["search_method"] = "core_law_hybrid:" + ",".join(methods)


def _final_core_rank(user_query: str, item: dict) -> float:
    query = _normalize_text(user_query)
    codex = _normalize_text(item.get("codex"))
    article_num = _normalize_text(item.get("article_num"))
    article_title = _normalize_text(item.get("article_title"))
    content = _normalize_text(item.get("content"))

    rank = 0.0
    rank += float(item.get("rrf_score") or 0) * 25.0
    rank += float(item.get("raw_score") or 0) * 0.75

    rank += _article_title_overlap_boost(query, article_title)
    rank += _codex_domain_boost(query, codex)
    rank += _article_number_boost(query, article_num)
    rank += _important_phrase_boost(query, article_title, content)

    return rank


def _article_title_overlap_boost(query: str, article_title: str) -> float:
    query_tokens = _meaningful_tokens(query)
    title_tokens = _meaningful_tokens(article_title)

    if not query_tokens or not title_tokens:
        return 0.0

    overlap = len(set(query_tokens) & set(title_tokens))

    if overlap >= 3:
        return 0.55

    if overlap == 2:
        return 0.35

    if overlap == 1:
        return 0.15

    return 0.0


def _codex_domain_boost(query: str, codex: str) -> float:
    boost = 0.0

    if _has_any(query, ["коап", "штраф", "административн", "правонаруш", "водител", "транспорт", "автомобил"]):
        if "административных правонарушениях" in codex or "коап" in codex:
            boost += 0.25

    if _has_any(query, ["труд", "работник", "работодатель", "увольнен", "зарплат", "отпуск"]):
        if "трудовой кодекс" in codex:
            boost += 0.25

    if _has_any(query, ["договор", "неустойк", "подряд", "убыт", "займ", "аренд", "купл", "продаж"]):
        if "гражданский кодекс" in codex:
            boost += 0.25

    if _has_any(query, ["супруг", "алим", "ребен", "ребенок", "развод", "брак"]):
        if "семейный кодекс" in codex:
            boost += 0.25

    if _has_any(query, ["уголов", "преступ", "наказан", "краж", "мошеннич"]):
        if "уголовный кодекс" in codex:
            boost += 0.25

    if _has_any(query, ["налог", "ндфл", "ндс", "вычет"]):
        if "налоговый кодекс" in codex:
            boost += 0.25

    if _has_any(query, ["жиль", "жилое", "квартира", "собственник", "мкд"]):
        if "жилищный кодекс" in codex:
            boost += 0.25

    return boost


def _article_number_boost(query: str, article_num: str) -> float:
    if not article_num:
        return 0.0

    if f"статья {article_num}" in query or f"ст {article_num}" in query:
        return 0.8

    return 0.0


def _important_phrase_boost(query: str, article_title: str, content: str) -> float:
    text = f"{article_title} {content}"
    boost = 0.0

    if _has_any(query, ["нетрезв", "опьянен", "опьянение", "пьяный", "пьяная езда"]):
        if "находящимся в состоянии опьянения" in text or "состоянии опьянения" in text:
            boost += 0.8
        if "управление транспортным средством" in text:
            boost += 0.45

    if _has_any(query, ["договор подряда", "подряд"]):
        if "договор подряда" in article_title:
            boost += 0.9

    if _has_any(query, ["неустойк"]):
        if "понятие неустойки" in article_title:
            boost += 0.85

    if _has_any(query, ["беременн", "беременная"]):
        if "беременн" in text and "расторжение трудового договора" in text:
            boost += 0.75

    if _has_any(query, ["исковая давность", "срок исковой"]):
        if "общий срок исковой давности" in article_title:
            boost += 0.9

    return boost


def _meaningful_tokens(text_value: str) -> list[str]:
    stop_words = {
        "что", "как", "какой", "какая", "какие", "можно", "может",
        "если", "для", "при", "или", "это", "его", "она", "они",
        "рф", "российской", "федерации", "кодекс", "статья",
    }

    tokens = []

    for token in _normalize_text(text_value).replace(".", " ").replace(",", " ").split():
        token = token.strip()

        if len(token) < 4:
            continue

        if token in stop_words:
            continue

        tokens.append(token)

    return tokens


def _has_any(text_value: str, needles: list[str]) -> bool:
    return any(needle in text_value for needle in needles)


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").lower().replace("ё", "е").split())


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