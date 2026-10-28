import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

spec = importlib.util.spec_from_file_location('label_export_import', Path(__file__).resolve().parents[2] / 'scripts/import_label_export.py')
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


@pytest.fixture
def label_db(tmp_path):
    path = tmp_path / 'labels.db'
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE users(id TEXT PRIMARY KEY, username TEXT);
            CREATE TABLE documents(id TEXT PRIMARY KEY, user_id TEXT, content_hash TEXT, updated_at TEXT,
                                   tags_json TEXT, difficulty TEXT, status TEXT);
            CREATE TABLE chunks(doc_id TEXT, content TEXT, seq INTEGER);
            CREATE TABLE ingest_tasks(doc_id TEXT, status TEXT);
            INSERT INTO users VALUES ('u', 'alice');
            INSERT INTO documents VALUES ('d', 'u', 'hash', 'old', NULL, NULL, 'ready');
            INSERT INTO chunks VALUES ('d', 'source text', 0);
        ''')
    entry = {'doc_id': 'd', 'username': 'alice', 'content_hash': 'hash', 'updated_at': 'old',
             'previous_tags': None, 'previous_difficulty': None,
             'parsed_text_sha256': hashlib.sha256(b'source text').hexdigest(),
             'tags': {'knowledge_points': ['导数'], 'question_types': ['计算题'], 'difficulty': '基础'}}
    return path, {'schema_version': 1, 'items': [entry]}


def test_preview_apply_and_field_only_rollback(label_db, tmp_path):
    path, package = label_db
    backup = tmp_path / 'backup.json'
    assert importer.run(path, package, 'alice')['eligible_count'] == 1
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT tags_json FROM documents').fetchone()[0] is None
    assert importer.run(path, package, 'alice', apply=True, backup_path=backup)['eligible_count'] == 1
    assert importer.run(path, package, 'alice')['eligible_count'] == 0
    recovery = json.loads(backup.read_text(encoding='utf-8'))
    with pytest.raises(ValueError):
        importer.run(path, package, 'alice', apply=True, backup_path=backup)
    assert importer.run(path, recovery, 'alice', apply=True, rollback=True)['eligible_count'] == 1
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT tags_json, difficulty FROM documents').fetchone() == (None, None)
        assert db.execute('SELECT content FROM chunks').fetchone()[0] == 'source text'


@pytest.mark.parametrize('change,reason', [
    ("UPDATE documents SET content_hash='new'", 'source_version_changed'),
    ("UPDATE chunks SET content='new'", 'parsed_text_changed'),
    ("UPDATE documents SET tags_json='{}'", 'labels_changed'),
    ("INSERT INTO ingest_tasks VALUES ('d', 'running')", 'active_ingestion'),
])
def test_source_or_label_changes_and_active_jobs_are_skipped(label_db, change, reason):
    path, package = label_db
    with sqlite3.connect(path) as db:
        db.execute(change)
    report = importer.run(path, package, 'alice')
    assert report['eligible_count'] == 0
    assert report['skipped'][0]['reason'] == reason


def test_wrong_owner_and_invalid_labels(label_db):
    path, package = label_db
    assert importer.run(path, package, 'bob')['eligible_count'] == 0
    package['items'][0]['tags']['difficulty'] = 'invalid'
    with pytest.raises(ValueError):
        importer.run(path, package, 'alice')
