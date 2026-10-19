"""鉴权依赖 —— **这是 C 的职责，这里是 A 联调用的开发占位实现**。

TODO(C)：用 JWT 实现替换本文件，保持函数签名不变：
    get_current_user(db=Depends(get_db), creds=Depends(bearer)) -> User
替换后 A 的 /api/docs/* 无需改动。

开发期行为：
- 带 `Authorization: Bearer dev:<id>` 时用该 id；
- 不带时固定用 `dev` 用户（首次访问自动创建）。
"""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db

DEV_USERNAME = "dev"


def _ensure_dev_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = User(username=username, nickname=username, password_hash="!dev-no-login")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    username = DEV_USERNAME
    if authorization and authorization.lower().startswith("bearer dev:"):
        username = authorization.split("dev:", 1)[1].strip() or DEV_USERNAME
    return _ensure_dev_user(db, username)
