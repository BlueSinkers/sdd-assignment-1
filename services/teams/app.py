"""Madrid Hoops — Teams microservice entry point.

Configuration (all optional with defaults):
    PORT          listen port                         (default 8000)
    SECRET_KEY    signs bearer tokens                 (default: dev-only)
    DATABASE_URL  mssql+pymssql://user:pass@host:1433/teams
    UI_ORIGIN     CORS allowed origin                 (default http://localhost:8080)
    VERSION       reported in /health                 (default: unknown)
"""
from __future__ import annotations

import logging
import os
import time

from flask import Flask, jsonify, request

import db
from teams.routes import bp as teams_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(*, run_migrations: bool | None = None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-not-secret")
    ui_origin = os.environ.get("UI_ORIGIN", "http://localhost:8080")
    app.config["UI_ORIGIN"] = ui_origin

    if run_migrations is None:
        run_migrations = bool(os.environ.get("DATABASE_URL"))
    if run_migrations:
        try:
            db.migrate()
        except Exception:  # noqa: BLE001 — boot should still expose /health on DB down
            logger.exception("migration failed on startup")


    app.teardown_appcontext(db.close_conn)
    app.register_blueprint(teams_bp)

    @app.after_request
    def apply_cors(response):
        response.headers["Access-Control-Allow-Origin"] = app.config["UI_ORIGIN"]
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.before_request
    def _start_timer():
        request._start_time = time.perf_counter()  # noqa: SLF001

    @app.after_request
    def log_request(response):
        started = getattr(request, "_start_time", None)
        duration_ms = (
            round((time.perf_counter() - started) * 1000, 2) if started is not None else 0
        )
        print(
            f"{request.method} {request.path} {response.status_code} {duration_ms}ms",
            flush=True,
        )
        return response

    @app.get("/health")
    def health():
        version = os.environ.get("VERSION", "unknown")
        db_ok = db.health_check_db()
        body = {
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else "error",
            "version": version,
        }
        return jsonify(body), 200 if db_ok else 503

    @app.route("/api/<path:_any>", methods=["OPTIONS"])
    @app.route("/health", methods=["OPTIONS"])
    def cors_preflight(_any=None):
        return ("", 204)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # 0.0.0.0 so the service is reachable from outside the container.
    create_app().run(host="0.0.0.0", port=port)

