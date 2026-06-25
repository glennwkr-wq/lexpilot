from sqlalchemy import text

from app.db.session import SessionLocal


def ensure_core_law_tables() -> None:
    with SessionLocal() as session:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS core_law_articles (
                id SERIAL PRIMARY KEY,
                codex TEXT NOT NULL,
                codex_id TEXT NOT NULL,
                chapter TEXT,
                article_num TEXT NOT NULL,
                article_title TEXT,
                content TEXT NOT NULL,
                url TEXT,
                source TEXT NOT NULL DEFAULT 'legal-ai-platform',
                search_vector tsvector,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (codex_id, article_num)
            )
        """))

        session.commit()


def ensure_core_law_indexes() -> None:
    with SessionLocal() as session:
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_core_law_articles_codex_id
            ON core_law_articles (codex_id)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_core_law_articles_article_num
            ON core_law_articles (article_num)
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_core_law_articles_search_vector
            ON core_law_articles USING GIN (search_vector)
        """))

        session.commit()