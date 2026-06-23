from datetime import date

from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.knowledge.ingest import split_text


ALLOWED_DOCUMENT_TYPES = {
    "law": "Закон / нормативный акт",
    "plenum_vsrf": "Пленум ВС РФ",
    "review_vsrf": "Обзор ВС РФ",
    "court_practice": "Судебная практика",
    "document_template": "Шаблон документа",
    "checklist": "Чек-лист",
    "real_example": "Обезличенный пример",
    "legal_position": "Правовая позиция",
}


def add_manual_knowledge_document(data: dict) -> dict:
    title = (data.get("title") or "").strip()
    document_type = (data.get("document_type") or "").strip()
    source_url = (data.get("source_url") or "").strip()
    document_date_raw = (data.get("document_date") or "").strip()
    content = (data.get("content") or "").strip()

    if not title:
        raise ValueError("Укажите название материала.")

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValueError("Выберите корректный тип материала.")

    if not content:
        raise ValueError("Добавьте текст материала.")

    if len(content) < 80:
        raise ValueError("Текст материала слишком короткий для базы знаний.")

    document_date = _parse_date(document_date_raw)

    chunks = split_text(content)

    if not chunks:
        raise ValueError("Не удалось подготовить фрагменты поиска.")

    with SessionLocal() as session:
        document_id = session.execute(
            text("""
                INSERT INTO legal_documents
                    (title, document_type, source, source_url, document_date, content)
                VALUES
                    (:title, :document_type, :source, :source_url, :document_date, :content)
                RETURNING id
            """),
            {
                "title": title,
                "document_type": document_type,
                "source": "manual",
                "source_url": source_url or "Добавлено вручную",
                "document_date": document_date,
                "content": content,
            },
        ).scalar_one()

        for index, chunk in enumerate(chunks):
            session.execute(
                text("""
                    INSERT INTO knowledge_chunks
                        (document_id, chunk_index, content)
                    VALUES
                        (:document_id, :chunk_index, :content)
                """),
                {
                    "document_id": document_id,
                    "chunk_index": index,
                    "content": chunk,
                },
            )

        session.commit()

    return {
        "id": document_id,
        "title": title,
        "document_type": document_type,
        "document_type_label": ALLOWED_DOCUMENT_TYPES[document_type],
        "source": "manual",
        "source_url": source_url or "Добавлено вручную",
        "document_date": document_date_raw,
        "chunks_count": len(chunks),
    }


def _parse_date(value: str) -> date | None:
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Дата документа должна быть в формате ГГГГ-ММ-ДД.") from error