import time

from openai import OpenAI
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal


BATCH_SIZE = 80
EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")


client = OpenAI(api_key=settings.OPENAI_API_KEY)


def main() -> None:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не настроен.")

    total = _count_missing_embeddings()
    print(f"Core law articles without embeddings: {total}")

    processed = 0

    while True:
        rows = _load_batch()

        if not rows:
            break

        texts = [_create_embedding_text(row)[:7000] for row in rows]

        try:
            embeddings = _embed_batch(texts)
        except Exception as error:
            print(f"Batch failed: {error}")
            print("Retrying one by one...")
            embeddings = []

            for item in texts:
                try:
                    embeddings.append(_embed_batch([item[:4000]])[0])
                except Exception:
                    embeddings.append(_embed_batch([item[:2000]])[0])

        _save_embeddings(rows, embeddings)

        processed += len(rows)
        print(f"Embedded {processed}/{total}")

        time.sleep(0.3)

    print("Done.")


def _count_missing_embeddings() -> int:
    with SessionLocal() as session:
        return session.execute(text("""
            SELECT COUNT(*)
            FROM core_law_articles
            WHERE embedding IS NULL
        """)).scalar_one()


def _load_batch() -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT
                id,
                codex,
                chapter,
                article_num,
                article_title,
                content
            FROM core_law_articles
            WHERE embedding IS NULL
            ORDER BY id ASC
            LIMIT :limit
        """), {
            "limit": BATCH_SIZE,
        }).mappings().fetchall()

    return [dict(row) for row in rows]


def _create_embedding_text(article: dict) -> str:
    parts = [
        article.get("codex") or "",
        article.get("chapter") or "",
        f"Статья {article.get('article_num') or ''}. {article.get('article_title') or ''}",
        article.get("content") or "",
    ]

    return "\n".join(part for part in parts if part.strip())


def _embed_batch(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )

    return [item.embedding for item in response.data]


def _save_embeddings(rows: list[dict], embeddings: list[list[float]]) -> None:
    payload = []

    for row, embedding in zip(rows, embeddings):
        payload.append({
            "id": row["id"],
            "embedding": _format_embedding(embedding),
        })

    with SessionLocal() as session:
        session.execute(text("""
            UPDATE core_law_articles
            SET
                embedding = CAST(:embedding AS vector),
                updated_at = NOW()
            WHERE id = :id
        """), payload)

        session.commit()


def _format_embedding(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"


if __name__ == "__main__":
    main()