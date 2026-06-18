from flask import Flask, render_template

from app.core.config import settings


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.SECRET_KEY

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", app_name=settings.APP_NAME)

    return app