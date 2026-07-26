from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth.models import (
    add_to_watchlist,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_watchlist,
    remove_from_watchlist,
    verify_password,
)
from app.auth.utils import create_access_token, create_refresh_token, decode_token
from app.config import get_settings

router = APIRouter()


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
async def register(body: RegisterRequest, response: Response):
    settings = get_settings()
    display_name = body.get_display_name()
    try:
        user = create_user(body.email, body.password, display_name)
    except ValueError:
        raise HTTPException(409, "Email already registered")
    access_token = create_access_token(user["id"])
    refresh_token = create_refresh_token(user["id"])
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"accessToken": access_token, "user": user}


@router.post("/login")
async def login(request: Request, body: LoginRequest, response: Response):
    settings = get_settings()
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    access_token = create_access_token(user["id"])
    refresh_token = create_refresh_token(user["id"])
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
async def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Missing refresh token")
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid or expired refresh token")
    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(404, "User not found")
    access_token = create_access_token(user["id"])
    return {"accessToken": access_token, "user": {k: v for k, v in user.items() if k != "password_hash"}}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"ok": True}


@router.get("/logout")
async def logout_get(response: Response):
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
