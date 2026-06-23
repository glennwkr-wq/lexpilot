from flask import Flask, render_template, jsonify, request
from sqlalchemy import text
from app.core.config import settings
from app.services.knowledge.ingest import ingest_knowledge_base
from app.services.knowledge.manual import (
    ALLOWED_DOCUMENT_TYPES,
    add_manual_knowledge_document,
)
from app.services.knowledge.search import search_knowledge, build_knowledge_context
from app.db.session import SessionLocal
from app.providers.llm.openai import generate_legal_answer, analyze_legal_document
from app.services.documents.builder import build_document_from_request
from app.services.settings_store import get_lawyer_profile, save_lawyer_profile
from app.services.workspace_store import (
    get_dashboard_workspace,
    get_all_cases,
    create_case,
    update_case,
    delete_case,
    get_all_tasks,
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

        return render_template(
            "document_builder.html",
            app_name=settings.APP_NAME,
            clients=clients,
        )

    @app.get("/document-analysis")
    def document_analysis_page():
        return render_template("document_analysis.html", app_name=settings.APP_NAME)

    @app.get("/cases")
    def cases_page():
        cases = get_all_cases()
        tasks = get_all_tasks()
        clients = get_all_clients()

        return render_template(
            "cases.html",
            app_name=settings.APP_NAME,
            cases=cases,
            tasks=tasks,
            clients=clients,
        )

    @app.get("/clients")
    def clients_page():
        clients = get_all_clients()

        return render_template(
            "clients.html",
            app_name=settings.APP_NAME,
            clients=clients,
        )

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

    @app.post("/api/ask")
    def api_ask():
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()

        if not question:
            return jsonify({
                "status": "error",
                "message": "Question is required",
            }), 400

        knowledge_results = search_knowledge(question, limit=5)
        knowledge_context = build_knowledge_context(knowledge_results)

        answer = generate_legal_answer(
            user_question=question,
            knowledge_context=knowledge_context,
        )

        return jsonify({
            "status": "ok",
            "question": question,
            "answer": answer,
            "sources": [
                {
                    "title": item["title"],
                    "document_type": item["document_type"],
                    "source_url": item["source_url"],
                }
                for item in knowledge_results
            ],
        })

    @app.post("/api/document-builder")
    def api_document_builder():
        data = request.get_json(silent=True) or {}
        user_request = (data.get("request") or "").strip()
        client_id = data.get("client_id") or None

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
        )

        if selected_client:
            result["client"] = {
                "id": selected_client["id"],
                "full_name": selected_client["full_name"],
            }

        return jsonify(result)

    @app.post("/api/document-analysis")
    def api_document_analysis():
        data = request.get_json(silent=True) or {}
        document_text = (data.get("document_text") or "").strip()

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

        return jsonify({
            "status": "ok",
            "analysis": analysis,
            "sources": [
                {
                    "title": item["title"],
                    "document_type": item["document_type"],
                    "source_url": item["source_url"],
                }
                for item in knowledge_results
            ],
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

    return app