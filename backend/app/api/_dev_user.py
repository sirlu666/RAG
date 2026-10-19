"""**临时替身**：真实鉴权是 C 的 /api/auth。

A 的 6 个文档接口需要一个"当前用户"，因此在 C 上线前用这个函数顶上。
C 接入时：把 `dev_current_user` 换成 JWT 版本（签名相同），删除本文件。

行为：
- 无 Authorization 时用 `dev` 用户；
- 带 `Authorization: Bearer dev:<name>` 时用指定用户名（方便 A 做多用户隔离自测）。
"""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db

DEV_USERNAME = "dev"


def _ensure_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def dev_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    username = DEV_USERNAME
    if authorization and authorization.lower().startswith("bearer dev:"):
        username = authorization.split("dev:", 1)[1].strip() or DEV_USERNAME
    return _ensure_user(db, username)
