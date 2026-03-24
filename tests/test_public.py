import io
import os

from models import db, Category, Pdf


class TestPublicHomepage:
    def test_homepage_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Tra cứu lãi suất".encode() in resp.data


class TestCategoriesAPI:
    def test_list_categories_returns_parents(self, app, client):
        """API returns 3 default parent categories with children arrays."""
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 3
        assert data[0]["name"] == "Lãi suất"
        assert "children" in data[0]

    def test_list_categories_with_children(self, app, client):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child1 = Category(name="Tiết kiệm", parent_id=parent.id, sort_order=1)
            child2 = Category(name="Cho vay", parent_id=parent.id, sort_order=2)
            db.session.add_all([child1, child2])
            db.session.commit()

        resp = client.get("/api/categories")
        data = resp.get_json()
        lai_suat = data[0]
        assert lai_suat["name"] == "Lãi suất"
        assert len(lai_suat["children"]) == 2
        assert lai_suat["children"][0]["name"] == "Tiết kiệm"
        assert lai_suat["children"][1]["name"] == "Cho vay"

    def test_categories_sorted_by_sort_order(self, app, client):
        resp = client.get("/api/categories")
        data = resp.get_json()
        assert data[0]["name"] == "Lãi suất"
        assert data[1]["name"] == "Các chương trình tín dụng ưu đãi"
        assert data[2]["name"] == "Phí dịch vụ"


class TestPdfsAPI:
    def test_list_pdfs_for_category(self, app, client):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            pdf1 = Pdf(
                category_id=child.id,
                title="PDF A",
                filename="a.pdf",
                file_size=100,
            )
            pdf2 = Pdf(
                category_id=child.id,
                title="PDF B",
                filename="b.pdf",
                file_size=200,
            )
            db.session.add_all([pdf1, pdf2])
            db.session.commit()
            cat_id = child.id

        resp = client.get(f"/api/categories/{cat_id}/pdfs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 2

    def test_pdfs_sorted_newest_first(self, app, client):
        from datetime import datetime, timezone

        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            old = Pdf(
                category_id=child.id,
                title="Old",
                filename="old.pdf",
                file_size=100,
                uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            new = Pdf(
                category_id=child.id,
                title="New",
                filename="new.pdf",
                file_size=100,
                uploaded_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
            db.session.add_all([old, new])
            db.session.commit()
            cat_id = child.id

        resp = client.get(f"/api/categories/{cat_id}/pdfs")
        data = resp.get_json()
        assert data[0]["title"] == "New"

    def test_pdfs_invalid_category(self, client):
        resp = client.get("/api/categories/999/pdfs")
        assert resp.status_code == 404


class TestServePdf:
    def test_serve_pdf(self, app, client):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            pdf = Pdf(
                category_id=child.id,
                title="Test",
                filename="serve-test.pdf",
                file_size=100,
            )
            db.session.add(pdf)
            db.session.commit()

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
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            pdf = Pdf(
                category_id=child.id,
                title="Missing",
                filename="does-not-exist.pdf",
                file_size=100,
            )
            db.session.add(pdf)
            db.session.commit()
            pdf_id = pdf.id

        resp = client.get(f"/pdf/{pdf_id}")
        assert resp.status_code == 404


class TestErrorPages:
    def test_404_page(self, client):
        resp = client.get("/nonexistent-page")
        assert resp.status_code == 404
        assert "Không tìm thấy".encode() in resp.data

    def test_404_missing_pdf(self, client):
        resp = client.get("/pdf/99999")
        assert resp.status_code == 404
