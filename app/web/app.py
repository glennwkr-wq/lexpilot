from flask import Flask, render_template, jsonify, request

from app.core.config import settings
from app.services.knowledge.ingest import ingest_knowledge_base

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

    return app