"""Madrid Hoops: entry point.

Start with `python app.py`. Configuration comes only from environment
variables:
    PORT        port to listen on            (default 8000)
    DATA_DIR    folder for the SQLite file   (default ./data)
"""
import os

from flask import Flask

import db


def create_app():
    app = Flask(__name__)
    db.init_db()

    @app.route("/")
    def home():
        return "Madrid Hoops is running."

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # 0.0.0.0, not 127.0.0.1, so the app is reachable from outside a container.
    create_app().run(host="0.0.0.0", port=port)
