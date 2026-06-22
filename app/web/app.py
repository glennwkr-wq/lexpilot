from flask import Flask, render_template, jsonify, request
from sqlalchemy import text
from app.core.config import settings
from app.services.knowledge.ingest import ingest_knowledge_base
from app.services.knowledge.search import search_knowledge, build_knowledge_context
from app.db.session import SessionLocal
from app.providers.llm.openai import generate_legal_answer, analyze_legal_document
from app.services.documents.builder import build_document_from_request

def get_knowledge_stats() -> dict:
    with SessionLocal() as session:
        total_documents = session.execute(
            text("SELECT COUNT(*) FROM legal_documents")
        ).scalar_one()

        total_chunks = session.execute(
            text("SELECT COUNT(*) FROM knowledge_chunks")
        ).scalar_one()

        categories = session.execute(
            text("""
                SELECT document_type, COUNT(*) AS count
                FROM legal_documents
                GROUP BY document_type
                ORDER BY count DESC, document_type ASC
            """)
        ).fetchall()

        recent_documents = session.execute(
            text("""
                SELECT title, document_type, source_url
                FROM legal_documents
                ORDER BY id DESC
                LIMIT 12
            """)
        ).fetchall()

    return {
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "categories": categories,
        "recent_documents": recent_documents,
    }

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", app_name=settings.APP_NAME)

    @app.get("/ask")
    def ask_page():
        return render_template("ask.html", app_name=settings.APP_NAME)

    @app.get("/document-builder")
    def document_builder_page():
        return render_template("document_builder.html", app_name=settings.APP_NAME)

    @app.get("/document-analysis")
    def document_analysis_page():
        return render_template("document_analysis.html", app_name=settings.APP_NAME)

    @app.get("/cases")
    def cases_page():
        return render_template("cases.html", app_name=settings.APP_NAME)

    @app.get("/knowledge")
    def knowledge_page():
        stats = get_knowledge_stats()
        return render_template(
            "knowledge.html",
            app_name=settings.APP_NAME,
            stats=stats,
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

        if not user_request:
            return jsonify({
                "status": "error",
                "message": "Request is required",
            }), 400

        result = build_document_from_request(user_request)
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

    return app