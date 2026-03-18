import io
import os

from models import db, Category, Pdf


class TestPublicHomepage:
    def test_homepage_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Tra cứu lãi suất".encode() in resp.data


class TestCategoriesAPI:
    def test_list_categories(self, app, client):
        with app.app_context():
            cat1 = Category(name="Tiết kiệm", icon="💰", sort_order=1)
            cat2 = Category(name="Cho vay", icon="🏦", sort_order=2)
            db.session.add_all([cat1, cat2])
            db.session.commit()

        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2
        assert data[0]["name"] == "Tiết kiệm"
        assert data[1]["name"] == "Cho vay"

    def test_list_categories_sorted(self, app, client):
        with app.app_context():
            cat1 = Category(name="Second", icon="📄", sort_order=2)
            cat2 = Category(name="First", icon="📄", sort_order=1)
            db.session.add_all([cat1, cat2])
            db.session.commit()

        resp = client.get("/api/categories")
        data = resp.get_json()
        assert data[0]["name"] == "First"
        assert data[1]["name"] == "Second"

    def test_empty_categories(self, client):
        resp = client.get("/api/categories")
        data = resp.get_json()
        assert data == []


class TestPdfsAPI:
    def test_list_pdfs_for_category(self, app, client):
        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            pdf1 = Pdf(
                category_id=cat.id,
                title="PDF A",
                filename="a.pdf",
                file_size=100,
            )
            pdf2 = Pdf(
                category_id=cat.id,
                title="PDF B",
                filename="b.pdf",
                file_size=200,
            )
            db.session.add_all([pdf1, pdf2])
            db.session.commit()
            cat_id = cat.id

        resp = client.get(f"/api/categories/{cat_id}/pdfs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2

    def test_pdfs_sorted_newest_first(self, app, client):
        from datetime import datetime, timezone, timedelta

        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            old = Pdf(
                category_id=cat.id,
                title="Old",
                filename="old.pdf",
                file_size=100,
                uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            new = Pdf(
                category_id=cat.id,
                title="New",
                filename="new.pdf",
                file_size=100,
                uploaded_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
            db.session.add_all([old, new])
            db.session.commit()
            cat_id = cat.id

        resp = client.get(f"/api/categories/{cat_id}/pdfs")
        data = resp.get_json()
        assert data[0]["title"] == "New"

    def test_pdfs_invalid_category(self, client):
        resp = client.get("/api/categories/999/pdfs")
        assert resp.status_code == 404


class TestServePdf:
    def test_serve_pdf(self, app, client):
        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            pdf = Pdf(
                category_id=cat.id,
                title="Test",
                filename="serve-test.pdf",
                file_size=100,
            )
            db.session.add(pdf)
            db.session.commit()

            # Write a fake PDF to disk
            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"], "serve-test.pdf"
            )
            with open(filepath, "wb") as f:
                f.write(b"%PDF-1.4 test content")

            pdf_id = pdf.id

        resp = client.get(f"/pdf/{pdf_id}")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"
        assert "inline" in resp.headers.get("Content-Disposition", "")

    def test_serve_missing_pdf(self, client):
        resp = client.get("/pdf/999")
        assert resp.status_code == 404

    def test_serve_pdf_missing_file(self, app, client):
        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            pdf = Pdf(
                category_id=cat.id,
                title="Missing",
                filename="does-not-exist.pdf",
                file_size=100,
            )
            db.session.add(pdf)
            db.session.commit()
            pdf_id = pdf.id

        resp = client.get(f"/pdf/{pdf_id}")
        assert resp.status_code == 404
