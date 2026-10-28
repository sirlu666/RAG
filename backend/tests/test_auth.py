"""Real auth integration tests: no A/B identity override is installed here."""

import time
from collections import deque
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.db.auth_models import AuthSession
from app.db.models import User, UserProfile
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture()
def browser():
    auth._attempts.clear()
    with TestClient(app) as client:
        yield client
    auth._attempts.clear()


def credentials():
    return {"username": f"learner_{uuid4().hex[:10]}", "password": "Math-learning-2026"}


def register(browser, account=None):
    account = account or credentials()
    response = browser.post("/api/auth/register", json=account)
    assert response.status_code == 200, response.text
    return account, response.json()["data"]


def test_register_hashes_password_and_restores_session(browser):
    account, data = register(browser)
    assert data["user"]["username"] == account["username"]
    assert "password" not in data["user"] and "password_hash" not in data["user"]
    cookie = browser.cookies.get(auth.COOKIE_NAME)
    with SessionLocal() as db:
        user = db.get(User, data["user"]["id"])
        assert user.password_hash != account["password"]
        assert auth.verify_password(account["password"], user.password_hash)
        assert db.get(AuthSession, cookie) is None
        assert db.get(AuthSession, auth.token_digest(cookie)).user_id == user.id
    restored = browser.get("/api/auth/me")
    assert restored.status_code == 200
    assert restored.headers["cache-control"] == "no-store"
    assert restored.json()["data"] == data
    assert browser.get("/api/docs").status_code == 200


def test_cookie_flags_and_duplicate_username(browser):
    account = credentials()
    response = browser.post("/api/auth/register", json=account)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/api" in cookie
    assert "max-age=" in cookie
    duplicate = browser.post("/api/auth/register", json=account)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 1005


def test_logout_revokes_copied_cookie_and_login_rotates_it(browser):
    account, data = register(browser)
    old_cookie = browser.cookies.get(auth.COOKIE_NAME)
    assert browser.post("/api/auth/logout", headers={"X-CSRF-Token": data["csrf_token"]}).status_code == 200
    assert browser.get("/api/docs").status_code == 401
    assert browser.get("/api/auth/me", headers={"Cookie": f"{auth.COOKIE_NAME}={old_cookie}"}).status_code == 401
    assert browser.post("/api/auth/login", json=account).status_code == 200
    assert browser.cookies.get(auth.COOKIE_NAME) != old_cookie


def test_password_errors_and_legacy_accounts_cannot_be_claimed(browser):
    account, _ = register(browser)
    browser.cookies.clear()
    wrong = {**account, "password": "incorrect-password"}
    missing = {**account, "username": "missing_" + uuid4().hex[:8]}
    a = browser.post("/api/auth/login", json=wrong)
    b = browser.post("/api/auth/login", json=missing)
    assert a.status_code == b.status_code == 401
    assert a.json()["message"] == b.json()["message"]
    legacy = "legacy_" + uuid4().hex[:8]
    with SessionLocal() as db:
        db.add(User(username=legacy))
        db.commit()
    assert browser.post("/api/auth/register", json={**account, "username": legacy}).status_code == 409
    assert browser.post("/api/auth/login", json={**account, "username": legacy}).status_code == 401


@pytest.mark.parametrize("path", ["/api/auth/me", "/api/docs", "/api/docs/doc_missing/preview"])
def test_no_cookie_or_dev_header_cannot_access_private_endpoints(browser, path):
    assert browser.get(path).status_code == 401
    assert browser.get(path, headers={"Authorization": "Bearer dev:alice"}).status_code == 401


def test_expired_and_forged_sessions_are_rejected(browser):
    _, data = register(browser)
    with SessionLocal() as db:
        session = db.get(AuthSession, auth.token_digest(browser.cookies.get(auth.COOKIE_NAME)))
        session.expires_at = int(time.time()) - 1
        db.commit()
    assert browser.get("/api/auth/me").status_code == 401
    browser.cookies.clear()
    browser.cookies.set(auth.COOKIE_NAME, "forged-cookie", path="/api")
    assert browser.get("/api/docs").status_code == 401


