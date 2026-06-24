import argparse
import time

from openai import OpenAI
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal


client = OpenAI(api_key=settings.OPENAI_API_KEY)


def format_embedding(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def fetch_batch(limit: int, only_base_law: bool) -> list[dict]:
    with SessionLocal() as session:
        if only_base_law:
            rows = session.execute(text("""
                SELECT
                    flc.id,
                    fld.title,
                    fld.document_type,
                    fld.document_number,
                    fld.document_date,
                    flc.content
                FROM federal_law_chunks flc
                JOIN federal_law_documents fld ON fld.id = flc.document_id
                WHERE
                    flc.embedding IS NULL
                    AND fld.is_base_law = TRUE
                ORDER BY fld.legal_rank DESC, flc.id ASC
                LIMIT :limit
            """), {"limit": limit}).mappings().fetchall()
        else:
            rows = session.execute(text("""
                SELECT
                    flc.id,
                    fld.title,
                    fld.document_type,
                    fld.document_number,
                    fld.document_date,
                    flc.content
                FROM federal_law_chunks flc
                JOIN federal_law_documents fld ON fld.id = flc.document_id
                WHERE flc.embedding IS NULL
                ORDER BY fld.legal_rank DESC, flc.id ASC
                LIMIT :limit
            """), {"limit": limit}).mappings().fetchall()

    return [dict(row) for row in rows]


def build_embedding_text(row: dict) -> str:
    return f"""
Название: {row.get("title")}
Тип: {row.get("document_type")}
Номер: {row.get("document_number")}
Дата: {row.get("document_date")}

Текст:
{row.get("content")}
""".strip()[:8000]


def update_embeddings(rows: list[dict], embeddings: list[list[float]]) -> None:
    update_rows = [
        {
            "id": row["id"],
            "embedding": format_embedding(embedding),
        }
        for row, embedding in zip(rows, embeddings)
    ]

    with SessionLocal() as session:
        for item in update_rows:
            session.execute(text("""
                UPDATE federal_law_chunks
                SET embedding = CAST(:embedding AS vector)
                WHERE id = :id
            """), item)

        session.commit()


def embed_chunks(batch_size: int, sleep_seconds: float, only_base_law: bool) -> None:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    total = 0

    while True:
        rows = fetch_batch(limit=batch_size, only_base_law=only_base_law)

        if not rows:
            break

        texts = [build_embedding_text(row) for row in rows]

        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
        )

        embeddings = [item.embedding for item in response.data]

        update_embeddings(rows, embeddings)

        total += len(rows)
        print(f"Embedded chunks: {total}")

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    print("Embedding complete")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--all", action="store_true")

    args = parser.parse_args()

    embed_chunks(
        batch_size=args.batch_size,
        sleep_seconds=args.sleep,
        only_base_law=not args.all,
    )


if __name__ == "__main__":
    main()