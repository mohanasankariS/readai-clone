"""
Minimal persistence layer. Uses SQLite for the MVP so you can run this
with zero external setup. Swap this file for a Postgres/SQLAlchemy
version when you're ready to deploy for real (see README).
"""
import sqlite3
import json
from contextlib import contextmanager

DB_PATH = "meetings.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                bot_id TEXT PRIMARY KEY,
                meeting_url TEXT,
                status TEXT,
                transcript TEXT,
                summary TEXT,
                action_items TEXT,
                highlights TEXT
            )
        """)


def save_meeting(bot_id, meeting_url=None, status=None, transcript=None,
                  summary=None, action_items=None, highlights=None):
    init_db()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM meetings WHERE bot_id = ?", (bot_id,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE meetings SET
                    status = COALESCE(?, status),
                    transcript = COALESCE(?, transcript),
                    summary = COALESCE(?, summary),
                    action_items = COALESCE(?, action_items),
                    highlights = COALESCE(?, highlights)
                WHERE bot_id = ?
            """, (status, transcript,
                  json.dumps(summary) if summary else None,
                  json.dumps(action_items) if action_items else None,
                  json.dumps(highlights) if highlights else None,
                  bot_id))
        else:
            conn.execute("""
                INSERT INTO meetings (bot_id, meeting_url, status, transcript,
                                       summary, action_items, highlights)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (bot_id, meeting_url, status, transcript,
                  json.dumps(summary) if summary else None,
                  json.dumps(action_items) if action_items else None,
                  json.dumps(highlights) if highlights else None))


def get_meeting(bot_id):
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM meetings WHERE bot_id = ?", (bot_id,)
        ).fetchone()
        return dict(row) if row else None


def list_meetings():
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM meetings").fetchall()
        return [dict(r) for r in rows]