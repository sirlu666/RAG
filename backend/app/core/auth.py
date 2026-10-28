"""Password hashing, opaque browser sessions, CSRF and origin checks."""

import hashlib
import hmac
import secrets
import time
from collections import deque
from threading import Lock

from fastapi import Depends, Request
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.core.exceptions import AppError
from app.db.auth_models import AuthSession
from app.db.models import User
from app.db.session import get_db

COOKIE_NAME = "mathrag_session"
PASSWORD_ITERATIONS = 600_000
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=str(ROOT_DIR / ".env"), extra="ignore")
    cookie_secure: bool = False  # Enable for HTTPS deployment; local HTTP cannot send secure cookies.
    session_seconds: int = Field(default=86_400, ge=60, le=2_592_000)


auth_settings = AuthSettings()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != PASSWORD_ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# A missing username still performs the same expensive password check.
DUMMY_PASSWORD = hash_password(secrets.token_urlsafe(24))


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    allowed = {
        str(request.base_url).rstrip("/"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
    if origin and origin not in allowed:
        raise AppError(1003, "请求来源不受信任，请从本站页面操作")


def current_session(request: Request, db: Session) -> AuthSession:
    token = request.cookies.get(COOKIE_NAME, "")
    session = db.get(AuthSession, token_digest(token)) if token and len(token) <= 128 else None
    if session is None or session.expires_at <= int(time.time()):
        raise AppError(1002, "请先登录，或登录已过期")
    return session


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = current_session(request, db)
    if request.method not in SAFE_METHODS:
        check_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied.isascii() or not hmac.compare_digest(supplied, session.csrf_token):
            raise AppError(1003, "请求校验失败，请刷新页面后重试")
    user = db.get(User, session.user_id)
    if user is None or not user.password_hash:
        raise AppError(1002, "登录账号不可用，请重新登录")
    return user


_attempts: dict[str, deque] = {}
_attempt_lock = Lock()


def check_auth_rate(request: Request) -> None:
    """Single-process local deployment: limit password work to 20 requests/min/IP."""
    host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _attempt_lock:
        for key in list(_attempts):
            if not _attempts[key] or _attempts[key][-1] <= now - 60:
                del _attempts[key]
        recent = _attempts.setdefault(host, deque())
        while recent and recent[0] <= now - 60:
            recent.popleft()
        if len(recent) >= 20:
            raise AppError(3001, "登录或注册操作过于频繁，请一分钟后重试")
        recent.append(now)
