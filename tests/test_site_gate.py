import os
import shutil
import tempfile

import pytest

from app import create_app
from extensions import db as _db


@pytest.fixture
def gate_app(tmp_path):
    db_fd, db_path = tempfile.mkstemp()
    upload_dir = tempfile.mkdtemp()

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "UPLOAD_FOLDER": upload_dir,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "SITE_GATE_ENABLED": True,
            "SITE_GATE_PASSWORD": "abc123",
            "SITE_GATE_TTL_MINUTES": 1440,
        }
    )

    with app.app_context():
        _db.create_all()

        from models import Category

        default_parents = [
            "Lãi suất",
            "Các chương trình tín dụng ưu đãi",
            "Phí dịch vụ",
        ]
        for i, name in enumerate(default_parents, start=1):
            _db.session.add(Category(name=name, is_default=True, sort_order=i))
        _db.session.commit()

    yield app

    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(upload_dir, ignore_errors=True)


@pytest.fixture
def gate_app_csrf_on(tmp_path):
    db_fd, db_path = tempfile.mkstemp()
    upload_dir = tempfile.mkdtemp()

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "UPLOAD_FOLDER": upload_dir,
            "WTF_CSRF_ENABLED": True,
            "SECRET_KEY": "test-secret-key",
            "SITE_GATE_ENABLED": True,
            "SITE_GATE_PASSWORD": "abc123",
            "SITE_GATE_TTL_MINUTES": 1440,
        }
    )

    with app.app_context():
        _db.create_all()

        from models import Category

        default_parents = [
            "Lãi suất",
            "Các chương trình tín dụng ưu đãi",
            "Phí dịch vụ",
        ]
        for i, name in enumerate(default_parents, start=1):
            _db.session.add(Category(name=name, is_default=True, sort_order=i))
        _db.session.commit()

    yield app

    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(upload_dir, ignore_errors=True)


class TestSiteGateHelpers:
    def test_is_public_protected_path_matches_scope(self):
        from site_gate import is_public_protected_path

        assert is_public_protected_path("/") is True
        assert is_public_protected_path("/api/categories") is True
        assert is_public_protected_path("/pdf/1") is True
        assert is_public_protected_path("/admin/login") is False
        assert is_public_protected_path("/gate/unlock") is False

    def test_record_failed_attempt_and_lockout(self, gate_app):
        from site_gate import record_failed_attempt, is_ip_locked, reset_ip_lock_state

        with gate_app.app_context():
            ip = "1.2.3.4"
            reset_ip_lock_state(ip)
            for _ in range(4):
                locked, _ = record_failed_attempt(ip)
                assert locked is False

            locked, seconds_left = record_failed_attempt(ip)
            assert locked is True
            assert 1 <= seconds_left <= 900

            locked_now, _ = is_ip_locked(ip)
            assert locked_now is True

    def test_session_unlock_and_expiry(self, gate_app):
        from site_gate import set_session_unlocked, is_session_unlocked

        with gate_app.test_request_context("/"):
            set_session_unlocked(1)
            assert is_session_unlocked() is True

            # Force expire
            from flask import session

            session["site_gate_until"] = 0
            assert is_session_unlocked() is False


class TestSiteGateMiddleware:
    def test_root_returns_gate_page_when_not_unlocked(self, gate_app):
        client = gate_app.test_client()
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Xác thực truy cập" in resp.get_data(as_text=True)

    def test_api_returns_403_when_not_unlocked(self, gate_app):
        client = gate_app.test_client()
        resp = client.get("/api/categories")
        assert resp.status_code == 403

    def test_admin_login_not_blocked(self, gate_app):
        client = gate_app.test_client()
        resp = client.get("/admin/login")
        assert resp.status_code == 200

    def test_locked_root_returns_403_with_gate_message(self, gate_app):
        client = gate_app.test_client()
        for _ in range(5):
            client.post("/gate/unlock", data={"password": "wrong"})

        resp = client.get("/")
        assert resp.status_code == 403
        assert "Vui lòng thử lại sau" in resp.get_data(as_text=True)


class TestSiteGateUnlockRoute:
    def test_unlock_correct_password_allows_api(self, gate_app):
        client = gate_app.test_client()

        resp = client.post(
            "/gate/unlock",
            data={"password": "abc123"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        api_resp = client.get("/api/categories")
        assert api_resp.status_code == 200

    def test_unlock_wrong_password_shows_error(self, gate_app):
        client = gate_app.test_client()

        resp = client.post(
            "/gate/unlock",
            data={"password": "wrong"},
        )
        assert resp.status_code == 200
        assert "Mật khẩu không đúng" in resp.get_data(as_text=True)

    def test_unlock_fails_closed_when_password_not_configured(self, tmp_path):
        db_fd, db_path = tempfile.mkstemp()
        upload_dir = tempfile.mkdtemp()

        app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
                "UPLOAD_FOLDER": upload_dir,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret-key",
                "SITE_GATE_ENABLED": True,
                "SITE_GATE_PASSWORD": "",
                "SITE_GATE_TTL_MINUTES": 1440,
            }
        )

        with app.app_context():
            _db.create_all()

        client = app.test_client()
        resp = client.post("/gate/unlock", data={"password": "anything"})
        assert resp.status_code == 403

        api_resp = client.get("/api/categories")
        assert api_resp.status_code == 403

        os.close(db_fd)
        os.unlink(db_path)
        shutil.rmtree(upload_dir, ignore_errors=True)


class TestSiteGateUI:
    def test_gate_page_contains_password_form_and_csrf(self, gate_app):
        client = gate_app.test_client()
        resp = client.get("/")

        html = resp.get_data(as_text=True)
        assert "name=\"password\"" in html
        assert "name=\"csrf_token\"" in html
        assert "Xác thực truy cập" in html
        assert "site-gate.js" in html


class TestSiteGateCsrf:
    def test_unlock_without_csrf_returns_400(self, gate_app_csrf_on):
        client = gate_app_csrf_on.test_client()
        resp = client.post("/gate/unlock", data={"password": "abc123"})
        assert resp.status_code == 400

    def test_unlock_with_csrf_token_succeeds(self, gate_app_csrf_on):
        import re

        client = gate_app_csrf_on.test_client()

        gate_page = client.get("/")
        html = gate_page.get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        assert match is not None
        token = match.group(1)

        resp = client.post(
            "/gate/unlock",
            data={"password": "abc123", "csrf_token": token},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)

        api_resp = client.get("/api/categories")
        assert api_resp.status_code == 200


class TestSiteGateConfig:
    def test_site_gate_enabled_default_is_false(self, app):
        assert app.config["SITE_GATE_ENABLED"] is False

    def test_site_gate_ttl_default_is_1440(self, app):
        assert app.config["SITE_GATE_TTL_MINUTES"] == 1440
