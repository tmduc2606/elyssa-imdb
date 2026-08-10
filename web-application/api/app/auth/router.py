from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth.models import (
    add_to_watchlist,
    create_user,
    delete_user,
    get_refresh_token,
    get_user_by_email,
    get_user_by_id,
    get_watchlist,
    remove_from_watchlist,
    revoke_token_family,
    update_user_display_name,
    update_watchlist_notes,
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
    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(404, "User not found")
    if row["revoked"]:
        # Reuse of a spent token. Distinguish a legitimate rotation race
        # (two tabs refreshing in parallel) from theft/logout: within the
        # grace window after the family's last issuance AND while the newest
        # family token is still active, re-issue rather than revoking.
        from datetime import datetime as _dt2, timedelta as _td, timezone as _tz2
        from app.auth.models import revoke_refresh_token, _get_db as _auth_db
        grace = settings.refresh_reuse_grace_seconds
        last_row = _auth_db().execute(
            "SELECT created_at, revoked AS last_revoked FROM refresh_tokens "
            "WHERE family_id = ? ORDER BY created_at DESC LIMIT 1",
            [family_id],
        ).fetchone()
        issued_at = None
        last_active = False
        if last_row:
            last_active = not last_row["last_revoked"]
            try:
                issued_at = _dt2.fromisoformat(last_row["created_at"])
                if issued_at.tzinfo is None:
                    issued_at = issued_at.replace(tzinfo=_tz2.utc)
            except (TypeError, ValueError):
                issued_at = None
        is_race = (
            last_active
            and issued_at is not None
            and (_dt2.now(_tz2.utc) - issued_at) <= _td(seconds=grace)
        )
        if is_race:
            # Rotation race — this token was already spent by a sibling call;
            # issue a fresh token in the same family without nuking it.
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
        revoke_token_family(family_id)
        response.delete_cookie("refresh_token")
        raise HTTPException(401, "Refresh token reused; family revoked")
    expires_at = _dt.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=_tz.utc)
    if _dt.now(_tz.utc) > expires_at:
        raise HTTPException(401, "Refresh token expired")
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
    if get_user_by_id(payload["sub"]) is None:
        raise HTTPException(404, "User not found")
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


class UpdateMeRequest(BaseModel):
    display_name: str | None = None
    displayName: str | None = None


@router.patch("/me")
async def update_me(request: Request, body: UpdateMeRequest):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    payload = decode_token(auth[7:])
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    display_name = body.displayName or body.display_name
    if display_name is None:
        raise HTTPException(422, "display_name is required")
    try:
        user = update_user_display_name(payload["sub"], display_name)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if user is None:
        raise HTTPException(404, "User not found")
    return user


class DeleteAccountRequest(BaseModel):
    confirm: str


@router.delete("/account")
async def delete_account(request: Request, body: DeleteAccountRequest):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    payload = decode_token(auth[7:])
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    if body.confirm != "DELETE":
        raise HTTPException(422, "Confirmation body must be {\"confirm\": \"DELETE\"}")
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        rp = decode_token(refresh_token)
        if rp and rp.get("family_id"):
            revoke_token_family(rp["family_id"])
    deleted = delete_user(payload["sub"])
    if not deleted:
        raise HTTPException(404, "User not found")
    response = Response(status_code=204)
    response.delete_cookie("refresh_token")
    return response


class UpdateWatchlistNotesRequest(BaseModel):
    notes: str | None = None


@router.patch("/watchlist/{entry_id}")
async def watchlist_update_notes(request: Request, entry_id: str, body: UpdateWatchlistNotesRequest):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid token")
    payload = decode_token(auth[7:])
    if payload is None:
        raise HTTPException(401, "Invalid or expired token")
    notes = (body.notes or "").strip()
    if len(notes) > 4000:
        raise HTTPException(422, "Notes must be at most 4000 characters")
    updated = update_watchlist_notes(payload["sub"], entry_id, notes)
    if not updated:
        raise HTTPException(404, "Watchlist entry not found")
    return {"ok": True, "notes": notes}
