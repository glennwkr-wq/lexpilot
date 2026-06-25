import json
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.core_law.schema import (
    ensure_core_law_tables,
    ensure_core_law_indexes,
)


DEFAULT_CODEX_JSON_PATH = Path("ingestion/data/parsed/all_codexes.json")


def import_core_law_articles(json_path: str | None = None) -> dict:
    ensure_core_law_tables()

    source_path = Path(json_path) if json_path else DEFAULT_CODEX_JSON_PATH

    if not source_path.exists():
        return {
            "status": "error",
            "message": f"Файл не найден: {source_path}",
            "imported": 0,
        }

    with open(source_path, encoding="utf-8") as file:
        articles = json.load(file)

    imported = 0
    skipped = 0

    with SessionLocal() as session:
        for article in articles:
            codex = _clean(article.get("codex"))
            codex_id = _clean(article.get("codex_id"))
            article_num = _clean(article.get("article_num"))
            article_title = _clean(article.get("article_title"))
            chapter = _clean(article.get("chapter"))
            content = _clean(article.get("text"))
            url = _clean(article.get("url"))

            if not codex or not codex_id or not article_num or not content:
                skipped += 1
                continue

            session.execute(text("""
                INSERT INTO core_law_articles (
                    codex,
                    codex_id,
                    chapter,
                    article_num,
                    article_title,
                    content,
                    url,
                    search_vector,
                    updated_at
                )
                VALUES (
                    :codex,
                    :codex_id,
                    :chapter,
                    :article_num,
                    :article_title,
                    :content,
                    :url,
                    to_tsvector(
                        'russian',
                        coalesce(:codex, '') || ' ' ||
                        coalesce(:chapter, '') || ' ' ||
                        coalesce(:article_num, '') || ' ' ||
                        coalesce(:article_title, '') || ' ' ||
                        coalesce(:content, '')
                    ),
                    NOW()
                )
                ON CONFLICT (codex_id, article_num) DO UPDATE
                SET
                    codex = EXCLUDED.codex,
                    chapter = EXCLUDED.chapter,
                    article_title = EXCLUDED.article_title,
                    content = EXCLUDED.content,
                    url = EXCLUDED.url,
                    search_vector = EXCLUDED.search_vector,
                    updated_at = NOW()
            """), {
                "codex": codex,
                "codex_id": codex_id,
                "chapter": chapter,
                "article_num": article_num,
                "article_title": article_title,
                "content": content,
                "url": url,
            })

            imported += 1

        session.commit()

    ensure_core_law_indexes()

    return {
        "status": "ok",
        "source_path": str(source_path),
        "imported": imported,
        "skipped": skipped,
    }


def _clean(value) -> str:
    if value is None:
        return ""

    return str(value).strip()