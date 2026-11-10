"""Madrid Hoops Games service: entry point.

Start with `python app.py`. Configuration comes only from environment
variables:
    PORT        port to listen on                     (default 8000)
    DATA_DIR    folder for the SQLite file            (default ./data)
    SECRET_KEY  signs the login cookie; set it for real use
                                                      (default: a dev-only value)
    TEAMS_URL   base URL of the Teams service         (default http://localhost:8001)
    TEAMS_TIMEOUT_S  seconds to wait for Teams        (default 2)
"""
import os

from flask import Flask

import db
from games.routes import bp as games_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-not-secret")

    db.init_db()
    app.teardown_appcontext(db.close_conn)

    app.register_blueprint(games_bp)

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # 0.0.0.0, not 127.0.0.1, so the app is reachable from outside a container.
    create_app().run(host="0.0.0.0", port=port)
