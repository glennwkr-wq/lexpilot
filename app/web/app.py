import time
from flask import Flask, render_template, jsonify, request, send_file
from sqlalchemy import text
from app.core.config import settings
from app.services.knowledge.ingest import ingest_knowledge_base
from app.services.knowledge.manual import (
    ALLOWED_DOCUMENT_TYPES,
    add_manual_knowledge_document,
)
from app.services.knowledge.search import search_knowledge, build_knowledge_context
from app.services.federal_law.schema import (
    ensure_federal_law_search_indexes,
    ensure_federal_law_tables,
    refresh_federal_law_roles,
)
from app.services.core_law.schema import ensure_core_law_indexes
from app.services.core_law.import_codexes import import_core_law_articles
from app.services.core_law.search import (
    search_core_law,
    build_core_law_context,
    is_core_law_sufficient,
)
from app.services.federal_law.search import (
    search_federal_law,
    build_federal_law_context,
)
from app.db.session import SessionLocal
from app.providers.llm.openai import (
    generate_legal_answer,
    generate_legal_search_queries,
    generate_embedding,
    rerank_core_law_sources,
    assess_core_law_sufficiency,
    rerank_federal_sources,
    analyze_legal_document,
    reset_openai_usage,
    get_openai_usage_summary,
)
from app.services.documents.builder import build_document_from_request
from app.services.documents.export_docx import (
    DOCX_MIME_TYPE,
    build_legal_docx,
    make_docx_filename,
)
from app.services.documents.docx_template_renderer import (
    get_docx_template_info,
    render_docx_template,
)
from app.services.documents.file_storage import (
    save_temp_file_and_extract,
    save_case_file,
    get_case_documents,
    get_document_file,
)
from app.services.documents.generated_store import (
    save_generated_document,
    get_case_generated_documents,
    get_generated_document_by_id,
)
from app.services.settings_store import get_lawyer_profile, save_lawyer_profile
from app.services.workspace_store import (
    get_dashboard_workspace,
    get_all_cases,
    get_case_by_id,
    create_case,
    update_case,
    delete_case,
    get_all_tasks,
    get_tasks_by_case,
    create_task,
    update_task,
    delete_task,
)
from app.services.clients_store import (
    get_all_clients,
    get_client_by_id,
    build_client_context,
    create_client,
    update_client,
    delete_client,
)

KNOWLEDGE_TYPE_LABELS = {
    "00_system_rules": "Системные правила",
    "01_scenarios": "Сценарии работы",
    "02_document_templates": "Шаблоны документов",
    "03_checklists": "Чек-листы",
    "04_risk_rules": "Правила оценки рисков",
    "05_legal_style": "Правила юридического стиля",
    "06_laws": "Законы и нормативные акты",
    "07_plenum_vsrf": "Пленумы ВС РФ",
    "08_reviews_vsrf": "Обзоры ВС РФ",
    "09_court_practice": "Судебная практика",
    "10_real_examples": "Обезличенные примеры",
    "11_template_blueprints": "Форматы шаблонов",
    "12_intake_forms": "Карты данных",
    "13_anonymization_rules": "Правила обезличивания",
    "law": "Закон / нормативный акт",
    "plenum_vsrf": "Пленум ВС РФ",
    "review_vsrf": "Обзор ВС РФ",
    "court_practice": "Судебная практика",
    "document_template": "Шаблон документа",
    "checklist": "Чек-лист",
    "real_example": "Обезличенный пример",
    "legal_position": "Правовая позиция",
}


def get_knowledge_type_label(document_type: str | None) -> str:
    if not document_type:
        return "Без категории"

    return KNOWLEDGE_TYPE_LABELS.get(document_type, document_type)


