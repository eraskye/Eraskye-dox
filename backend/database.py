import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "cloviss.db")


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@contextmanager
def db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses (
                key          TEXT PRIMARY KEY,
                created_at   TEXT NOT NULL,
                expires_at   TEXT,
                duration     INTEGER NOT NULL,
                device_id    TEXT,
                status       TEXT NOT NULL DEFAULT 'unused',
                activated_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status)"
        )
