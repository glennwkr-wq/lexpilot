from sqlalchemy import text

from app.db.session import SessionLocal


def search_knowledge(query: str, limit: int = 5) -> list[dict]:
    query = query.strip()

    if not query:
        return []

    words = [word.strip() for word in query.split() if len(word.strip()) >= 3]
    words = words[:8]

    if not words:
        words = [query]

    conditions = []
    params = {"limit": limit}

    for index, word in enumerate(words):
        key = f"q{index}"
        conditions.append(
            f"""
            kc.content ILIKE :{key}
            OR ld.title ILIKE :{key}
            OR ld.document_type ILIKE :{key}
            OR ld.source_url ILIKE :{key}
            """
        )
        params[key] = f"%{word}%"

    where_sql = " OR ".join(f"({condition})" for condition in conditions)

    with SessionLocal() as session:
        rows = session.execute(
            text(f"""
                SELECT
                    kc.id,
                    kc.content,
                    ld.title,
                    ld.document_type,
                    ld.source,
                    ld.source_url
                FROM knowledge_chunks kc
                JOIN legal_documents ld ON ld.id = kc.document_id
                WHERE {where_sql}
                ORDER BY kc.id DESC
                LIMIT :limit
            """),
            params,
        ).fetchall()

    return _rows_to_dicts(rows)


def search_knowledge_by_phrase(phrase: str, limit: int = 5) -> list[dict]:
    phrase = phrase.strip()

    if not phrase:
        return []

    with SessionLocal() as session:
        rows = session.execute(
            text("""
                SELECT
                    kc.id,
                    kc.content,
                    ld.title,
                    ld.document_type,
                    ld.source,
                    ld.source_url
                FROM knowledge_chunks kc
                JOIN legal_documents ld ON ld.id = kc.document_id
                WHERE
                    kc.content ILIKE :phrase
                    OR ld.title ILIKE :phrase
                    OR ld.document_type ILIKE :phrase
                    OR ld.source_url ILIKE :phrase
                ORDER BY kc.id DESC
                LIMIT :limit
            """),
            {
                "phrase": f"%{phrase}%",
                "limit": limit,
            },
        ).fetchall()

    return _rows_to_dicts(rows)


def _rows_to_dicts(rows) -> list[dict]:
    return [
        {
            "chunk_id": row.id,
            "content": row.content,
            "title": row.title,
            "document_type": row.document_type,
            "source": row.source,
            "source_url": row.source_url,
        }
        for row in rows
    ]


def build_knowledge_context(results: list[dict]) -> str:
    if not results:
        return ""

    blocks = []

    for index, item in enumerate(results, start=1):
        blocks.append(
            f"""
[Источник {index}]
Название: {item["title"]}
Тип: {item["document_type"]}
Путь/источник: {item["source_url"]}

Фрагмент:
{item["content"]}
""".strip()
        )

    return "\n\n---\n\n".join(blocks)