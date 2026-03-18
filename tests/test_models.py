import pytest
from models import db, Category, Pdf, Admin


class TestCategoryModel:
    def test_create_category(self, app):
        with app.app_context():
            cat = Category(name="Lãi suất tiết kiệm", icon="💰", sort_order=1)
            db.session.add(cat)
            db.session.commit()

            assert cat.id is not None
            assert cat.name == "Lãi suất tiết kiệm"
            assert cat.icon == "💰"
            assert cat.sort_order == 1
            assert cat.created_at is not None

    def test_category_pdf_count(self, app):
        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            pdf = Pdf(
                category_id=cat.id,
                title="Test PDF",
                filename="abc-test.pdf",
                file_size=1024,
            )
            db.session.add(pdf)
            db.session.commit()

            assert cat.pdfs.count() == 1

    def test_cannot_delete_category_with_pdfs(self, app):
        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            pdf = Pdf(
                category_id=cat.id,
                title="Test PDF",
                filename="abc-test.pdf",
                file_size=1024,
            )
            db.session.add(pdf)
            db.session.commit()

            db.session.delete(cat)
            with pytest.raises(Exception):
                db.session.commit()


class TestPdfModel:
    def test_create_pdf(self, app):
        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            pdf = Pdf(
                category_id=cat.id,
                title="Lãi suất tháng 3",
                filename="uuid-lai-suat-t3.pdf",
                file_size=245000,
            )
            db.session.add(pdf)
            db.session.commit()

            assert pdf.id is not None
            assert pdf.uploaded_at is not None
            assert pdf.category.name == "Test"

    def test_filename_unique(self, app):
        with app.app_context():
            cat = Category(name="Test", icon="📄")
            db.session.add(cat)
            db.session.commit()

            pdf1 = Pdf(
                category_id=cat.id,
                title="PDF 1",
                filename="same-name.pdf",
                file_size=100,
            )
            db.session.add(pdf1)
            db.session.commit()

            pdf2 = Pdf(
                category_id=cat.id,
                title="PDF 2",
                filename="same-name.pdf",
                file_size=200,
            )
            db.session.add(pdf2)
            with pytest.raises(Exception):
                db.session.commit()


class TestAdminModel:
    def test_create_admin(self, app):
        with app.app_context():
            admin = Admin(username="testadmin")
            admin.set_password("secret123")
            db.session.add(admin)
            db.session.commit()

            assert admin.id is not None
            assert admin.force_password_change is True
            assert admin.check_password("secret123") is True
            assert admin.check_password("wrong") is False

    def test_username_unique(self, app):
        with app.app_context():
            a1 = Admin(username="admin")
            a1.set_password("pass1")
            db.session.add(a1)
            db.session.commit()

            a2 = Admin(username="admin")
            a2.set_password("pass2")
            db.session.add(a2)
            with pytest.raises(Exception):
                db.session.commit()
