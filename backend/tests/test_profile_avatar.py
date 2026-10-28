"""Real image avatar storage, authentication and transaction retention."""
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from sqlalchemy.orm import Session

from app.core import auth
from app.main import app


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app) as client:
        yield client
    auth._attempts.clear()


def login(browser):
    account = {'username': 'avatar_' + uuid4().hex[:10], 'password': uuid4().hex}
    response = browser.post('/api/auth/register', json=account)
    assert response.status_code == 200, response.text
    return account, {'X-CSRF-Token': response.json()['data']['csrf_token']}


def picture(color='red', format='PNG'):
    stream = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('Comment', 'private source metadata')
    Image.new('RGB', (300, 180), color).save(stream, format=format, pnginfo=metadata)
    return stream.getvalue()


@pytest.mark.parametrize('extension,format', [('png', 'PNG'), ('jpg', 'JPEG'), ('jpeg', 'JPEG')])
def test_avatar_is_normalized_persistent_and_independent_of_nickname(browser, extension, format):
    account, headers = login(browser)
    assert browser.get('/api/auth/me').json()['data']['user']['avatar_url'] is None
    assert browser.get('/api/auth/me/avatar').status_code == 404
    assert browser.patch('/api/auth/me', json={'nickname': '头像练习'}, headers=headers).status_code == 200
    response = browser.post('/api/auth/me/avatar', files={'file': ('photo.' + extension, picture(format=format))}, headers=headers)
    assert response.status_code == 200, response.text
    user = response.json()['data']['user']
    assert user['nickname'] == '头像练习' and user['username'] == account['username']
    avatar = browser.get(user['avatar_url'])
    assert avatar.status_code == 200
    assert avatar.headers['content-type'] == 'image/png'
    assert avatar.headers['cache-control'] == 'no-store'
    assert avatar.headers['x-content-type-options'] == 'nosniff'
    with Image.open(BytesIO(avatar.content)) as image:
        assert image.size == (256, 256) and image.format == 'PNG'
        assert not image.info and not image.getexif()
    assert browser.get('/api/auth/me').json()['data']['user'] == user
    assert browser.post('/api/auth/logout', headers=headers).status_code == 200
    logged_in = browser.post('/api/auth/login', json=account)
    assert logged_in.json()['data']['user'] == user
    headers = {'X-CSRF-Token': logged_in.json()['data']['csrf_token']}
    changed = browser.post('/api/auth/me/avatar', files={'file': ('new.png', picture('blue'))}, headers=headers)
    assert changed.status_code == 200
    assert changed.json()['data']['user']['avatar_url'] != user['avatar_url']
    assert browser.get('/api/auth/me/avatar').content != avatar.content
    removed = browser.delete('/api/auth/me/avatar', headers=headers)
    assert removed.status_code == 200
    assert removed.json()['data']['user']['avatar_url'] is None
    assert removed.json()['data']['user']['nickname'] == '头像练习'
    assert browser.get('/api/auth/me/avatar').status_code == 404


@pytest.mark.parametrize('filename,raw,status', [
    ('broken.png', b'broken image', 422), ('fake.jpg', picture(), 422),
    ('photo.svg', b'<svg/>', 415), ('empty.png', b'', 413),
    ('large.png', b'x' * (2 * 1024 * 1024 + 1), 413),
], ids=['broken', 'format-mismatch', 'unsupported', 'empty', 'oversized'])
def test_invalid_avatar_preserves_existing_image(browser, filename, raw, status):
    _, headers = login(browser)
    assert browser.post('/api/auth/me/avatar', files={'file': ('old.png', picture())}, headers=headers).status_code == 200
    before = browser.get('/api/auth/me/avatar').content
    response = browser.post('/api/auth/me/avatar', files={'file': (filename, raw)}, headers=headers)
    assert response.status_code == status, response.text
    assert browser.get('/api/auth/me/avatar').content == before


def test_avatar_requires_session_csrf_and_is_private_to_current_account(browser):
    account, headers = login(browser)
    assert browser.post('/api/auth/me/avatar', files={'file': ('old.png', picture())}).status_code == 403
    response = browser.post('/api/auth/me/avatar', files={'file': ('old.png', picture())}, headers=headers)
    url = response.json()['data']['user']['avatar_url']
    before = browser.get(url).content
    assert browser.delete('/api/auth/me/avatar').status_code == 403
    _, other = login(browser)
    assert browser.get(url).status_code == 404
    assert browser.delete('/api/auth/me/avatar', headers=other).status_code == 200
    logged_in = browser.post('/api/auth/login', json=account)
    assert logged_in.status_code == 200
    assert browser.get(url).content == before
    browser.cookies.clear()
    assert browser.get(url).status_code == 401
    assert browser.post('/api/auth/me/avatar', files={'file': ('photo.png', picture())}).status_code == 401
    assert browser.delete('/api/auth/me/avatar').status_code == 401


def test_failed_avatar_commit_keeps_old_image(browser, monkeypatch):
    _, headers = login(browser)
    assert browser.post('/api/auth/me/avatar', files={'file': ('old.png', picture())}, headers=headers).status_code == 200
    before = browser.get('/api/auth/me/avatar').content
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise RuntimeError('injected database failure')
        patch.setattr(Session, 'commit', fail)
        with pytest.raises(RuntimeError, match='injected database failure'):
            browser.post('/api/auth/me/avatar', files={'file': ('new.png', picture('blue'))}, headers=headers)
    assert browser.get('/api/auth/me/avatar').content == before
