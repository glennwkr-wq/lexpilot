from sqlalchemy import text

from app.db.session import SessionLocal


def search_knowledge(query: str, limit: int = 5) -> list[dict]:
    query = query.strip()

    if not query:
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
                    kc.content ILIKE :query
                    OR ld.title ILIKE :query
                    OR ld.document_type ILIKE :query
                ORDER BY kc.id DESC
                LIMIT :limit
            """),
            {
                "query": f"%{query}%",
                "limit": limit,
            },
        ).fetchall()

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