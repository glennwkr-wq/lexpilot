from flask import Flask, render_template, jsonify, request

from app.core.config import settings
from app.services.knowledge.ingest import ingest_knowledge_base
from app.services.knowledge.search import search_knowledge, build_knowledge_context
from app.providers.llm.openai import generate_legal_answer

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", app_name=settings.APP_NAME)

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

    return app