"""Migration preserves old rows and creates a usable, non-overwritten backup."""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine

from app.db.auth_migration import migrate_auth_schema


def test_legacy_migration_backs_up_and_is_idempotent(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT, created_at TEXT)")
        db.execute("INSERT INTO users VALUES ('u_old', 'dev', '2026-10-23')")
        db.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, user_id TEXT)")
        db.execute("INSERT INTO documents VALUES ('doc_old', 'u_old')")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        backup = migrate_auth_schema(engine)
        assert backup and backup.exists()
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT id, username, password_hash FROM users").fetchone() == ("u_old", "dev", None)
            assert db.execute("SELECT id, user_id FROM documents").fetchone() == ("doc_old", "u_old")
        with sqlite3.connect(backup) as db:
            assert "password_hash" not in {row[1] for row in db.execute("PRAGMA table_info(users)")}
            assert db.execute("SELECT id FROM documents").fetchone() == ("doc_old",)
        assert migrate_auth_schema(engine) is None
        assert len(list(backup.parent.iterdir())) == 1
    finally:
        engine.dispose()


def test_empty_database_needs_no_legacy_backup(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    try:
        assert migrate_auth_schema(engine) is None
        assert not (tmp_path / 'backups').exists()
    finally:
        engine.dispose()


def test_backup_captures_committed_wal_rows(tmp_path):
    path = tmp_path / "wal.db"
    source = sqlite3.connect(path)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        source.execute("PRAGMA journal_mode=WAL")
        source.execute("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT)")
        source.execute("INSERT INTO users VALUES ('u_wal', 'kept_in_wal')")
        source.commit()
        assert Path(str(path) + "-wal").exists()
        backup = migrate_auth_schema(engine)
        with sqlite3.connect(backup) as snapshot:
            assert snapshot.execute("SELECT username FROM users").fetchone() == ("kept_in_wal",)
    finally:
        source.close()
        engine.dispose()