def get_knowledge_stats() -> dict:
    with SessionLocal() as session:
        total_documents = session.execute(
            text("SELECT COUNT(*) FROM legal_documents")
        ).scalar_one()

        total_chunks = session.execute(
            text("SELECT COUNT(*) FROM knowledge_chunks")
        ).scalar_one()

        manual_documents = session.execute(
            text("""
                SELECT COUNT(*)
                FROM legal_documents
                WHERE source = 'manual'
            """)
        ).scalar_one()

        system_documents = session.execute(
            text("""
                SELECT COUNT(*)
                FROM legal_documents
                WHERE source IS DISTINCT FROM 'manual'
            """)
        ).scalar_one()

        templates_count = session.execute(
            text("""
                SELECT COUNT(*)
                FROM legal_documents
                WHERE document_type IN ('02_document_templates', 'document_template')
            """)
        ).scalar_one()

        intake_forms_count = session.execute(
            text("""
                SELECT COUNT(*)
                FROM legal_documents
                WHERE document_type = '12_intake_forms'
            """)
        ).scalar_one()

        categories_rows = session.execute(
            text("""
                SELECT document_type, COUNT(*) AS count
                FROM legal_documents
                GROUP BY document_type
                ORDER BY count DESC, document_type ASC
            """)
        ).fetchall()

        documents_rows = session.execute(
            text("""
                SELECT
                    id,
                    title,
                    document_type,
                    source,
                    source_url,
                    document_date,
                    created_at
                FROM legal_documents
                ORDER BY id DESC
                LIMIT 80
            """)
        ).fetchall()

    categories = [
        {
            "document_type": row.document_type,
            "label": get_knowledge_type_label(row.document_type),
            "count": row.count,
        }
        for row in categories_rows
    ]

    documents = [
        {
            "id": row.id,
            "title": row.title,
            "document_type": row.document_type,
            "document_type_label": get_knowledge_type_label(row.document_type),
            "source": row.source,
            "source_url": row.source_url,
            "document_date": row.document_date,
            "created_at": row.created_at,
            "origin_label": "Материал юриста" if row.source == "manual" else "Системный материал",
        }
        for row in documents_rows
    ]

    return {
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "manual_documents": manual_documents,
        "system_documents": system_documents,
        "templates_count": templates_count,
        "intake_forms_count": intake_forms_count,
        "categories": categories,
        "documents": documents,
    }

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    ensure_federal_law_tables()
    ensure_federal_law_search_indexes()

    @app.get("/")
    def dashboard():
        workspace = get_dashboard_workspace()
        stats = get_knowledge_stats()

        return render_template(
            "dashboard.html",
            app_name=settings.APP_NAME,
            workspace=workspace,
            stats=stats,
        )

    @app.get("/ask")
    def ask_page():
        return render_template("ask.html", app_name=settings.APP_NAME)

    @app.get("/document-builder")
    def document_builder_page():
        clients = get_all_clients()
        cases = get_all_cases()
        selected_case_id = request.args.get("case_id") or ""

        return render_template(
            "document_builder.html",
            app_name=settings.APP_NAME,
            clients=clients,
            cases=cases,
            selected_case_id=selected_case_id,
        )

    @app.get("/document-analysis")
    def document_analysis_page():
        cases = get_all_cases()
        selected_case_id = request.args.get("case_id") or ""

        return render_template(
            "document_analysis.html",
            app_name=settings.APP_NAME,
            cases=cases,
            selected_case_id=selected_case_id,
        )

    @app.get("/cases")
    def cases_page():
        cases = get_all_cases()
        tasks = get_all_tasks()
        clients = get_all_clients()

        documents_by_case = {
            case["id"]: get_case_documents(case["id"])
            for case in cases
        }

        return render_template(
            "cases.html",
            app_name=settings.APP_NAME,
            cases=cases,
            tasks=tasks,
            clients=clients,
            documents_by_case=documents_by_case,
        )

    @app.get("/cases/<int:case_id>")
    def case_detail_page(case_id: int):
        case = get_case_by_id(case_id)

        if not case:
            return jsonify({
                "status": "error",
                "message": "Дело не найдено.",
            }), 404

        documents = get_case_documents(case_id)
        tasks = get_tasks_by_case(case_id)
        generated_documents = get_case_generated_documents(case_id)

        return render_template(
            "case_detail.html",
            app_name=settings.APP_NAME,
            case=case,
            documents=documents,
            tasks=tasks,
            generated_documents=generated_documents,
        )

    @app.get("/clients")
    def clients_page():
        clients = get_all_clients()

        return render_template(
            "clients.html",
            app_name=settings.APP_NAME,
            clients=clients,
        )

    @app.get("/robots.txt")
    def robots_txt():
        return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}

    @app.get("/knowledge")
    def knowledge_page():
        stats = get_knowledge_stats()
        return render_template(
            "knowledge.html",
            app_name=settings.APP_NAME,
            stats=stats,
            knowledge_types=ALLOWED_DOCUMENT_TYPES,
        )

    @app.post("/api/knowledge/manual")
    def api_add_manual_knowledge():
        data = request.get_json(silent=True) or {}

        try:
            document = add_manual_knowledge_document(data)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "document": document,
        })

    @app.post("/api/knowledge/upload")
    def api_upload_knowledge_file():
        uploaded_file = request.files.get("file")
        document_type = (request.form.get("document_type") or "").strip()
        title = (request.form.get("title") or "").strip()
        source_url = (request.form.get("source_url") or "").strip()
        document_date = (request.form.get("document_date") or "").strip()

        try:
            extracted = save_temp_file_and_extract(uploaded_file)

            document = add_manual_knowledge_document({
                "document_type": document_type,
                "title": title or extracted["original_filename"],
                "source_url": source_url or extracted["original_filename"],
                "document_date": document_date,
                "content": extracted["text"],
            })
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "document": document,
        })

    @app.get("/settings")
    def settings_page():
        profile = get_lawyer_profile()
        return render_template(
            "settings.html",
            app_name=settings.APP_NAME,
            profile=profile,
        )

    @app.get("/admin/ingest-knowledge")
    def admin_ingest_knowledge():
        token = request.args.get("token")

        if token != settings.INIT_DB_TOKEN:
            return jsonify({"status": "error", "message": "Forbidden"}), 403

        result = ingest_knowledge_base()
        return jsonify(result)

    @app.get("/admin/federal-law-index")
    def admin_federal_law_index():
        token = request.args.get("token")

        if token != settings.INIT_DB_TOKEN:
            return jsonify({"status": "error", "message": "Forbidden"}), 403

        ensure_federal_law_search_indexes()

        return jsonify({
            "status": "ok",
            "message": "Federal law search indexes ensured.",
        })

    @app.get("/admin/federal-law-roles")
    def admin_federal_law_roles():
        token = request.args.get("token")

        if token != settings.INIT_DB_TOKEN:
            return jsonify({"status": "error", "message": "Forbidden"}), 403

        result = refresh_federal_law_roles()
        return jsonify(result)

    @app.get("/admin/core-law-import")
    def admin_core_law_import():
        token = request.args.get("token")

        if token != settings.INIT_DB_TOKEN:
            return jsonify({"status": "error", "message": "Forbidden"}), 403

        result = import_core_law_articles()
        return jsonify(result)


    @app.get("/admin/core-law-index")
    def admin_core_law_index():
        token = request.args.get("token")

        if token != settings.INIT_DB_TOKEN:
            return jsonify({"status": "error", "message": "Forbidden"}), 403

        ensure_core_law_indexes()

        return jsonify({
            "status": "ok",
            "message": "Core law search indexes ensured.",
        })

    @app.get("/admin/cleanup-local-knowledge")
    def admin_cleanup_local_knowledge():
        token = request.args.get("token")

        if token != settings.INIT_DB_TOKEN:
            return jsonify({"status": "error", "message": "Forbidden"}), 403

        keep_types = [
            "00_system_rules",
            "01_scenarios",
            "02_document_templates",
            "03_checklists",
            "05_legal_style",
            "11_template_blueprints",
            "12_intake_forms",
            "13_anonymization_rules",
            "document_template",
            "checklist",
            "real_example",
        ]

        with SessionLocal() as session:
            delete_chunks_result = session.execute(text("""
                DELETE FROM knowledge_chunks
                WHERE document_id IN (
                    SELECT id
                    FROM legal_documents
                    WHERE document_type NOT IN :keep_types
                )
            """), {
                "keep_types": tuple(keep_types),
            })

            delete_documents_result = session.execute(text("""
                DELETE FROM legal_documents
                WHERE document_type NOT IN :keep_types
            """), {
                "keep_types": tuple(keep_types),
            })

            session.commit()

        return jsonify({
            "status": "ok",
            "deleted_chunks": delete_chunks_result.rowcount,
            "deleted_documents": delete_documents_result.rowcount,
            "kept_types": keep_types,
        })

    @app.post("/api/ask")
    def api_ask():
        request_started_at = time.perf_counter()
        timings = {}

        def mark_timing(name: str, started_at: float) -> None:
            timings[name] = round(time.perf_counter() - started_at, 3)

        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()

        if not question:
            return jsonify({
                "status": "error",
                "message": "Question is required",
            }), 400
        reset_openai_usage()
        step_started = time.perf_counter()
        search_queries = generate_legal_search_queries(question)
        mark_timing("generate_search_queries", step_started)

        step_started = time.perf_counter()
        try:
            core_query_embedding = generate_embedding(" ".join(search_queries[:3]))
        except Exception:
            core_query_embedding = []
        mark_timing("generate_embedding", step_started)

        core_law_results = []
        federal_law_candidates = []
        federal_law_results = []
        federal_search_error = ""
        search_route = "core_law"

        try:
            step_started = time.perf_counter()
            core_law_candidates = search_core_law(
                question,
                limit=12,
                expanded_queries=search_queries,
                query_embedding=core_query_embedding,
            )
            mark_timing("core_law_search", step_started)

            if not core_law_candidates:
                core_law_reranked = []
                core_gate = {
                    "is_sufficient": False,
                    "confidence": 1.0,
                    "reason": "Статьи кодексов не найдены.",
                    "federal_search_query": question,
                }
            else:

                step_started = time.perf_counter()
                core_law_reranked = rerank_core_law_sources(
                    user_question=question,
                    sources=core_law_candidates[:15],
                    limit=5,
                )
                mark_timing("core_law_rerank", step_started)

                step_started = time.perf_counter()
                core_gate = assess_core_law_sufficiency(
                    user_question=question,
                    core_sources=core_law_reranked[:5],
                )
                mark_timing("core_law_gate", step_started)

            if is_core_law_sufficient(core_law_reranked) and core_gate.get("is_sufficient"):
                core_law_results = core_law_reranked[:5]
                search_route = "core_law_only"
            else:
                search_route = "core_law_then_federal_law"

                federal_query = core_gate.get("federal_search_query") or question
                federal_expanded_queries = [federal_query] + search_queries

                step_started = time.perf_counter()
                federal_law_candidates = search_federal_law(
                    federal_query,
                    limit=15,
                    expanded_queries=federal_expanded_queries,
                    query_embedding=[],
                )
                mark_timing("federal_law_search", step_started)

                combined_candidates = []

                for item in core_law_reranked[:5]:
                    combined_candidates.append(item)

                for item in federal_law_candidates:
                    combined_candidates.append(item)

                step_started = time.perf_counter()
                federal_law_results = rerank_federal_sources(
                    user_question=question,
                    sources=combined_candidates[:15],
                    limit=5,
                )
                mark_timing("federal_law_rerank", step_started)

        except Exception as error:
            core_law_results = []
            federal_law_candidates = []
            federal_law_results = []
            federal_search_error = str(error)

        step_started = time.perf_counter()
        core_context = build_core_law_context(core_law_results)
        federal_context = build_federal_law_context(federal_law_results)
        local_context = build_knowledge_context([])
        mark_timing("build_context", step_started)

        knowledge_context = "\n\n".join(
            block for block in [core_context, federal_context, local_context] if block
        )

        step_started = time.perf_counter()
        answer = generate_legal_answer(
            user_question=question,
            knowledge_context=knowledge_context,
        )
        mark_timing("generate_answer", step_started)

        all_sources = []

        for item in core_law_results:
            all_sources.append({
                "title": item.get("codex"),
                "document_type": "Статья кодекса",
                "authority": item.get("codex"),
                "document_number": item.get("article_num"),
                "document_date": None,
                "status": "Актуальность требует проверки по официальному источнику",
                "source_url": item.get("source_url") or item.get("url"),
                "rank": float(item.get("rank") or 0),
                "source_group": "core_law",
                "article_title": item.get("article_title"),
                "chapter": item.get("chapter"),
            })

        for item in federal_law_results:
            all_sources.append({
                "title": item.get("title"),
                "document_type": item.get("document_type"),
                "authority": item.get("authority"),
                "document_number": item.get("document_number"),
                "document_date": item.get("document_date"),
                "status": item.get("status"),
                "source_url": item.get("source_url"),
                "rank": float(item.get("rank") or 0),
                "source_group": item.get("source_group") or "federal_law",
            })

        timings["total"] = round(time.perf_counter() - request_started_at, 3)

        print({
            "event": "api_ask_timing",
            "question": question[:120],
            "search_route": search_route,
            "timings": timings,
            "core_law_count": len(core_law_results),
            "federal_candidates_count": len(federal_law_candidates),
            "sources_count": len(all_sources),
        }, flush=True)

        openai_usage = get_openai_usage_summary()

        print({
            "event": "api_ask_openai_usage_total",
            "question": question[:120],
            "search_route": search_route,
            "openai_usage": openai_usage,
        }, flush=True)
        all_sources = all_sources[:5]
        return jsonify({
            "status": "ok",
            "question": question,
            "search_queries": search_queries,
            "search_route": search_route,
            "core_gate": core_gate if "core_gate" in locals() else None,
            "timings": timings,
            "answer": answer,
            "federal_search_error": federal_search_error,
            "core_law_count": len(core_law_results),
            "federal_candidates_count": len(federal_law_candidates),
            "openai_usage": openai_usage,
            "sources": all_sources,
        })

    @app.post("/api/document-builder")
    def api_document_builder():
        data = request.get_json(silent=True) or {}
        user_request = (data.get("request") or "").strip()
        client_id = data.get("client_id") or None
        case_id = data.get("case_id") or None
        previous_data = data.get("previous_data") or None
        answers = data.get("answers") or {}
        selected_template_id = data.get("selected_template_id") or None

        if not user_request:
            return jsonify({
                "status": "error",
                "message": "Request is required",
            }), 400

        selected_client = get_client_by_id(client_id)
        client_context = build_client_context(selected_client)

        result = build_document_from_request(
            user_request=user_request,
            client_context=client_context,
            previous_data=previous_data,
            answers=answers,
            selected_template_id=selected_template_id,
        )

        if selected_client:
            result["client"] = {
                "id": selected_client["id"],
                "full_name": selected_client["full_name"],
            }

        if result.get("status") == "ok" and case_id and result.get("draft"):
            saved_document = save_generated_document({
                "case_id": case_id,
                "document_type": result.get("detected_family") or "draft",
                "title": _build_generated_document_title(result.get("detected_family")),
                "content": result["draft"],
            })

            result["saved_document"] = {
                "id": saved_document["id"],
                "title": saved_document["title"],
            }

        return jsonify(result)

    @app.post("/api/document-builder/docx")
    def api_document_builder_docx():
        data = request.get_json(silent=True) or {}

        content = (data.get("content") or "").strip()
        title = (data.get("title") or "Юридический документ").strip()
        client_name = (data.get("client_name") or "").strip()
        template_id = (data.get("template_id") or "").strip()
        extracted_data = data.get("extracted_data") or {}
        signature_data_url = (data.get("signature_data_url") or "").strip()

        if template_id and extracted_data:
            try:
                file_stream = render_docx_template(
                    template_id=template_id,
                    extracted_data=extracted_data,
                    title=title,
                    client_name=client_name,
                    signature_data_url=signature_data_url,
                )

                return send_file(
                    file_stream,
                    mimetype=DOCX_MIME_TYPE,
                    as_attachment=True,
                    download_name=make_docx_filename(title),
                )
            except FileNotFoundError:
                pass

        if not content:
            return jsonify({
                "status": "error",
                "message": "Нет текста документа для скачивания.",
            }), 400

        file_stream = build_legal_docx(
            content=content,
            title=title,
            client_name=client_name,
        )

        return send_file(
            file_stream,
            mimetype=DOCX_MIME_TYPE,
            as_attachment=True,
            download_name=make_docx_filename(title),
        )
    @app.get("/api/generated-documents/<int:document_id>/docx")
    def api_download_generated_document_docx(document_id: int):
        try:
            document = get_generated_document_by_id(document_id)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 404

        file_stream = build_legal_docx(
            content=document["content"],
            title=document["title"],
        )

        return send_file(
            file_stream,
            mimetype=DOCX_MIME_TYPE,
            as_attachment=True,
            download_name=make_docx_filename(document["title"]),
        )

    @app.post("/api/document-analysis")
    def api_document_analysis():
        data = request.get_json(silent=True) or {}
        document_text = (data.get("document_text") or "").strip()
        case_id = data.get("case_id") or None

        if not document_text:
            return jsonify({
                "status": "error",
                "message": "Document text is required",
            }), 400

        knowledge_results = search_knowledge(document_text[:1000], limit=5)
        knowledge_context = build_knowledge_context(knowledge_results)

        analysis = analyze_legal_document(
            document_text=document_text,
            knowledge_context=knowledge_context,
        )

        saved_analysis = None

        if case_id and analysis:
            saved_analysis = save_generated_document({
                "case_id": case_id,
                "document_type": "analysis",
                "title": "Анализ документа",
                "content": analysis,
            })

        return jsonify({
            "status": "ok",
            "analysis": analysis,
            "saved_analysis": {
                "id": saved_analysis["id"],
                "title": saved_analysis["title"],
            } if saved_analysis else None,
            "sources": [
                {
                    "title": item["title"],
                    "document_type": item["document_type"],
                    "source_url": item["source_url"],
                }
                for item in knowledge_results
            ],
        })

    @app.post("/api/document-analysis/upload")
    def api_document_analysis_upload():
        uploaded_file = request.files.get("file")

        try:
            result = save_temp_file_and_extract(uploaded_file)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "filename": result["original_filename"],
            "text": result["text"],
        })

    @app.post("/api/settings/profile")
    def api_save_lawyer_profile():
        data = request.get_json(silent=True) or {}
        profile = save_lawyer_profile(data)

        return jsonify({
            "status": "ok",
            "profile": profile,
        })

    @app.post("/api/cases")
    def api_create_case():
        data = request.get_json(silent=True) or {}

        try:
            case = create_case(data)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "case": case,
        })


    @app.put("/api/cases/<int:case_id>")
    def api_update_case(case_id: int):
        data = request.get_json(silent=True) or {}

        try:
            case = update_case(case_id, data)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "case": case,
        })


    @app.delete("/api/cases/<int:case_id>")
    def api_delete_case(case_id: int):
        try:
            delete_case(case_id)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 404

        return jsonify({
            "status": "ok",
        })

    @app.post("/api/cases/<int:case_id>/documents")
    def api_upload_case_document(case_id: int):
        uploaded_file = request.files.get("file")

        try:
            document = save_case_file(case_id, uploaded_file)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "document": {
                "id": document["id"],
                "original_filename": document["original_filename"],
                "document_type": document["document_type"],
                "created_at": str(document["created_at"]),
            },
        })


    @app.get("/api/documents/<int:document_id>/download")
    def api_download_case_document(document_id: int):
        try:
            document = get_document_file(document_id)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 404

        return send_file(
            document["path"],
            as_attachment=True,
            download_name=document["original_filename"],
        )

    @app.post("/api/clients")
    def api_create_client():
        data = request.get_json(silent=True) or {}

        try:
            client = create_client(data)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "client": client,
        })


    @app.put("/api/clients/<int:client_id>")
    def api_update_client(client_id: int):
        data = request.get_json(silent=True) or {}

        try:
            client = update_client(client_id, data)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "client": client,
        })


    @app.delete("/api/clients/<int:client_id>")
    def api_delete_client(client_id: int):
        try:
            delete_client(client_id)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 404

        return jsonify({
            "status": "ok",
        })

    @app.post("/api/tasks")
    def api_create_task():
        data = request.get_json(silent=True) or {}

        try:
            task = create_task(data)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "task": task,
        })


    @app.put("/api/tasks/<int:task_id>")
    def api_update_task(task_id: int):
        data = request.get_json(silent=True) or {}

        try:
            task = update_task(task_id, data)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 400

        return jsonify({
            "status": "ok",
            "task": task,
        })


    @app.delete("/api/tasks/<int:task_id>")
    def api_delete_task(task_id: int):
        try:
            delete_task(task_id)
        except ValueError as error:
            return jsonify({
                "status": "error",
                "message": str(error),
            }), 404

        return jsonify({
            "status": "ok",
        })

    def _build_generated_document_title(document_family: str | None) -> str:
        if document_family == "claim":
            return "Претензия"

        if document_family == "lawsuit":
            return "Исковое заявление"

        if document_family == "motion":
            return "Ходатайство"

        if document_family == "response":
            return "Отзыв или возражения"

        if document_family == "appeal":
            return "Апелляционная жалоба"

        if document_family == "cassation":
            return "Кассационная жалоба"

        if document_family == "complaint":
            return "Жалоба"

        return "Юридический документ"

    return app