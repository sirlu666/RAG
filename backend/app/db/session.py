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
    _migrate_messages_related()


def _migrate_messages_related() -> None:
    """幂等补列：create_all 不会 ALTER 旧库，这里给 messages 表补 related 列。

    只做一次判断 + 补列，SQLite 下 ADD COLUMN 幂等安全；新库 create_all 已含该列则跳过。
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "messages" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("messages")}
    if "related" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE messages ADD COLUMN related text DEFAULT '{}'"))


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
