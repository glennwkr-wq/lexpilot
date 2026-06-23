from pathlib import Path
import shutil
import tempfile

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from sqlalchemy import text
from tqdm import tqdm

from app.db.session import SessionLocal
from app.services.federal_law.schema import (
    ensure_federal_law_tables,
    ensure_federal_law_search_indexes,
)


RUSLAWOD_REPO_ID = "irlspbru/RusLawOD"
RUSLAWOD_FILES = [f"ruslawod_{index:02d}.parquet" for index in range(1, 11)]


def split_text(text_value: str, chunk_size: int = 2500) -> list[str]:
    text_value = (text_value or "").strip()
    if not text_value:
        return []

    return [
        text_value[start:start + chunk_size].strip()
        for start in range(0, len(text_value), chunk_size)
        if text_value[start:start + chunk_size].strip()
    ]


def import_ruslawod(
    limit_files: int | None = None,
    batch_size: int = 300,
    create_indexes: bool = False,
) -> dict:
    ensure_federal_law_tables()

    files = RUSLAWOD_FILES[:limit_files] if limit_files else RUSLAWOD_FILES

    total_documents = 0
    total_chunks = 0
    total_skipped = 0

    cache_dir = Path(tempfile.gettempdir()) / "ruslawod_hf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    for filename in files:
        if _is_file_imported(filename):
            print(f"SKIP already imported: {filename}")
            continue

        _mark_file_started(filename)

        try:
            print(f"Downloading {filename}...")

            parquet_path = hf_hub_download(
                repo_id=RUSLAWOD_REPO_ID,
                filename=filename,
                repo_type="dataset",
                cache_dir=str(cache_dir),
            )

            result = _import_parquet_file(
                filename=filename,
                parquet_path=Path(parquet_path),
                batch_size=batch_size,
            )

            _mark_file_finished(filename, result)

            total_documents += result["documents"]
            total_chunks += result["chunks"]
            total_skipped += result["skipped"]

            print(f"Imported {filename}: {result}")

        except Exception as error:
            _mark_file_failed(filename, error)
            raise

        finally:
            shutil.rmtree(cache_dir, ignore_errors=True)
            cache_dir.mkdir(parents=True, exist_ok=True)

    if create_indexes:
        print("Creating federal law search indexes...")
        ensure_federal_law_search_indexes()

    return {
        "status": "ok",
        "documents": total_documents,
        "chunks": total_chunks,
        "skipped": total_skipped,
    }


def _import_parquet_file(filename: str, parquet_path: Path, batch_size: int) -> dict:
    parquet_file = pq.ParquetFile(parquet_path)

    documents_count = 0
    chunks_count = 0
    skipped_count = 0

    for batch in tqdm(
        parquet_file.iter_batches(batch_size=batch_size),
        desc=f"Import {filename}",
    ):
        rows = batch.to_pylist()

        with SessionLocal() as session:
            for row in rows:
                content = _clean_value(row.get("textIPS"))
                external_id = _clean_value(row.get("pravogovruNd"))

                if not content or not external_id:
                    skipped_count += 1
                    continue

                title = (
                    _clean_value(row.get("headingIPS"))
                    or _clean_value(row.get("issuedByIPS"))
                    or f"Правовой акт {external_id}"
                )

                document_id = session.execute(text("""
                    INSERT INTO federal_law_documents (
                        external_id,
                        title,
                        document_type,
                        authority,
                        document_number,
                        document_date,
                        status,
                        is_widely_used,
                        source,
                        source_url,
                        content,
                        updated_at
                    )
                    VALUES (
                        :external_id,
                        :title,
                        :document_type,
                        :authority,
                        :document_number,
                        :document_date,
                        :status,
                        :is_widely_used,
                        'RusLawOD',
                        :source_url,
                        :content,
                        NOW()
                    )
                    ON CONFLICT (external_id) DO NOTHING
                    RETURNING id
                """), {
                    "external_id": external_id,
                    "title": title,
                    "document_type": _clean_value(row.get("doc_typeIPS")),
                    "authority": _clean_value(row.get("doc_author_normal_formIPS")),
                    "document_number": _clean_value(row.get("docNumberIPS")),
                    "document_date": _clean_value(row.get("docdateIPS")),
                    "status": _clean_value(row.get("statusIPS")),
                    "is_widely_used": _to_bool(row.get("is_widely_used")),
                    "source_url": f"RusLawOD:{external_id}",
                    "content": content,
                }).scalar_one_or_none()

                if not document_id:
                    skipped_count += 1
                    continue

                chunk_rows = [
                    {
                        "document_id": document_id,
                        "chunk_index": index,
                        "title": title,
                        "content": chunk,
                    }
                    for index, chunk in enumerate(split_text(content))
                ]

                if chunk_rows:
                    session.execute(text("""
                        INSERT INTO federal_law_chunks (
                            document_id,
                            chunk_index,
                            title,
                            content
                        )
                        VALUES (
                            :document_id,
                            :chunk_index,
                            :title,
                            :content
                        )
                    """), chunk_rows)

                documents_count += 1
                chunks_count += len(chunk_rows)

            session.commit()

    return {
        "documents": documents_count,
        "chunks": chunks_count,
        "skipped": skipped_count,
    }


def _is_file_imported(filename: str) -> bool:
    with SessionLocal() as session:
        row = session.execute(text("""
            SELECT status
            FROM federal_law_import_runs
            WHERE filename = :filename
            LIMIT 1
        """), {"filename": filename}).fetchone()

    return bool(row and row.status == "done")


def _mark_file_started(filename: str) -> None:
    with SessionLocal() as session:
        session.execute(text("""
            INSERT INTO federal_law_import_runs (
                filename,
                status,
                started_at,
                updated_at
            )
            VALUES (
                :filename,
                'running',
                NOW(),
                NOW()
            )
            ON CONFLICT (filename) DO UPDATE
            SET
                status = 'running',
                error_message = NULL,
                started_at = NOW(),
                updated_at = NOW()
        """), {"filename": filename})

        session.commit()


def _mark_file_finished(filename: str, result: dict) -> None:
    with SessionLocal() as session:
        session.execute(text("""
            UPDATE federal_law_import_runs
            SET
                status = 'done',
                documents_count = :documents_count,
                chunks_count = :chunks_count,
                skipped_count = :skipped_count,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE filename = :filename
        """), {
            "filename": filename,
            "documents_count": result["documents"],
            "chunks_count": result["chunks"],
            "skipped_count": result["skipped"],
        })

        session.commit()


def _mark_file_failed(filename: str, error: Exception) -> None:
    with SessionLocal() as session:
        session.execute(text("""
            UPDATE federal_law_import_runs
            SET
                status = 'error',
                error_message = :error_message,
                updated_at = NOW()
            WHERE filename = :filename
        """), {
            "filename": filename,
            "error_message": repr(error),
        })

        session.commit()


def _clean_value(value) -> str:
    if value is None:
        return ""

    text_value = str(value).strip()

    if text_value.lower() in {"nan", "none", "null"}:
        return ""

    return text_value


def _to_bool(value) -> bool:
    text_value = _clean_value(value).lower()
    return text_value in {"1", "true", "yes", "да"}