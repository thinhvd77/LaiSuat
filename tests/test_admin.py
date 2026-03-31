from extensions import db
from models import Admin, Category


def _get_parent_id(app, name="Lãi suất"):
    """Get the ID of a default parent category."""
    with app.app_context():
        cat = Category.query.filter_by(name=name, parent_id=None).first()
        return cat.id


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


class TestCategoryCRUD:
    def test_create_child_category(self, app, auth_client):
        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "Lãi suất tiết kiệm", "parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Lãi suất tiết kiệm"
        assert data["parent_id"] == parent_id

    def test_create_category_with_pdf(self, app, auth_client):
        """Create child category with optional PDF file."""
        import io

        parent_id = _get_parent_id(app)
        pdf_bytes = b"%PDF-1.4 fake pdf content for testing"

        resp = auth_client.post(
            "/admin/categories",
            data={
                "name": "Lãi suất cho vay",
                "parent_id": str(parent_id),
                "pdf_title": "Lãi suất tháng 3",
                "file": (io.BytesIO(pdf_bytes), "lai-suat.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Lãi suất cho vay"
        assert data["pdf_count"] == 1

    def test_create_root_category_with_pdf(self, auth_client):
        """Create root category with optional PDF file."""
        import io

        pdf_bytes = b"%PDF-1.4 fake pdf content for testing"
        resp = auth_client.post(
            "/admin/categories",
            data={
                "name": "Danh mục gốc mới",
                "pdf_title": "PDF danh mục gốc",
                "file": (io.BytesIO(pdf_bytes), "root-category.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Danh mục gốc mới"
        assert data["parent_id"] is None
        assert data["depth"] == 0
        assert data["pdf_count"] == 1

    def test_create_category_missing_name(self, app, auth_client):
        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_create_category_missing_parent(self, auth_client):
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "No Parent"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "No Parent"
        assert data["parent_id"] is None
        assert data["depth"] == 0

    def test_update_child_category(self, app, auth_client):
        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "Old Name", "parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        cat_id = resp.get_json()["id"]

        resp = auth_client.put(
            f"/admin/categories/{cat_id}",
            json={"name": "New Name", "sort_order": 5},
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "New Name"
        assert resp.get_json()["sort_order"] == 5

    def test_cannot_update_default_category(self, app, auth_client):
        parent_id = _get_parent_id(app)
        resp = auth_client.put(
            f"/admin/categories/{parent_id}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 400

    def test_cannot_delete_default_category(self, app, auth_client):
        parent_id = _get_parent_id(app)
        resp = auth_client.delete(f"/admin/categories/{parent_id}")
        assert resp.status_code == 400

    def test_delete_empty_child_category(self, app, auth_client):
        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "To Delete", "parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        cat_id = resp.get_json()["id"]

        resp = auth_client.delete(f"/admin/categories/{cat_id}")
        assert resp.status_code == 200

    def test_delete_category_with_pdfs_fails(self, app, auth_client):
        from models import Pdf

        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "Has PDFs", "parent_id": str(parent_id)},
            content_type="multipart/form-data",
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
        resp = client.post(
            "/admin/categories",
            data={"name": "X", "parent_id": "1"},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 302


import io
import os


class TestPdfUploadDelete:
    def _make_pdf_bytes(self):
        """Minimal valid PDF content (starts with %PDF-)."""
        return b"%PDF-1.4 fake pdf content for testing"

    def _create_child_category(self, app, auth_client):
        """Helper: create a child category and return its ID."""
        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "Test Cat", "parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        return resp.get_json()["id"]

    def test_upload_pdf(self, app, auth_client):
        cat_id = self._create_child_category(app, auth_client)

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

        with app.app_context():
            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"], result["filename"]
            )
            assert os.path.exists(filepath)

    def test_upload_to_parent_rejected(self, app, auth_client):
        """Can upload PDF directly to a root leaf category."""
        parent_id = _get_parent_id(app)
        data = {
            "title": "Direct to parent",
            "category_id": str(parent_id),
            "file": (io.BytesIO(self._make_pdf_bytes()), "test.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201

    def test_upload_non_pdf_rejected(self, app, auth_client):
        cat_id = self._create_child_category(app, auth_client)

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
        cat_id = self._create_child_category(app, auth_client)

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
        cat_id = self._create_child_category(app, auth_client)

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

        resp = auth_client.delete(f"/admin/pdfs/{pdf_id}")
        assert resp.status_code == 200
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


class TestThreeLevelCategories:
    def _create_l1(self, app, auth_client, name="L1 Cat"):
        parent_id = _get_parent_id(app)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": name, "parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        return resp.get_json()["id"]

    def test_create_l2_under_l1(self, app, auth_client):
        """Can create L2 category under L1."""
        l1_id = self._create_l1(app, auth_client)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "L2 Child", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "L2 Child"
        assert data["parent_id"] == l1_id
        assert data["depth"] == 2

    def test_reject_create_child_of_l2(self, app, auth_client):
        """Cannot create child under L2 (max depth reached)."""
        l1_id = self._create_l1(app, auth_client)
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "L2", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )
        l2_id = resp.get_json()["id"]

        resp = auth_client.post(
            "/admin/categories",
            data={"name": "L3 Rejected", "parent_id": str(l2_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_upload_pdf_to_l1_leaf(self, app, auth_client):
        """Can upload PDF to L1 leaf (no children)."""
        l1_id = self._create_l1(app, auth_client)
        data = {
            "title": "PDF on L1",
            "category_id": str(l1_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "l1.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 201

    def test_reject_upload_to_l1_with_children(self, app, auth_client):
        """Cannot upload PDF to L1 that has children (not a leaf)."""
        l1_id = self._create_l1(app, auth_client)
        # Add a child to make L1 non-leaf
        auth_client.post(
            "/admin/categories",
            data={"name": "L2 Child", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )

        data = {
            "title": "Should fail",
            "category_id": str(l1_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "fail.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 400

    def test_reject_add_child_to_category_with_pdfs(self, app, auth_client):
        """Cannot add child to L1 that already has PDFs."""
        l1_id = self._create_l1(app, auth_client)
        # Upload a PDF first
        data = {
            "title": "Existing PDF",
            "category_id": str(l1_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "existing.pdf"),
        }
        auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )

        # Try to add a child
        resp = auth_client.post(
            "/admin/categories",
            data={"name": "Should fail", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_delete_category_with_children_fails(self, app, auth_client):
        """Cannot delete L1 that has children."""
        l1_id = self._create_l1(app, auth_client)
        auth_client.post(
            "/admin/categories",
            data={"name": "L2 Child", "parent_id": str(l1_id)},
            content_type="multipart/form-data",
        )

        resp = auth_client.delete(f"/admin/categories/{l1_id}")
        assert resp.status_code == 400

    def test_upload_to_root_with_children_rejected(self, app, auth_client):
        """Cannot upload PDF to root category that already has children."""
        parent_id = _get_parent_id(app)
        auth_client.post(
            "/admin/categories",
            data={"name": "Root child", "parent_id": str(parent_id)},
            content_type="multipart/form-data",
        )
        data = {
            "title": "Root upload",
            "category_id": str(parent_id),
            "file": (io.BytesIO(b"%PDF-1.4 test"), "root.pdf"),
        }
        resp = auth_client.post(
            "/admin/pdfs", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 400
