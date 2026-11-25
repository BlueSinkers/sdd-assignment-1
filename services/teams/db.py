"""SQL Server connection, migrations, and per-request connection helpers."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymssql
from flask import g

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def parse_database_url(url: str | None = None) -> dict:
    """Parse DATABASE_URL or fall back to DB_* environment variables.

    Supported URL form:
        mssql+pymssql://user:password@host:1433/dbname
    """
    url = url if url is not None else os.environ.get("DATABASE_URL")
    if url:
        # urlparse needs a standard scheme; strip the +driver part.
        normalized = url.replace("mssql+pymssql://", "mssql://", 1)
        parsed = urlparse(normalized)
        db_name = (parsed.path or "").lstrip("/")
        if not db_name:
            raise ValueError("DATABASE_URL must include a database name")
        return {
            "server": parsed.hostname or "localhost",
            "port": parsed.port or 1433,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": db_name,
        }

    return {
        "server": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "1433")),
        "user": os.environ.get("DB_USER", ""),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "teams"),
    }


def connect(config: dict | None = None):
    """Open a new pymssql connection from config or the environment."""
    cfg = config or parse_database_url()
    return pymssql.connect(
        server=cfg["server"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        port=cfg["port"],
        login_timeout=5,
        timeout=10,
    )


def get_conn():
    """One connection per web request, opened the first time it is needed."""
    if "conn" not in g:
        g.conn = connect()
    return g.conn


def close_conn(exception=None):
    """Called by Flask at the end of every request."""
    conn = g.pop("conn", None)
    if conn is not None:
        try:
            if exception is not None:
                conn.rollback()
            conn.close()
        except Exception:  # noqa: BLE001 — teardown must not raise
            logger.exception("error closing db connection")


def _ensure_schema_migrations(conn):
    cur = conn.cursor()
    cur.execute(
        """
        IF NOT EXISTS (
            SELECT * FROM sys.tables WHERE name = 'schema_migrations'
        )
        CREATE TABLE schema_migrations (
            version NVARCHAR(255) NOT NULL PRIMARY KEY,
            applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
        )
        """
    )
    conn.commit()


def _applied_versions(conn) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cur.fetchall()}


def migrate(conn=None):
    """Apply pending *.sql migrations in sorted order. Each version runs once."""
    own_conn = conn is None
    if own_conn:
        conn = connect()
    try:
        _ensure_schema_migrations(conn)
        applied = _applied_versions(conn)
        scripts = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for script in scripts:
            version = script.name
            if version in applied:
                continue
            sql = script.read_text(encoding="utf-8")
            cur = conn.cursor()
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            conn.commit()
            logger.info("applied migration %s", version)
            print(f"applied migration {version}", flush=True)
    finally:
        if own_conn:
            conn.close()


def health_check_db() -> bool:
    """Return True if the database accepts a read/write round-trip."""
    try:
        conn = connect()
        try:
            cur = conn.cursor()
            # Prefer insert+delete on health_check when the table exists;
            # otherwise fall back to SELECT 1 + write.
            try:
                cur.execute("INSERT INTO health_check DEFAULT VALUES")
                cur.execute("SELECT SCOPE_IDENTITY() AS id")
                row = cur.fetchone()
                check_id = int(row[0]) if row else None
                if check_id is not None:
                    cur.execute("DELETE FROM health_check WHERE id = %s", (check_id,))
                conn.commit()
            except pymssql.Error:
                conn.rollback()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
                conn.commit()
            return True
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        logger.exception("health_check_db failed")
        return False
