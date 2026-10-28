"""Real multi-format version replacement and old-data retention."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.core.config import settings
from app.db.models import Document, DocumentCategory
from app.db.session import SessionLocal
from app.main import app
from app.rag.vectorstore import get_store
from app.services import doc_service, document_text


def content(extension, marker):
    text = marker + ' A quadratic equation has two distinct real roots when its discriminant is positive. Example: x^2 - 3x + 2 = 0 has roots 1 and 2. ' + uuid4().hex
    if extension == 'docx':
        from docx import Document as WordDocument
        document = WordDocument()
        document.add_paragraph(text)
        stream = BytesIO()
        document.save(stream)
        return stream.getvalue()
    if extension == 'pdf':
        import pymupdf
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 500), text, fontsize=11)
            return document.tobytes()
    return text.encode('utf-8')


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    auth._attempts.clear()


def login(browser):
    response = browser.post('/api/auth/register', json={
        'username': 'replace_' + uuid4().hex[:10], 'password': 'Replacement-learning-2026',
    })
    assert response.status_code == 200, response.text
    return {'X-CSRF-Token': response.json()['data']['csrf_token']}


def setup(browser, extension='txt'):
    headers = login(browser)
    old_raw = content(extension, 'OLD-VERSION')
    response = browser.post('/api/docs/upload', files={'file': ('original.'+extension, old_raw)}, headers=headers)
    assert response.status_code == 200, response.text
    doc_id = response.json()['data']['doc_id']
    url = f'/api/docs/{doc_id}/replacement'
    info = browser.get(url).json()['data']
    return headers, doc_id, url, info, old_raw


def replace(browser, headers, url, version, raw, filename='new.txt'):
    return browser.post(url, data={'version': version}, files={'file': (filename, raw)}, headers=headers)


@pytest.mark.parametrize('extension', ['pdf', 'docx', 'md', 'txt'])
def test_replacement_updates_real_document_and_retains_identity_category_and_backup(browser, extension):
    headers, doc_id, url, info, old_raw = setup(browser, extension)
    old_vectors = get_store().snapshot_doc(doc_id)
    with SessionLocal() as db:
        source = db.get(Document, doc_id)
        path = Path(source.stored_path)
        kb_id = source.kb_id
        db.add(DocumentCategory(doc_id=doc_id, category='代数', revision=uuid4().hex))
        db.commit()
    new_raw = content(extension, 'NEW-VERSION')
    response = replace(browser, headers, url, info['version'], new_raw, 'replacement.' + extension)
    assert response.status_code == 200, response.text
    assert response.json()['data']['changed'] is True
    assert path.read_bytes() == new_raw
    assert browser.get(url).json()['data']['version'] != info['version']
    preview = browser.get(f'/api/docs/{doc_id}/preview').json()['data']
    assert 'NEW-VERSION' in str(preview) and 'OLD-VERSION' not in str(preview)
    assert not ({item['id'] for item in old_vectors} & get_store().ids())
    with SessionLocal() as db:
        source = db.get(Document, doc_id)
        assert source.filename == 'original.' + extension
        assert source.kb_id == kb_id and source.status == 'ready'
        assert source.page_count == (1 if extension == 'pdf' else None)
        assert db.get(DocumentCategory, doc_id).category == '代数'
    assert any(file.read_bytes() == old_raw for file in (path.parent / '.versions' / doc_id).glob('*/' + path.name))
    assert not list(path.parent.glob('.replacement-*'))
    assert replace(browser, headers, url, info['version'], new_raw, 'replacement.'+extension).status_code == 409
    fresh = browser.get(url).json()['data']
    assert replace(browser, headers, url, fresh['version'], new_raw, 'replacement.'+extension).json()['data']['changed'] is False


@pytest.mark.parametrize('case', ['short', 'wrong-type', 'broken-docx', 'broken-pdf', 'empty', 'oversized'])
def test_invalid_replacement_leaves_file_chunks_and_vectors_untouched(browser, monkeypatch, case):
    extension = 'docx' if case == 'broken-docx' else 'pdf' if case == 'broken-pdf' else 'txt'
    headers, doc_id, url, info, old_raw = setup(browser, extension)
    before = get_store().snapshot_doc(doc_id)
    with SessionLocal() as db:
        path = Path(db.get(Document, doc_id).stored_path)
    raw, filename, expected = b'too short', 'new.'+extension, 422
    if case == 'wrong-type': filename, expected = 'new.pdf', 415
    if case == 'empty': raw, expected = b'', 400
    if case == 'oversized':
        monkeypatch.setattr(settings, 'max_upload_mb', 0)
        raw, expected = b'x', 413
    response = replace(browser, headers, url, info['version'], raw, filename)
    assert response.status_code == expected, response.text
    assert path.read_bytes() == old_raw
    assert get_store().snapshot_doc(doc_id) == before
    assert browser.get(f'/api/docs/{doc_id}/preview').status_code == 200
    assert not list(path.parent.glob('.replacement-*'))


def test_permissions_csrf_processing_and_embedding_failure(browser, monkeypatch):
    headers, doc_id, url, info, old_raw = setup(browser)
    raw = content('txt', 'NEW-VERSION')
    assert replace(browser, {}, url, info['version'], raw).status_code == 403
    with doc_service._INGEST_LOCK:
        assert replace(browser, headers, url, info['version'], raw).status_code == 409
    before = get_store().snapshot_doc(doc_id)
    monkeypatch.setattr(document_text, 'embed_texts', lambda texts: (_ for _ in ()).throw(RuntimeError('embedding failed')))
    assert replace(browser, headers, url, info['version'], raw).status_code == 500
    assert get_store().snapshot_doc(doc_id) == before
    with SessionLocal() as db:
        assert Path(db.get(Document, doc_id).stored_path).read_bytes() == old_raw
    other = login(browser)
    assert browser.get(url).status_code == 403
    assert replace(browser, other, url, info['version'], raw).status_code == 403
    browser.cookies.clear()
    assert browser.get(url).status_code == 401
    assert replace(browser, headers, url, info['version'], raw).status_code == 401


@pytest.mark.parametrize('extension', ['png', 'jpg', 'jpeg'])
def test_short_image_question_can_be_uploaded_and_replaced_without_losing_short_chunks(browser, monkeypatch, extension):
    from PIL import Image
    from app.services.parsing import ocr

    def image_bytes(color):
        stream = BytesIO()
        Image.new('RGB', (8, 8), color).save(stream, format='PNG' if extension == 'png' else 'JPEG')
        return stream.getvalue()

    old_raw, new_raw, short_raw = [image_bytes(color) for color in ('blue', 'red', 'green')]
    recognized = {old_raw: '求解 x+1=2', new_raw: '求解 x+2=3', short_raw: 'x=1'}
    # Only OCR inference is stubbed; the real upload, splitting, indexing and replacement run.
    monkeypatch.setattr(settings, 'ocr_enable', True)
    monkeypatch.setattr(ocr, 'ocr_image_pages', lambda path: [(1, recognized[path.read_bytes()])])
    headers = login(browser)
    uploaded = browser.post('/api/docs/upload', files={'file': ('question.' + extension, old_raw)}, headers=headers)
    assert uploaded.status_code == 200, uploaded.text
    doc_id = uploaded.json()['data']['doc_id']
    preview_url = f'/api/docs/{doc_id}/preview'
    initial = browser.get(preview_url)
    assert initial.status_code == 200, initial.text
    assert initial.json()['data']['items'][0]['content'] == recognized[old_raw]

    url = f'/api/docs/{doc_id}/replacement'
    version = browser.get(url).json()['data']['version']
    replaced = replace(browser, headers, url, version, new_raw, 'question-new.' + extension)
    assert replaced.status_code == 200, replaced.text
    assert browser.get(preview_url).json()['data']['items'][0]['content'] == recognized[new_raw]
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        path = Path(doc.stored_path)
        assert doc.status == 'ready' and doc.chunk_count == 1
        assert path.read_bytes() == new_raw
        assert any(backup.read_bytes() == old_raw for backup in (path.parent / '.versions' / doc_id).glob('*/' + path.name))

    vectors = get_store().snapshot_doc(doc_id)
    version = browser.get(url).json()['data']['version']
    rejected = replace(browser, headers, url, version, short_raw, 'too-short.' + extension)
    assert rejected.status_code == 422
    assert path.read_bytes() == new_raw and get_store().snapshot_doc(doc_id) == vectors
