from extensions import db
from models import Admin


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


from models import Category


class TestCategoryCRUD:
    def test_create_category(self, app, auth_client):
        resp = auth_client.post(
            "/admin/categories",
            json={"name": "Lãi suất tiết kiệm", "icon": "💰"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Lãi suất tiết kiệm"
        assert data["icon"] == "💰"

    def test_create_category_missing_name(self, auth_client):
        resp = auth_client.post("/admin/categories", json={"icon": "💰"})
        assert resp.status_code == 400

    def test_update_category(self, app, auth_client):
        # Create first
        resp = auth_client.post(
            "/admin/categories",
            json={"name": "Old Name", "icon": "📄"},
        )
        cat_id = resp.get_json()["id"]

        # Update
        resp = auth_client.put(
            f"/admin/categories/{cat_id}",
            json={"name": "New Name", "icon": "💰", "sort_order": 5},
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "New Name"
        assert resp.get_json()["sort_order"] == 5

    def test_delete_empty_category(self, app, auth_client):
        resp = auth_client.post(
            "/admin/categories",
            json={"name": "To Delete", "icon": "🗑️"},
        )
        cat_id = resp.get_json()["id"]

        resp = auth_client.delete(f"/admin/categories/{cat_id}")
        assert resp.status_code == 200

    def test_delete_category_with_pdfs_fails(self, app, auth_client):
        from models import Pdf

        resp = auth_client.post(
            "/admin/categories",
            json={"name": "Has PDFs", "icon": "📄"},
        )
        cat_id = resp.get_json()["id"]

        with app.app_context():
            pdf = Pdf(
                category_id=cat_id,
                title="Test",
                filename="test-uuid.pdf",
                file_size=100,
            )
            db.session.add(pdf)
            db.session.commit()

        resp = auth_client.delete(f"/admin/categories/{cat_id}")
        assert resp.status_code == 400

    def test_category_crud_requires_auth(self, client):
        resp = client.post("/admin/categories", json={"name": "X"})
        assert resp.status_code == 302  # redirect to login


import io
import os


class TestPdfUploadDelete:
    def _make_pdf_bytes(self):
        """Minimal valid PDF content (starts with %PDF-)."""
        return b"%PDF-1.4 fake pdf content for testing"

    def test_upload_pdf(self, app, auth_client):
        # Create a category first
        resp = auth_client.post(
            "/admin/categories",
            json={"name": "Test Cat", "icon": "📄"},
        )
        cat_id = resp.get_json()["id"]

        data = {
            "title": "Lãi suất tháng 3",
            "category_id": str(cat_id),
            "file": (io.BytesIO(self._make_pdf_bytes()), "test.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        result = resp.get_json()
        assert result["title"] == "Lãi suất tháng 3"

        # Verify file exists on disk
        with app.app_context():
            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"], result["filename"]
            )
            assert os.path.exists(filepath)

    def test_upload_non_pdf_rejected(self, app, auth_client):
        resp = auth_client.post(
            "/admin/categories",
            json={"name": "Test Cat", "icon": "📄"},
        )
        cat_id = resp.get_json()["id"]

        data = {
            "title": "Not a PDF",
            "category_id": str(cat_id),
            "file": (io.BytesIO(b"not a pdf file"), "test.txt"),
        }
        resp = auth_client.post(
            "/admin/pdfs",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_fake_pdf_extension_rejected(self, app, auth_client):
        resp = auth_client.post(
            "/admin/categories",
            json={"name": "Test Cat", "icon": "📄"},
        )
        cat_id = resp.get_json()["id"]

        data = {
            "title": "Fake PDF",
            "category_id": str(cat_id),
            "file": (io.BytesIO(b"not actually pdf"), "fake.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_delete_pdf(self, app, auth_client):
        # Create category + upload PDF
        resp = auth_client.post(
            "/admin/categories",
            json={"name": "Test Cat", "icon": "📄"},
        )
        cat_id = resp.get_json()["id"]

        data = {
            "title": "To Delete",
            "category_id": str(cat_id),
            "file": (io.BytesIO(self._make_pdf_bytes()), "delete-me.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs",
            data=data,
            content_type="multipart/form-data",
        )
        pdf_data = resp.get_json()
        pdf_id = pdf_data["id"]

        with app.app_context():
            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"], pdf_data["filename"]
            )
            assert os.path.exists(filepath)

        # Delete
        resp = auth_client.delete(f"/admin/pdfs/{pdf_id}")
        assert resp.status_code == 200

        # Verify file removed from disk
        assert not os.path.exists(filepath)

    def test_upload_requires_auth(self, client):
        resp = client.post("/admin/pdfs", data={})
        assert resp.status_code == 302


class TestRateLimiting:
    def test_login_rate_limit(self, app, client):
        """After 5 failed logins, should be rate limited."""
        with app.app_context():
            admin = Admin(username="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()

        for _ in range(5):
            client.post(
                "/admin/login",
                data={"username": "admin", "password": "wrong"},
            )

        resp = client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong"},
        )
        assert resp.status_code == 429
