"""Font persistence, independent theme settings and account isolation."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from backend.tests.test_auth import browser, register  # noqa: F401


def test_font_persists_without_changing_other_settings(browser):
    account, data = register(browser)
    assert data['user']['font'] == 'default'
    headers = {'X-CSRF-Token': data['csrf_token']}
    browser.patch('/api/auth/me', json={'nickname': '小明'}, headers=headers)
    browser.patch('/api/auth/me/theme', json={'theme': 'dark'}, headers=headers)
    for font in ('song', 'kai', 'default', 'kai'):
        result = browser.patch('/api/auth/me/font', json={'font': font}, headers=headers)
        assert result.status_code == 200
        user = result.json()['data']['user']
        assert (user['font'], user['nickname'], user['theme']) == (font, '小明', 'dark')
        assert browser.get('/api/auth/me').json()['data']['user']['font'] == font
    # Subsequent theme/nickname saves must preserve the selected font.
    assert browser.patch('/api/auth/me/theme', json={'theme': 'light'}, headers=headers).json()['data']['user']['font'] == 'kai'
    assert browser.patch('/api/auth/me', json={'nickname': '小红'}, headers=headers).json()['data']['user']['font'] == 'kai'
    browser.post('/api/auth/logout', headers=headers)
    restored = browser.post('/api/auth/login', json=account).json()['data']['user']
    assert (restored['font'], restored['theme']) == ('kai', 'light')
    with TestClient(app) as other:
        _, second = register(other)
        assert second['user']['font'] == 'default'
        other.patch('/api/auth/me/font', json={'font': 'song'}, headers={'X-CSRF-Token': second['csrf_token']})
    assert browser.get('/api/auth/me').json()['data']['user']['font'] == 'kai'


def test_font_requires_login_and_csrf(browser):
    assert browser.patch('/api/auth/me/font', json={'font': 'kai'}).status_code == 401
    register(browser)
    assert browser.patch('/api/auth/me/font', json={'font': 'kai'}).status_code == 403
    assert browser.get('/api/auth/me').json()['data']['user']['font'] == 'default'


@pytest.mark.parametrize('body', [{'font': 'unknown'}, {'font': None}, {}, {'font': 'kai', 'user_id': 'other'}])
def test_invalid_font_preserves_saved_value(browser, body):
    _, data = register(browser)
    headers = {'X-CSRF-Token': data['csrf_token']}
    browser.patch('/api/auth/me/font', json={'font': 'song'}, headers=headers)
    assert browser.patch('/api/auth/me/font', json=body, headers=headers).status_code == 400
    assert browser.get('/api/auth/me').json()['data']['user']['font'] == 'song'