def test_csrf_and_untrusted_origins_are_rejected(browser):
    _, data = register(browser)
    assert browser.post("/api/auth/logout").status_code == 403
    assert browser.post("/api/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert browser.post("/api/auth/logout", headers={"X-CSRF-Token": data["csrf_token"], "Origin": "https://untrusted.example"}).status_code == 403
    assert browser.get("/api/auth/me").status_code == 200
    assert browser.post("/api/auth/login", json=credentials(), headers={"Origin": "https://untrusted.example"}).status_code == 403


def test_real_cookie_users_cannot_read_each_others_documents(browser):
    _, owner = register(browser)
    upload = browser.post("/api/docs/upload", files={"file": ("private.md", "一元二次方程的求根公式与判别式。".encode(), "text/markdown")}, headers={"X-CSRF-Token": owner["csrf_token"]})
    assert upload.status_code == 200, upload.text
    doc_id = upload.json()["data"]["doc_id"]
    assert browser.get(f"/api/docs/{doc_id}/status").status_code == 200
    # Registration of a different account rotates the session instead of inheriting ownership.
    _, other = register(browser)
    assert browser.get(f"/api/docs/{doc_id}/status").status_code == 403
    assert all(doc["id"] != doc_id for doc in browser.get("/api/docs").json()["data"])
    assert browser.delete(f"/api/docs/{doc_id}", headers={"X-CSRF-Token": other["csrf_token"]}).status_code == 403


@pytest.mark.parametrize("updates", [{"username": "a"}, {"username": "bad name"}, {"password": "short"}, {"password": "a" * 129}])
def test_invalid_registration(browser, updates):
    assert browser.post("/api/auth/register", json={**credentials(), **updates}).status_code == 400


def test_login_is_rate_limited(browser):
    auth._attempts["testclient"] = deque([time.monotonic()] * 20)
    response = browser.post("/api/auth/login", json=credentials())
    assert response.status_code == 429


def test_nickname_persists_without_changing_login_or_identity(browser):
    account, session = register(browser)
    assert session['user']['nickname'] == ''
    user_id = session['user']['id']
    headers = {'X-CSRF-Token': session['csrf_token']}
    response = browser.patch('/api/auth/me', json={'nickname': '  数学学习者  '}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    updated = response.json()['data']['user']
    assert updated['id'] == user_id and updated['username'] == account['username']
    assert updated['nickname'] == '数学学习者'
    assert browser.get('/api/auth/me').json()['data']['user'] == updated
    with SessionLocal() as db:
        assert db.get(UserProfile, user_id).nickname == '数学学习者'
    assert browser.post('/api/auth/logout', headers=headers).status_code == 200
    logged_in = browser.post('/api/auth/login', json=account)
    assert logged_in.status_code == 200
    assert logged_in.json()['data']['user'] == updated
    cleared = browser.patch('/api/auth/me', json={'nickname': ''},
                            headers={'X-CSRF-Token': logged_in.json()['data']['csrf_token']})
    assert cleared.status_code == 200
    assert cleared.json()['data']['user']['nickname'] == ''
    assert browser.get('/api/auth/me').json()['data']['user']['nickname'] == ''


@pytest.mark.parametrize('nickname', ['x' * 31, '含\n换行', '含\x00控制字符'])
def test_invalid_nickname_leaves_profile_unchanged(browser, nickname):
    _, session = register(browser)
    response = browser.patch('/api/auth/me', json={'nickname': nickname},
                             headers={'X-CSRF-Token': session['csrf_token']})
    assert response.status_code == 400, response.text
    assert browser.get('/api/auth/me').json()['data']['user']['nickname'] == ''


def test_nickname_requires_session_csrf_and_cannot_target_other_accounts(browser):
    account, owner = register(browser)
    assert browser.patch('/api/auth/me', json={'nickname': '未授权'}).status_code == 403
    _, other = register(browser)
    headers = {'X-CSRF-Token': other['csrf_token']}
    assert browser.patch('/api/auth/me', json={'nickname': '越权', 'user_id': owner['user']['id']}, headers=headers).status_code == 400
    assert browser.patch('/api/auth/me', json={'nickname': '其他账号'}, headers=headers).status_code == 200
    logged_in = browser.post('/api/auth/login', json=account)
    assert logged_in.json()['data']['user']['nickname'] == ''
    browser.cookies.clear()
    assert browser.patch('/api/auth/me', json={'nickname': '游客'}).status_code == 401
