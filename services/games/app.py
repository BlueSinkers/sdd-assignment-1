"""Madrid Hoops Games service entry point.

Environment:
    PORT            listen port (default 8000); always binds 0.0.0.0
    DATABASE_URL    SQL Server URL
    SECRET_KEY      shared with Teams for Bearer tokens
    TEAMS_URL       Teams base URL (default http://teams:8000)
    TEAMS_TIMEOUT_S Teams HTTP timeout seconds (default 2)
    UI_ORIGIN       CORS allowed origin (default http://localhost:8080)
    VERSION         git sha for /health
"""
from __future__ import annotations

import logging
import os
import time

from flask import Flask, request

import db
from games.routes import bp as games_bp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(*, run_migrations: bool = True):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-not-secret")
    app.config["UI_ORIGIN"] = os.environ.get("UI_ORIGIN", "http://localhost:8080")

    if run_migrations:
        try:
            db.run_migrations()
        except Exception:  # noqa: BLE001
            logger.exception("migration failed on startup")

    app.teardown_appcontext(db.close_conn)
    app.register_blueprint(games_bp)

    @app.before_request
    def _start_timer():
        request._start_time = time.perf_counter()  # noqa: SLF001

    @app.after_request
    def add_cors_and_log(response):
        response.headers["Access-Control-Allow-Origin"] = app.config["UI_ORIGIN"]
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        started = getattr(request, "_start_time", None)
        duration_ms = (
            round((time.perf_counter() - started) * 1000, 2) if started is not None else 0
        )
        print(
            f"{request.method} {request.path} {response.status_code} {duration_ms}ms",
            flush=True,
        )
        return response

    @app.route("/api/<path:_any>", methods=["OPTIONS"])
    @app.route("/health", methods=["OPTIONS"])
    def cors_preflight(_any=None):
        return ("", 204)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    create_app().run(host="0.0.0.0", port=port)
