from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

from app.config import get_settings

_local = threading.local()


def _get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        settings = get_settings()
        db_path = settings.database_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(db_path)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                tconst TEXT NOT NULL,
                title_data TEXT DEFAULT '{}',
                added_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, tconst)
            )
        """)
        _local.conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                jti TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                family_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        try:
            _local.conn.execute("ALTER TABLE watchlist ADD COLUMN notes TEXT")
        except sqlite3.OperationalError:
            pass
        _local.conn.commit()
    return _local.conn


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def store_refresh_token(jti: str, user_id: str, family_id: str, token: str, expires_at: str) -> None:
    db = _get_db()
    db.execute(
        """INSERT INTO refresh_tokens (jti, user_id, family_id, token_hash, expires_at, revoked, created_at)
           VALUES (?, ?, ?, ?, ?, 0, ?)""",
        [jti, user_id, family_id, _hash_token(token), expires_at, datetime.now(timezone.utc).isoformat()],
    )
    db.commit()


def revoke_refresh_token(jti: str) -> None:
    db = _get_db()
    db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE jti = ?", [jti])
    db.commit()


def revoke_token_family(family_id: str) -> None:
    db = _get_db()
    db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE family_id = ?", [family_id])
    db.commit()


def get_refresh_token(jti: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT jti, user_id, family_id, token_hash, expires_at, revoked FROM refresh_tokens WHERE jti = ?",
        [jti],
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_user(email: str, password: str, display_name: str) -> dict:
    db = _get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", [email]).fetchone()
    if existing:
        raise ValueError("Email already registered")
    import uuid
    user_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)
    db.execute(
        "INSERT INTO users (id, email, display_name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        [user_id, email, display_name, pw_hash, now],
    )
    db.commit()
    return {"id": user_id, "email": email, "display_name": display_name, "created_at": now}


def get_user_by_email(email: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT id, email, display_name, password_hash, created_at FROM users WHERE email = ?",
        [email],
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_user_by_id(user_id: str) -> dict | None:
    db = _get_db()
    row = db.execute(
        "SELECT id, email, display_name, created_at FROM users WHERE id = ?",
        [user_id],
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_watchlist(user_id: str) -> list[dict]:
    db = _get_db()
    import json
    try:
        rows = db.execute(
            "SELECT id, tconst, title_data, notes, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
            [user_id],
        ).fetchall()
    except sqlite3.OperationalError:
        rows = db.execute(
            "SELECT id, tconst, title_data, NULL AS notes, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
            [user_id],
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["title"] = json.loads(d.pop("title_data"))
        except (json.JSONDecodeError, TypeError):
            d["title"] = {}
        result.append(d)
    return result


def add_to_watchlist(user_id: str, tconst: str, title: dict | None = None) -> dict:
    db = _get_db()
    import json
    import uuid
    existing = db.execute(
        "SELECT id, tconst, title_data, added_at FROM watchlist WHERE user_id = ? AND tconst = ?",
        [user_id, tconst],
    ).fetchone()
    if existing:
        return dict(existing)
    entry_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc).isoformat()
    title_data = json.dumps(title or {})
    db.execute(
        "INSERT INTO watchlist (id, user_id, tconst, title_data, added_at) VALUES (?, ?, ?, ?, ?)",
        [entry_id, user_id, tconst, title_data, now],
    )
    db.commit()
    return {"id": entry_id, "tconst": tconst, "title": title or {}, "added_at": now}


def remove_from_watchlist(user_id: str, entry_id: str) -> bool:
    db = _get_db()
    cur = db.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND id = ?",
        [user_id, entry_id],
    )
    db.commit()
    return cur.rowcount > 0


def update_watchlist_notes(user_id: str, entry_id: str, notes: str | None) -> bool:
    db = _get_db()
    notes = (notes or "").strip()
    cur = db.execute(
        "UPDATE watchlist SET notes = ? WHERE user_id = ? AND id = ?",
        [notes, user_id, entry_id],
    )
    db.commit()
    return cur.rowcount > 0


def update_user_display_name(user_id: str, display_name: str) -> dict | None:
    db = _get_db()
    display_name = display_name.strip()
    if not 1 <= len(display_name) <= 64:
        raise ValueError("Display name must be 1-64 characters")
    cur = db.execute(
        "UPDATE users SET display_name = ? WHERE id = ?",
        [display_name, user_id],
    )
    db.commit()
    if cur.rowcount == 0:
        return None
    return get_user_by_id(user_id)


def delete_user(user_id: str) -> bool:
    db = _get_db()
    db.execute("DELETE FROM watchlist WHERE user_id = ?", [user_id])
    db.execute("DELETE FROM refresh_tokens WHERE user_id = ?", [user_id])
    cur = db.execute("DELETE FROM users WHERE id = ?", [user_id])
    db.commit()
    return cur.rowcount > 0
