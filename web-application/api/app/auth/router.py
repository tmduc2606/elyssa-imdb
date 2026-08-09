from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth.models import (
    add_to_watchlist,
    create_user,
    get_refresh_token,
    get_user_by_email,
    get_user_by_id,
    get_watchlist,
    remove_from_watchlist,
    revoke_token_family,
    verify_password,
)
from app.auth.utils import create_access_token, create_refresh_token, decode_token
from app.cache.rate_limiter import SlidingWindowRateLimiter
from app.config import get_settings

router = APIRouter()

_auth_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)


def check_auth_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not _auth_limiter.check(client_ip):
        raise HTTPException(
            429,
            "Too many attempts. Try again later.",
            headers={"Retry-After": "60"},
        )


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    displayName: str | None = None

    def get_display_name(self) -> str:
        return self.displayName or self.display_name or self.email.split("@")[0]


class LoginRequest(BaseModel):
    email: str
    password: str


class WatchlistAddRequest(BaseModel):
    tconst: str
    title: dict | None = None


@router.post("/register")
async def register(
    body: RegisterRequest,
    response: Response,
    request: Request,
    _=Depends(check_auth_rate_limit),
):
    settings = get_settings()
    display_name = body.get_display_name()
    try:
        user = create_user(body.email, body.password, display_name)
    except ValueError:
        raise HTTPException(409, "Email already registered")
    access_token = create_access_token(user["id"])
    refresh_token, _, _ = create_refresh_token(user["id"])
    secure = settings.secure_cookies and request.url.scheme == "https"
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"accessToken": access_token, "user": user}


@router.post("/login")
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    _=Depends(check_auth_rate_limit),
):
    settings = get_settings()
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    access_token = create_access_token(user["id"])
    refresh_token, _, _ = create_refresh_token(user["id"])
    secure = settings.secure_cookies and request.url.scheme == "https"
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"accessToken": access_token, "user": {k: v for k, v in user.items() if k != "password_hash"}}


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
):
    from datetime import datetime as _dt, timezone as _tz
    settings = get_settings()
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        # No cookie = unauthenticated bootstrap; must NOT consume the
        # rate limit, or every SPA page load would exhaust the auth quota.
        raise HTTPException(401, "Missing refresh token")
    check_auth_rate_limit(request)
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid or expired refresh token")
    jti = payload.get("jti")
    family_id = payload.get("family_id")
    if not jti or not family_id:
        raise HTTPException(401, "Invalid refresh token claims")
    row = get_refresh_token(jti)
    if row is None:
        raise HTTPException(401, "Refresh token not recognized")
    if row["revoked"]:
        # Reuse of a spent token — revoke the whole family
        revoke_token_family(family_id)
        response.delete_cookie("refresh_token")
        raise HTTPException(401, "Refresh token reused; family revoked")
    expires_at = _dt.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=_tz.utc)
    if _dt.now(_tz.utc) > expires_at:
        raise HTTPException(401, "Refresh token expired")
    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(404, "User not found")
    # Rotate: revoke current token, issue new one in the same family
    from app.auth.models import revoke_refresh_token
    revoke_refresh_token(jti)
    new_refresh, _, _ = create_refresh_token(user["id"], family_id=family_id)
    access_token = create_access_token(user["id"])
    secure = settings.secure_cookies and request.url.scheme == "https"
    response.set_cookie(
        "refresh_token",
        new_refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"accessToken": access_token, "user": {k: v for k, v in user.items() if k != "password_hash"}}


@router.post("/logout")
async def logout(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload and payload.get("family_id"):
            revoke_token_family(payload["family_id"])
    response.delete_cookie("refresh_token")
    return {"ok": True}


@router.get("/logout")
async def logout_get(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload and payload.get("family_id"):
            revoke_token_family(payload["family_id"])
    response.delete_cookie("refresh_token")
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    payload = decode_token(auth[7:])
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.get("/watchlist")
async def watchlist_get(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    payload = decode_token(auth[7:])
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    return get_watchlist(payload["sub"])


@router.post("/watchlist")
async def watchlist_add(request: Request, body: WatchlistAddRequest):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    payload = decode_token(auth[7:])
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    return add_to_watchlist(payload["sub"], body.tconst, body.title)


@router.delete("/watchlist/{entry_id}")
async def watchlist_remove(request: Request, entry_id: str):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    payload = decode_token(auth[7:])
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    removed = remove_from_watchlist(payload["sub"], entry_id)
    if not removed:
        raise HTTPException(404, "Title not in watchlist")
    return {"ok": True}
