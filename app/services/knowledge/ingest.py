from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal


PROJECT_ROOT = Path.cwd()
KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge_base"


def split_text(text_value: str, chunk_size: int = 3500) -> list[str]:
    text_value = text_value.strip()

    if not text_value:
        return []

    chunks = []
    start = 0

    while start < len(text_value):
        end = start + chunk_size
        chunk = text_value[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end

    return chunks


def infer_category(file_path: Path) -> str:
    relative_parts = file_path.relative_to(KNOWLEDGE_ROOT).parts

    if len(relative_parts) > 1:
        return relative_parts[0]

    return "general"


def extract_title(content: str, file_path: Path) -> str:
    for line in content.splitlines():
        line = line.strip()

        if line.startswith("# "):
            return line.replace("# ", "", 1).strip()

        if line.upper().startswith("TITLE:"):
            return line.split(":", 1)[1].strip()

    return file_path.stem.replace("_", " ").strip().title()


def ingest_knowledge_base() -> dict:
    if not KNOWLEDGE_ROOT.exists():
        return {
            "status": "error",
            "message": "knowledge_base folder not found",
            "documents": 0,
            "chunks": 0,
        }

    files = sorted(
        list(KNOWLEDGE_ROOT.rglob("*.md")) +
        list(KNOWLEDGE_ROOT.rglob("*.txt"))
    )

    documents_count = 0
    chunks_count = 0

    with SessionLocal() as session:
        for file_path in files:
            content = file_path.read_text(encoding="utf-8").strip()

            if not content:
                continue

            relative_path = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            title = extract_title(content, file_path)
            category = infer_category(file_path)

            existing = session.execute(
                text("""
                    SELECT id
                    FROM legal_documents
                    WHERE source_url = :source_url
                    LIMIT 1
                """),
                {"source_url": relative_path},
            ).fetchone()

            if existing:
                document_id = existing[0]

                session.execute(
                    text("""
                        UPDATE legal_documents
                        SET
                            title = :title,
                            document_type = :document_type,
                            source = :source,
                            content = :content
                        WHERE id = :id
                    """),
                    {
                        "id": document_id,
                        "title": title,
                        "document_type": category,
                        "source": "local knowledge_base",
                        "content": content,
                    },
                )

                session.execute(
                    text("""
                        DELETE FROM knowledge_chunks
                        WHERE document_id = :document_id
                    """),
                    {"document_id": document_id},
                )

            else:
                document_id = session.execute(
                    text("""
                        INSERT INTO legal_documents
                            (title, document_type, source, source_url, content)
                        VALUES
                            (:title, :document_type, :source, :source_url, :content)
                        RETURNING id
                    """),
                    {
                        "title": title,
                        "document_type": category,
                        "source": "local knowledge_base",
                        "source_url": relative_path,
                        "content": content,
                    },
                ).scalar_one()

            chunks = split_text(content)

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

            documents_count += 1
            chunks_count += len(chunks)

        session.commit()

    return {
        "status": "ok",
        "message": "Knowledge base ingested successfully",
        "documents": documents_count,
        "chunks": chunks_count,
    }