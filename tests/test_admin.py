from models import db, Admin


class TestLogin:
    def test_login_page_loads(self, client):
        resp = client.get("/admin/login")
        assert resp.status_code == 200
        assert "Đăng nhập".encode() in resp.data

    def test_login_success(self, app, client):
        with app.app_context():
            admin = Admin(username="admin")
            admin.set_password("admin123")
            admin.force_password_change = False
            db.session.add(admin)
            db.session.commit()

        resp = client.post(
            "/admin/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "Admin Panel".encode() in resp.data

    def test_login_wrong_password(self, app, client):
        with app.app_context():
            admin = Admin(username="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()

        resp = client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong"},
            follow_redirects=True,
        )
        assert "Sai tên đăng nhập hoặc mật khẩu".encode() in resp.data

    def test_login_redirects_to_change_password(self, app, client):
        with app.app_context():
            admin = Admin(username="admin")
            admin.set_password("admin123")
            admin.force_password_change = True
            db.session.add(admin)
            db.session.commit()

        resp = client.post(
            "/admin/login",
            data={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 302
        assert "/admin/change-password" in resp.headers["Location"]

    def test_logout(self, auth_client):
        resp = auth_client.post("/admin/logout", follow_redirects=True)
        assert resp.status_code == 200
        assert "Đăng nhập".encode() in resp.data


class TestChangePassword:
    def test_change_password_page_loads(self, auth_client):
        resp = auth_client.get("/admin/change-password")
        assert resp.status_code == 200
        assert "Đổi mật khẩu".encode() in resp.data

    def test_change_password_success(self, app, auth_client):
        resp = auth_client.post(
            "/admin/change-password",
            data={
                "current_password": "admin123",
                "new_password": "newpass456",
                "confirm_password": "newpass456",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            admin = Admin.query.filter_by(username="admin").first()
            assert admin.check_password("newpass456") is True
            assert admin.force_password_change is False

    def test_change_password_wrong_current(self, auth_client):
        resp = auth_client.post(
            "/admin/change-password",
            data={
                "current_password": "wrongpass",
                "new_password": "newpass456",
                "confirm_password": "newpass456",
            },
            follow_redirects=True,
        )
        assert "Mật khẩu hiện tại không đúng".encode() in resp.data

    def test_change_password_mismatch(self, auth_client):
        resp = auth_client.post(
            "/admin/change-password",
            data={
                "current_password": "admin123",
                "new_password": "newpass456",
                "confirm_password": "different",
            },
            follow_redirects=True,
        )
        assert "Mật khẩu mới không khớp".encode() in resp.data


class TestAdminAccess:
    def test_admin_requires_login(self, client):
        resp = client.get("/admin")
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]
