"""Image corrections preserve original bytes and atomically replace searchable text."""
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.core import auth
from app.core.config import settings
from app.db.models import Document, DocumentOcrText
from app.db.session import SessionLocal
from app.rag.vectorstore import get_store
from app.services import document_text
from app.services.parsing import ocr

OLD = '已知长方形长为六宽为四求面积'
NEW = '已知长方形长为八宽为五求面积'


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    auth._attempts.clear()


def login(browser):
    response = browser.post('/api/auth/register', json={
        'username': 'ocr_' + uuid4().hex[:10], 'password': 'Ocr-learning-2026',
    })
    assert response.status_code == 200, response.text
    return {'X-CSRF-Token': response.json()['data']['csrf_token']}


def setup_image(browser, monkeypatch, extension='png'):
    stream = BytesIO()
    Image.new('RGB', (120, 60), 'white').save(stream, format='PNG' if extension == 'png' else 'JPEG')
    raw = stream.getvalue()
    monkeypatch.setattr(settings, 'ocr_enable', True)
    monkeypatch.setattr(ocr, 'ocr_image_pages', lambda path: [(1, OLD)])
    headers = login(browser)
    response = browser.post('/api/docs/upload', files={'file': ('practice.' + extension, raw)}, headers=headers)
    assert response.status_code == 200, response.text
    doc_id = response.json()['data']['doc_id']
    url = f'/api/docs/{doc_id}/text'
    old = browser.get(url)
    assert old.status_code == 200, old.text
    return headers, doc_id, url, old.json()['data'], raw


@pytest.mark.parametrize('extension', ['png', 'jpg', 'jpeg'])
def test_correction_updates_index_keeps_image_and_checks_versions(browser, monkeypatch, extension):
    headers, doc_id, url, old, raw = setup_image(browser, monkeypatch, extension)
    before = get_store().snapshot_doc(doc_id)
    response = browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers)
    assert response.status_code == 200, response.text
    fresh = browser.get(url).json()['data']
    assert fresh['content'] == NEW and fresh['version'] != old['version']
    assert response.json()['data']['version'] == fresh['version']
    assert browser.get(f'/api/docs/{doc_id}/file').content == raw
    preview = browser.get(f'/api/docs/{doc_id}/preview').json()['data']
    assert NEW in str(preview) and OLD not in str(preview)
    assert all(item['d'] == NEW for item in get_store().snapshot_doc(doc_id))
    assert not ({item['id'] for item in before} & get_store().ids())
    assert browser.put(url, json={'content': OLD, 'version': old['version']}, headers=headers).status_code == 409
    assert browser.put(url, json={'content': NEW, 'version': fresh['version']}, headers=headers).json()['data']['changed'] is False
    assert browser.put(url, json={'content': '太短', 'version': fresh['version']}, headers=headers).status_code == 422
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        assert Path(doc.stored_path).read_bytes() == raw
        backups = list((Path(doc.stored_path).parent / '.versions' / doc_id).glob('*/index.json'))
        assert len(backups) == 1 and OLD in backups[0].read_text(encoding='utf-8')
    # Reindex must use saved corrections rather than rerun OCR and discard them.
    assert browser.post(f'/api/docs/{doc_id}/reindex', headers=headers).status_code == 200
    assert browser.get(url).json()['data']['content'] == NEW
    assert NEW in browser.get(f'/api/docs/{doc_id}/preview').text
    assert browser.delete(f'/api/docs/{doc_id}', headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.get(DocumentOcrText, doc_id) is None


@pytest.mark.parametrize('failure', ['embedding', 'vector', 'database'])
def test_failed_correction_preserves_previous_correction(browser, monkeypatch, failure):
    headers, doc_id, url, old, raw = setup_image(browser, monkeypatch)
    assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers).status_code == 200
    fresh = browser.get(url).json()['data']
    store = get_store()
    before = store.snapshot_doc(doc_id)
    if failure == 'embedding':
        monkeypatch.setattr(document_text, 'embed_texts', lambda texts: (_ for _ in ()).throw(RuntimeError('injected')))
    else:
        target, name = (store, '_save') if failure == 'vector' else (Session, 'commit')
        original = getattr(target, name)
        calls = 0
        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError('injected')
            return original(*args, **kwargs)
        monkeypatch.setattr(target, name, fail_once)
    response = browser.put(url, json={'content': OLD, 'version': fresh['version']}, headers=headers)
    assert response.status_code == 500, response.text
    assert browser.get(url).json()['data'] == fresh
    assert browser.get(f'/api/docs/{doc_id}/file').content == raw
    assert store.snapshot_doc(doc_id) == before


