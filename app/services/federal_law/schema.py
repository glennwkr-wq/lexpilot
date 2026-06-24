from sqlalchemy import text
from app.db.session import SessionLocal


def ensure_federal_law_tables() -> None:
    with SessionLocal() as session:
        session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        session.execute(text("""
            CREATE TABLE IF NOT EXISTS federal_law_documents (
                id SERIAL PRIMARY KEY,
                external_id TEXT UNIQUE,
                title TEXT NOT NULL,
                document_type TEXT,
                authority TEXT,
                document_number TEXT,
                document_date TEXT,
                status TEXT,
                is_widely_used BOOLEAN DEFAULT FALSE,
                source TEXT NOT NULL DEFAULT 'RusLawOD',
                source_url TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        session.execute(text("""
            CREATE TABLE IF NOT EXISTS federal_law_chunks (
                id SERIAL PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES federal_law_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        session.execute(text("""
            ALTER TABLE federal_law_documents
            ADD COLUMN IF NOT EXISTS search_vector tsvector
        """))

        session.execute(text("""
            ALTER TABLE federal_law_chunks
            ADD COLUMN IF NOT EXISTS search_vector tsvector
        """))

        session.execute(text("""
            ALTER TABLE federal_law_chunks
            ADD COLUMN IF NOT EXISTS embedding vector(1536)
        """))

        session.execute(text("""
            ALTER TABLE federal_law_documents
            ADD COLUMN IF NOT EXISTS is_base_law BOOLEAN NOT NULL DEFAULT FALSE
        """))

        session.execute(text("""
            ALTER TABLE federal_law_documents
            ADD COLUMN IF NOT EXISTS is_change_law BOOLEAN NOT NULL DEFAULT FALSE
        """))

        session.execute(text("""
            ALTER TABLE federal_law_documents
            ADD COLUMN IF NOT EXISTS is_project_law BOOLEAN NOT NULL DEFAULT FALSE
        """))

        session.execute(text("""
            ALTER TABLE federal_law_documents
            ADD COLUMN IF NOT EXISTS legal_rank NUMERIC NOT NULL DEFAULT 0
        """))

        session.execute(text("""
            CREATE TABLE IF NOT EXISTS federal_law_import_runs (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                documents_count INTEGER NOT NULL DEFAULT 0,
                chunks_count INTEGER NOT NULL DEFAULT 0,
                skipped_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        session.commit()


def ensure_federal_law_search_indexes() -> None:
    with SessionLocal() as session:
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_documents_external_id
            ON federal_law_documents (external_id)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_documents_type
            ON federal_law_documents (document_type)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_documents_type_status
            ON federal_law_documents (document_type, status)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_documents_number_date
            ON federal_law_documents (document_number, document_date)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_documents_legal_rank
            ON federal_law_documents (legal_rank DESC)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_chunks_document_id
            ON federal_law_chunks (document_id)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_documents_search_vector
            ON federal_law_documents USING GIN (search_vector)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_federal_law_chunks_search_vector
            ON federal_law_chunks USING GIN (search_vector)
        """))

        session.commit()