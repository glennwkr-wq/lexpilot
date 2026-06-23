from sqlalchemy import text

from app.db.session import SessionLocal


def ensure_generated_documents_table() -> None:
    with SessionLocal() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS generated_documents (
                id SERIAL PRIMARY KEY,
                case_id INTEGER,
                document_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        session.commit()


def save_generated_document(data: dict) -> dict:
    ensure_generated_documents_table()

    title = (data.get("title") or "Документ").strip()
    content = (data.get("content") or "").strip()
    document_type = (data.get("document_type") or "draft").strip()
    case_id = _parse_optional_int(data.get("case_id"))

    if not content:
        raise ValueError("Нет текста документа для сохранения.")

    with SessionLocal() as session:
        row = session.execute(text("""
            INSERT INTO generated_documents (
                case_id,
                document_type,
                title,
                content,
                updated_at
            )
            VALUES (
                :case_id,
                :document_type,
                :title,
                :content,
                NOW()
            )
            RETURNING
                id,
                case_id,
                document_type,
                title,
                content,
                created_at,
                updated_at
        """), {
            "case_id": case_id,
            "document_type": document_type,
            "title": title,
            "content": content,
        }).mappings().fetchone()

        session.commit()

    return dict(row)


def get_case_generated_documents(case_id: int) -> list[dict]:
    ensure_generated_documents_table()

    with SessionLocal() as session:
        rows = session.execute(text("""
            SELECT
                id,
                case_id,
                document_type,
                title,
                content,
                created_at,
                updated_at
            FROM generated_documents
            WHERE case_id = :case_id
            ORDER BY id DESC
        """), {"case_id": case_id}).mappings().fetchall()

    return [dict(row) for row in rows]


def get_generated_document_by_id(document_id: int) -> dict:
    ensure_generated_documents_table()

    with SessionLocal() as session:
        row = session.execute(text("""
            SELECT
                id,
                case_id,
                document_type,
                title,
                content,
                created_at,
                updated_at
            FROM generated_documents
            WHERE id = :id
            LIMIT 1
        """), {"id": document_id}).mappings().fetchone()

    if not row:
        raise ValueError("Документ не найден.")

    return dict(row)


def _parse_optional_int(value) -> int | None:
    if not value:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None