def test_image_correction_permissions_and_file_replacement(browser, monkeypatch):
    headers, doc_id, url, old, raw = setup_image(browser, monkeypatch)
    assert browser.put(url, json={'content': NEW, 'version': old['version']}).status_code == 403
    assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=headers).status_code == 200
    version = browser.get(f'/api/docs/{doc_id}/replacement').json()['data']['version']
    stream = BytesIO()
    Image.new('RGB', (120, 60), 'red').save(stream, format='PNG')
    response = browser.post(f'/api/docs/{doc_id}/replacement', data={'version': version},
                            files={'file': ('new.png', stream.getvalue())}, headers=headers)
    assert response.status_code == 200, response.text
    assert browser.get(url).json()['data']['content'] == OLD
    with SessionLocal() as db:
        assert db.get(DocumentOcrText, doc_id) is None
    other = login(browser)
    assert browser.get(url).status_code == 403
    assert browser.put(url, json={'content': NEW, 'version': old['version']}, headers=other).status_code == 403
    browser.cookies.clear()
    assert browser.get(url).status_code == 401


def test_formula_suggestion_does_not_save_until_explicit_text_update(browser, monkeypatch):
    from app.services.parsing import formula
    headers, doc_id, url, old, raw = setup_image(browser, monkeypatch)
    monkeypatch.setattr(settings, 'ocr_formula', 'rapid_latex')
    latex = r'x^{2}-3x+2=0'
    monkeypatch.setattr(formula, 'recognize_array', lambda image: latex)
    before = get_store().snapshot_doc(doc_id)
    response = browser.post(f'/api/docs/{doc_id}/formula', data={'version': old['version']},
                            files={'file': ('formula.png', raw)}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['data']['latex'] == latex
    assert browser.get(url).json()['data'] == old
    assert get_store().snapshot_doc(doc_id) == before
    assert browser.get(f'/api/docs/{doc_id}/file').content == raw
    content = OLD + '\n\n$$\n' + latex + '\n$$'
    assert browser.put(url, json={'content': content, 'version': old['version']}, headers=headers).status_code == 200
    assert latex in browser.get(f'/api/docs/{doc_id}/preview').text
    assert any(latex in item['d'] for item in get_store().snapshot_doc(doc_id))


@pytest.mark.parametrize('case', ['stale', 'invalid-image', 'failure', 'missing-csrf'])
def test_formula_errors_leave_document_untouched(browser, monkeypatch, case):
    from app.services.parsing import formula
    headers, doc_id, url, old, raw = setup_image(browser, monkeypatch)
    monkeypatch.setattr(settings, 'ocr_formula', 'rapid_latex')
    def fail(image):
        raise RuntimeError('injected model error')
    monkeypatch.setattr(formula, 'recognize_array', fail)
    response = browser.post(f'/api/docs/{doc_id}/formula',
        data={'version': '0' * 64 if case == 'stale' else old['version']},
        files={'file': ('formula.png', b'broken' if case == 'invalid-image' else raw)},
        headers={} if case == 'missing-csrf' else headers)
    assert response.status_code == {'stale': 409, 'missing-csrf': 403}.get(case, 422), response.text
    assert browser.get(url).json()['data'] == old
    assert browser.get(f'/api/docs/{doc_id}/file').content == raw


def test_formula_screenshot_requires_owner_session(browser, monkeypatch):
    headers, doc_id, url, old, raw = setup_image(browser, monkeypatch)
    other = login(browser)
    endpoint = f'/api/docs/{doc_id}/formula'
    args = {'data': {'version': old['version']}, 'files': {'file': ('formula.png', raw)}}
    assert browser.post(endpoint, **args, headers=other).status_code == 403
    browser.cookies.clear()
    assert browser.post(endpoint, **args).status_code == 401
