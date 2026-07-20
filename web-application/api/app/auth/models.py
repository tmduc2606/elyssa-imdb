from __future__ import annotations

from datetime import datetime, timezone

import bcrypt

_in_memory_users: dict[str, dict] = {}
_in_memory_watchlists: dict[str, list[dict]] = {}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_user(email: str, password: str, display_name: str) -> dict:
    user_id = f"user_{len(_in_memory_users) + 1}"
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "password_hash": hash_password(password),
        "created_at": now,
    }
    _in_memory_users[email] = user
    _in_memory_watchlists[user_id] = []
    return {k: v for k, v in user.items() if k != "password_hash"}


def get_user_by_email(email: str) -> dict | None:
    return _in_memory_users.get(email)


def get_user_by_id(user_id: str) -> dict | None:
    for u in _in_memory_users.values():
        if u["id"] == user_id:
            return {k: v for k, v in u.items() if k != "password_hash"}
    return None


def get_watchlist(user_id: str) -> list[dict]:
    return _in_memory_watchlists.get(user_id, [])


def add_to_watchlist(user_id: str, tconst: str, title: dict | None = None) -> dict:
    wl = _in_memory_watchlists.setdefault(user_id, [])
    existing = next((x for x in wl if x["tconst"] == tconst), None)
    if existing:
        return existing
    entry = {
        "id": f"wl_{len(wl) + 1}",
        "tconst": tconst,
        "title": title or {},
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    wl.append(entry)
    return entry


def remove_from_watchlist(user_id: str, entry_id: str) -> bool:
    wl = _in_memory_watchlists.get(user_id, [])
    before = len(wl)
    _in_memory_watchlists[user_id] = [x for x in wl if x["id"] != entry_id]
    return len(_in_memory_watchlists[user_id]) < before
