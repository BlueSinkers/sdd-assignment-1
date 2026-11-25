"""SQL Server connection and migration runner for the Games service.

DATABASE_URL examples:
  mssql+pymssql://sa:Password@sqlserver:1433/games
  mssql://user:pass@localhost:1433/games
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymssql
from flask import g

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def parse_database_url(url: str | None = None) -> dict:
    raw = url or os.environ.get("DATABASE_URL", "")
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")

    # Accept both mssql+pymssql:// and mssql://
    normalized = raw.replace("mssql+pymssql://", "mssql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in ("mssql", "pymssql"):
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")

    database = (parsed.path or "").lstrip("/")
    if not database:
        raise RuntimeError("DATABASE_URL must include a database name")

    return {
        "server": parsed.hostname or "localhost",
        "port": parsed.port or 1433,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
    }


def connect(url: str | None = None):
    cfg = parse_database_url(url)
    return pymssql.connect(
        server=cfg["server"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        port=cfg["port"],
        login_timeout=5,
        timeout=10,
        as_dict=True,
        autocommit=False,
    )


def get_conn():
    """One connection per web request."""
    if "conn" not in g:
        g.conn = connect()
    return g.conn


def close_conn(exception=None):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def _split_batches(sql: str) -> list[str]:
    """Split a script on GO batch separators (case-insensitive, line alone)."""
    batches, current = [], []
    for line in sql.splitlines():
        if line.strip().upper() == "GO":
            batch = "\n".join(current).strip()
            if batch:
                batches.append(batch)
            current = []
        else:
            current.append(line)
    batch = "\n".join(current).strip()
    if batch:
        batches.append(batch)
    return batches


def _ensure_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'schema_migrations')
            CREATE TABLE schema_migrations (
                version     NVARCHAR(100) NOT NULL PRIMARY KEY,
                applied_at  DATETIME2     NOT NULL CONSTRAINT DF_schema_migrations_applied
                                          DEFAULT SYSUTCDATETIME()
            )
            """
        )
    conn.commit()


def _applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}


def run_migrations(conn=None):
    """Apply pending *.sql files under migrations/ in name order."""
    own_conn = conn is None
    if own_conn:
        conn = connect()
    try:
        _ensure_migrations_table(conn)
        applied = _applied_versions(conn)
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for path in files:
            version = path.name
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                for batch in _split_batches(sql):
                    cur.execute(batch)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def ping(conn=None) -> bool:
    """True if the Games database answers. Used by GET /health."""
    own_conn = conn is None
    if own_conn:
        conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
            return bool(row and row.get("ok") == 1)
    finally:
        if own_conn:
            conn.close()
