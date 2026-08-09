from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, family_id: str | None = None) -> tuple[str, str, str]:
    """Create a refresh token, persist it, and return (token, jti, family_id).

    If ``family_id`` is None a new token family is started (login/register).
    Pass an existing ``family_id`` to rotate within the same family (refresh).
    """
    import uuid
    settings = get_settings()
    jti = str(uuid.uuid4())
    if family_id is None:
        family_id = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_days)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "jti": jti,
        "family_id": family_id,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    from app.auth.models import store_refresh_token
    store_refresh_token(jti, user_id, family_id, token, expire.isoformat())
    return token, jti, family_id


def decode_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
