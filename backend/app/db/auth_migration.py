"""Add the nullable password column, backing up legacy SQLite with its WAL first."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, inspect

logger = logging.getLogger("mathrag.migration")


def migrate_auth_schema(engine: Engine) -> Path | None:
    if not inspect(engine).has_table("users"):
        return None
    if "password_hash" in {column["name"] for column in inspect(engine).get_columns("users")}:
        return None
    if engine.dialect.name != "sqlite" or not engine.url.database:
        raise RuntimeError("Legacy auth migration currently requires a file-backed SQLite database")

    database = Path(engine.url.database)
    backup_dir = database.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"{database.stem}.pre-auth.{stamp}.{uuid4().hex[:8]}.sqlite3"
    # Reserve a new path; never overwrite a previous backup.
    with backup.open("xb"):
        pass
    with sqlite3.connect(str(database)) as source, sqlite3.connect(str(backup)) as target:
        source.backup(target)
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE users ADD COLUMN password_hash TEXT")
    logger.info("Added users.password_hash; pre-migration snapshot: %s", backup)
    return backup
