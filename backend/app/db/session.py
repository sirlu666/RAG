"""数据库连接。

SQLite 说明：
- 开 WAL，允许"一写多读"，避免上传时问答被锁死；
- check_same_thread=False 供 BackgroundTasks 线程使用；
- 同一时刻只允许一个入库任务（services/doc_service 里的单写锁）。
"""

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base

settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.sqlite_path}",
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """给后台任务/脚本用：自己开自己关。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ensure_dirs() -> None:
    for path in (settings.upload_path, settings.chroma_path, Path(settings.sqlite_path).parent):
        path.mkdir(parents=True, exist_ok=True)
