"""C: registration, login, session restoration, server-side logout."""

import re
import secrets
import time
from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import (
    COOKIE_NAME, DUMMY_PASSWORD, auth_settings, check_auth_rate, check_origin,
    current_session, get_current_user, hash_password, token_digest, verify_password,
)
from app.core.exceptions import AppError, ok
from app.db.auth_models import AuthSession
from app.db.models import User, UserProfile, UserAvatar, UserAppearance, UserFont
from app.db.session import get_db
from app.services.profile_avatar import MAX_AVATAR_BYTES, save_avatar

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: SecretStr

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9_\u4e00-\u9fff]{3,32}", value):
            raise ValueError("用户名需为 3–32 位中文、字母、数字或下划线")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        if not 8 <= len(value.get_secret_value()) <= 128:
            raise ValueError("密码长度需为 8–128 位")
        return value


class NicknameEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nickname: str = Field(max_length=30)

    @field_validator('nickname')
    @classmethod
    def validate_nickname(cls, value):
        if any(ord(char) < 32 or 127 <= ord(char) <= 159 or char in '\u2028\u2029' for char in value):
            raise ValueError('昵称不能包含换行或控制字符')
        return value.strip()


class ThemeEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    theme: Literal['default', 'light', 'dark']


class FontEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    font: Literal['default', 'song', 'kai']


def public_user(user: User, db: Session) -> dict:
    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    profile = db.get(UserProfile, user.id)
    avatar = db.get(UserAvatar, user.id)
    appearance = db.get(UserAppearance, user.id)
    font = db.get(UserFont, user.id)
    return {"id": user.id, "username": user.username, "nickname": profile.nickname if profile else '',
            "avatar_url": f'/api/auth/me/avatar?v={avatar.revision}' if avatar else None,
            "theme": appearance.theme if appearance else 'default',
            "font": font.font if font else 'default',
            "created_at": created_at.isoformat()}


def start_session(request: Request, response: Response, db: Session, user: User) -> dict:
    previous = request.cookies.get(COOKIE_NAME)
    if previous:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_digest(previous)))
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= int(time.time())))
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    db.add(AuthSession(token_hash=token_digest(token), user_id=user.id, csrf_token=csrf_token,
                       expires_at=int(time.time()) + auth_settings.session_seconds))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=auth_settings.session_seconds,
                        httponly=True, secure=auth_settings.cookie_secure, samesite="lax", path="/api")
    response.headers["Cache-Control"] = "no-store"
    return ok({"user": public_user(user, db), "csrf_token": csrf_token})


@router.post("/register", summary="注册并登录")
def register(credentials: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    check_origin(request)
    check_auth_rate(request)
    user = User(username=credentials.username, password_hash=hash_password(credentials.password.get_secret_value()))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(1005, "用户名已存在，请换一个或直接登录") from exc
    return start_session(request, response, db, user)


@router.post("/login", summary="登录")
def login(credentials: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    check_origin(request)
    check_auth_rate(request)
    user = db.query(User).filter(User.username == credentials.username).first()
    valid = verify_password(credentials.password.get_secret_value(), user.password_hash if user and user.password_hash else DUMMY_PASSWORD)
    if not valid or user is None or not user.password_hash:
        raise AppError(1002, "用户名或密码错误")
    return start_session(request, response, db, user)


@router.get("/me", summary="恢复当前登录状态")
def me(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return ok({"user": public_user(user, db), "csrf_token": current_session(request, db).csrf_token})


@router.patch('/me', summary='修改当前账号昵称')
def update_nickname(body: NicknameEdit, response: Response, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    profile.nickname = body.nickname
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return ok({'user': public_user(user, db)})


@router.patch('/me/theme', summary='保存当前账号主题')
def update_theme(body: ThemeEdit, response: Response, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    appearance = db.get(UserAppearance, user.id)
    if appearance is None:
        appearance = UserAppearance(user_id=user.id)
        db.add(appearance)
    appearance.theme = body.theme
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return ok({'user': public_user(user, db)})


@router.patch('/me/font', summary='保存当前账号字体')
def update_font(body: FontEdit, response: Response, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    preference = db.get(UserFont, user.id)
    if preference is None:
        preference = UserFont(user_id=user.id)
        db.add(preference)
    preference.font = body.font
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return ok({'user': public_user(user, db)})


@router.get('/me/avatar', summary='读取当前账号头像')
def get_avatar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    avatar = db.get(UserAvatar, user.id)
    if avatar is None:
        raise AppError(1004, '尚未设置头像')
    return Response(content=avatar.content, media_type='image/png',
                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.post('/me/avatar', summary='上传并保存当前账号头像')
def upload_avatar(response: Response, file: UploadFile = File(...),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    raw = file.file.read(MAX_AVATAR_BYTES + 1)
    save_avatar(db, user, file.filename or '', raw)
    response.headers['Cache-Control'] = 'no-store'
    return ok({'user': public_user(user, db)})


@router.delete('/me/avatar', summary='恢复当前账号默认头像')
def remove_avatar(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    avatar = db.get(UserAvatar, user.id)
    if avatar is not None:
        db.delete(avatar)
        db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return ok({'user': public_user(user, db)})


@router.post("/logout", summary="退出并撤销当前会话")
def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = current_session(request, db)
    db.delete(session)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api", httponly=True, secure=auth_settings.cookie_secure, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return ok({"logged_out": True})
