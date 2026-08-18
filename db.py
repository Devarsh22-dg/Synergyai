"""Storage abstraction for ScopeForge's user accounts.

The rest of the app (auth.py) only calls the functions below — it never
touches SQL or a file path directly. That boundary is deliberate: today this
is backed by a local SQLite file (free, zero-setup, good for development and
testing), but SQLite's file is NOT persistent on Streamlit Community Cloud
(its filesystem is ephemeral and gets wiped on every redeploy). Moving to a
real backend — Postgres, Supabase, a client's own SQL instance — later means
writing one new class that implements the same functions below and pointing
get_storage() at it. Nothing in auth.py or synergyai_app.py should need to
change.

Schema (users):
    id, username, email, password_hash, email_verified (0/1, currently always
    set true at signup — email OTP verification was removed 2026-08-17),
    mfa_enabled (0/1, reserved for a future phase), created_at
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("SCOPEFORGE_DB_PATH", os.path.join(os.path.dirname(__file__), "scopeforge.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email_verified INTEGER NOT NULL DEFAULT 0,
    mfa_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.executescript(SCHEMA)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# --- Users ---

def create_user(username, email, password_hash):
    """Creates an unverified user (email_verified=0). Raises sqlite3.IntegrityError
    if the username or email is already taken — callers should catch this and show
    a friendly message rather than letting it surface raw."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, email_verified, mfa_enabled, created_at) "
            "VALUES (?, ?, ?, 0, 0, ?)",
            (username, email, password_hash, _now_iso()),
        )
        return cur.lastrowid


def update_pending_user(user_id, username, password_hash):
    """Updates an unverified account's username/password — handles a
    pre-existing unverified row left over from before email OTP verification
    was removed, or a create_user() that partially failed previously. Only
    ever call this on a row where email_verified = 0; verified accounts must
    not be silently modified this way."""
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET username = ?, password_hash = ? WHERE id = ? AND email_verified = 0",
            (username, password_hash, user_id),
        )


def get_user_by_username(username):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def mark_email_verified(user_id):
    with _connect() as conn:
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,))


def get_all_verified_users():
    """Used to build the credentials dict streamlit-authenticator needs at login time."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM users WHERE email_verified = 1").fetchall()
        return [dict(r) for r in rows]
