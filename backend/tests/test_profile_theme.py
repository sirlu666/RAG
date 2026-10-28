"""Account theme persistence, isolation, and request validation."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from backend.tests.test_auth import browser, register  # noqa: F401 - shared isolated browser fixture


def test_theme_defaults_persists_and_does_not_change_nickname(browser):
    account, data = register(browser)
    assert data['user']['theme'] == 'default'
    headers = {'X-CSRF-Token': data['csrf_token']}
    browser.patch('/api/auth/me', json={'nickname': '小明'}, headers=headers)
    for theme in ('dark', 'light', 'default', 'dark'):
        response = browser.patch('/api/auth/me/theme', json={'theme': theme}, headers=headers)
        assert response.status_code == 200
        assert response.json()['data']['user']['nickname'] == '小明'
        assert response.json()['data']['user']['theme'] == theme
        assert browser.get('/api/auth/me').json()['data']['user']['theme'] == theme
    browser.post('/api/auth/logout', headers=headers)
    restored = browser.post('/api/auth/login', json=account).json()['data']
    assert restored['user']['theme'] == 'dark'
    with TestClient(app) as other:
        _, second = register(other)
        assert second['user']['theme'] == 'default'
        other.patch('/api/auth/me/theme', json={'theme': 'light'}, headers={'X-CSRF-Token': second['csrf_token']})
    assert browser.get('/api/auth/me').json()['data']['user']['theme'] == 'dark'


def test_theme_requires_login_and_csrf(browser):
    assert browser.patch('/api/auth/me/theme', json={'theme': 'dark'}).status_code == 401
    _, data = register(browser)
    assert browser.patch('/api/auth/me/theme', json={'theme': 'dark'}).status_code == 403
    assert browser.get('/api/auth/me').json()['data']['user']['theme'] == 'default'


@pytest.mark.parametrize('body', [{'theme': 'invalid'}, {'theme': None}, {}, {'theme': 'dark', 'user_id': 'other'}])
def test_invalid_theme_keeps_saved_value(browser, body):
    _, data = register(browser)
    response = browser.patch('/api/auth/me/theme', json=body, headers={'X-CSRF-Token': data['csrf_token']})
    assert response.status_code == 400
    assert browser.get('/api/auth/me').json()['data']['user']['theme'] == 'default'
