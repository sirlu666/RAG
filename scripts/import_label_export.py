"""Import version-bound, model-authored labels; default is read-only preview.

Never calls a provider, rewrites source files, rebuilds vectors or changes accounts.
The label export and field-only recovery file belong outside Git.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


def validate_tags(tags):
    if not isinstance(tags, dict) or set(tags) != {'knowledge_points', 'question_types', 'difficulty'}:
        raise ValueError('Invalid label fields')
    if tags['difficulty'] not in ('基础', '进阶', '困难'):
        raise ValueError('Invalid difficulty')
    for key, maximum, length in [('knowledge_points', 6, 40), ('question_types', 5, 24)]:
        values = tags[key]
        if not isinstance(values, list) or len(values) > maximum:
            raise ValueError('Invalid label array')
        if any(not isinstance(x, str) or not x.strip() or x != x.strip() or len(x) > length for x in values):
            raise ValueError('Invalid label text')
        if len(set(values)) != len(values):
            raise ValueError('Duplicate label')
    if not tags['knowledge_points'] and not tags['question_types']:
        raise ValueError('Empty label result')
    return tags


def text_digest(db, doc_id):
    body = '\n'.join(row[0] for row in db.execute('SELECT content FROM chunks WHERE doc_id=? ORDER BY seq', (doc_id,)))
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush()
        import os
        os.fsync(output.fileno())


def run(db_path, package, username, *, apply=False, backup_path=None, rollback=False):
    if package.get('schema_version') != 1:
        raise ValueError('Unsupported export schema')
    if rollback and str(Path(db_path).resolve()) != package.get('database'):
        raise ValueError('Recovery file belongs to another database')
    entries = package['items']
    if len({x['doc_id'] for x in entries}) != len(entries):
        raise ValueError('Duplicate document ids')
    if not rollback:
        for entry in entries:
            validate_tags(entry['tags'])
    if apply and not rollback and (not backup_path or Path(backup_path).exists()):
        raise ValueError('A new recovery file path is required')
    db_path = Path(db_path).resolve()
    db = sqlite3.connect(db_path.as_uri() + ('?mode=rw' if apply else '?mode=ro'), uri=True, timeout=15)
    db.row_factory = sqlite3.Row
    report = {'apply': apply, 'rollback': rollback, 'eligible': [], 'skipped': []}
    timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=' ', timespec='microseconds')
    recovery = {'schema_version': 1, 'database': str(db_path), 'items': []}
    try:
        db.execute('BEGIN IMMEDIATE' if apply else 'BEGIN')
        for entry in entries:
            row = db.execute('SELECT d.*,u.username FROM documents d JOIN users u ON u.id=d.user_id WHERE d.id=?',
                             (entry['doc_id'],)).fetchone()
            reason = None
            expected_tags = entry['imported_tags'] if rollback else entry['previous_tags']
            expected_difficulty = entry['imported_difficulty'] if rollback else entry['previous_difficulty']
            expected_time = entry['imported_updated_at'] if rollback else entry['updated_at']
            if row is None or row['username'] != username or entry['username'] != username:
                reason = 'missing_or_wrong_owner'
            elif row['status'] != 'ready':
                reason = 'document_not_ready'
            elif row['content_hash'] != entry['content_hash'] or str(row['updated_at']) != expected_time:
                reason = 'source_version_changed'
            elif row['tags_json'] != expected_tags or row['difficulty'] != expected_difficulty:
                reason = 'labels_changed'
            elif not rollback and row['tags_json'] not in (None, ''):
                reason = 'existing_labels_preserved'
            elif db.execute("SELECT 1 FROM ingest_tasks WHERE doc_id=? AND status IN ('pending','running') LIMIT 1",
                            (entry['doc_id'],)).fetchone():
                reason = 'active_ingestion'
            elif text_digest(db, entry['doc_id']) != entry['parsed_text_sha256']:
                reason = 'parsed_text_changed'
            if reason:
                report['skipped'].append({'doc_id': entry['doc_id'], 'reason': reason})
                continue
            report['eligible'].append(entry['doc_id'])
            encoded = entry['previous_tags'] if rollback else json.dumps(entry['tags'], ensure_ascii=False)
            difficulty = entry['previous_difficulty'] if rollback else entry['tags']['difficulty']
            if not rollback:
                recovery['items'].append({**entry, 'imported_tags': encoded, 'imported_difficulty': difficulty,
                                          'imported_updated_at': timestamp})
            if apply:
                # BEGIN IMMEDIATE keeps source checks and this field-only write atomic.
                db.execute('UPDATE documents SET tags_json=?, difficulty=?, updated_at=? WHERE id=?',
                           (encoded, difficulty, timestamp, entry['doc_id']))
        if apply and not rollback:
            # Durable undo record exists before the transaction can commit.
            write_new(backup_path, recovery)
        if apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    report['eligible_count'] = len(report['eligible'])
    report['skipped_count'] = len(report['skipped'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--rollback', action='store_true', help='Use the field-only recovery file as --labels')
    args = parser.parse_args()
    package = json.loads(args.labels.read_text(encoding='utf-8'))
    report = run(args.db, package, args.user, apply=args.apply, backup_path=args.backup, rollback=args.rollback)
    if args.report:
        write_new(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
