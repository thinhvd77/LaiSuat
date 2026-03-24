import pytest
from models import db, Category, Pdf, Admin


class TestCategoryModel:
    def test_create_child_category(self, app):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Lãi suất tiết kiệm", parent_id=parent.id, sort_order=1)
            db.session.add(child)
            db.session.commit()

            assert child.id is not None
            assert child.name == "Lãi suất tiết kiệm"
            assert child.parent_id == parent.id
            assert child.depth == 1
            assert child.created_at is not None

    def test_default_parent_categories_exist(self, app):
        with app.app_context():
            parents = Category.query.filter_by(parent_id=None).all()
            assert len(parents) == 3
            names = {p.name for p in parents}
            assert "Lãi suất" in names
            assert "Các chương trình tín dụng ưu đãi" in names
            assert "Phí dịch vụ" in names
            for p in parents:
                assert p.is_default is True
                assert p.depth == 0

    def test_parent_to_dict_includes_children(self, app):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Tiết kiệm", parent_id=parent.id, sort_order=1)
            db.session.add(child)
            db.session.commit()

            d = parent.to_dict()
            assert "children" in d
            assert len(d["children"]) == 1
            assert d["children"][0]["name"] == "Tiết kiệm"
            assert "pdf_count" in d["children"][0]

    def test_category_pdf_count(self, app):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            pdf = Pdf(
                category_id=child.id,
                title="Test PDF",
                filename="abc-test.pdf",
                file_size=1024,
            )
            db.session.add(pdf)
            db.session.commit()

            assert child.pdfs.count() == 1

    def test_cannot_delete_category_with_pdfs(self, app):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            pdf = Pdf(
                category_id=child.id,
                title="Test PDF",
                filename="abc-test.pdf",
                file_size=1024,
            )
            db.session.add(pdf)
            db.session.commit()

            db.session.delete(child)
            with pytest.raises(Exception):
                db.session.commit()

    def test_depth_property(self, app):
        with app.app_context():
            root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
            db.session.add(l1)
            db.session.commit()
            l2 = Category(name="Tiết kiệm online", parent_id=l1.id, sort_order=1)
            db.session.add(l2)
            db.session.commit()

            assert root.depth == 0
            assert l1.depth == 1
            assert l2.depth == 2

    def test_can_have_children(self, app):
        with app.app_context():
            root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
            db.session.add(l1)
            db.session.commit()
            l2 = Category(name="Tiết kiệm online", parent_id=l1.id, sort_order=1)
            db.session.add(l2)
            db.session.commit()

            assert root.can_have_children is True
            assert l1.can_have_children is True
            assert l2.can_have_children is False

    def test_is_leaf(self, app):
        with app.app_context():
            root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            # Root with no children is technically a leaf
            assert root.is_leaf is True

            l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
            db.session.add(l1)
            db.session.commit()

            # Root now has children, no longer a leaf
            assert root.is_leaf is False
            # L1 with no children is a leaf
            assert l1.is_leaf is True

    def test_to_dict_3_levels(self, app):
        with app.app_context():
            root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            l1 = Category(name="Tiết kiệm", parent_id=root.id, sort_order=1)
            db.session.add(l1)
            db.session.commit()
            l2 = Category(name="Online", parent_id=l1.id, sort_order=1)
            db.session.add(l2)
            db.session.commit()

            d = root.to_dict()
            assert d["depth"] == 0
            assert d["is_leaf"] is False
            assert d["can_have_children"] is True
            assert "children" in d
            assert len(d["children"]) == 1

            l1_dict = d["children"][0]
            assert l1_dict["depth"] == 1
            assert l1_dict["is_leaf"] is False
            assert l1_dict["can_have_children"] is True
            assert "children" in l1_dict
            assert len(l1_dict["children"]) == 1

            l2_dict = l1_dict["children"][0]
            assert l2_dict["depth"] == 2
            assert l2_dict["is_leaf"] is True
            assert l2_dict["can_have_children"] is False
            assert "pdf_count" in l2_dict
            assert "children" not in l2_dict

    def test_l1_leaf_to_dict_has_pdf_count(self, app):
        """L1 leaf (no children) should have pdf_count, not children."""
        with app.app_context():
            root = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            l1_leaf = Category(name="Liên ngân hàng", parent_id=root.id, sort_order=1)
            db.session.add(l1_leaf)
            db.session.commit()

            d = l1_leaf.to_dict()
            assert d["is_leaf"] is True
            assert d["can_have_children"] is True
            assert "pdf_count" in d
            assert "children" not in d


class TestPdfModel:
    def test_create_pdf(self, app):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            pdf = Pdf(
                category_id=child.id,
                title="Lãi suất tháng 3",
                filename="uuid-lai-suat-t3.pdf",
                file_size=245000,
            )
            db.session.add(pdf)
            db.session.commit()

            assert pdf.id is not None
            assert pdf.uploaded_at is not None
            assert pdf.category.name == "Test Child"

    def test_filename_unique(self, app):
        with app.app_context():
            parent = Category.query.filter_by(name="Lãi suất", parent_id=None).first()
            child = Category(name="Test Child", parent_id=parent.id)
            db.session.add(child)
            db.session.commit()

            pdf1 = Pdf(
                category_id=child.id,
                title="PDF 1",
                filename="same-name.pdf",
                file_size=100,
            )
            db.session.add(pdf1)
            db.session.commit()

            pdf2 = Pdf(
                category_id=child.id,
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
            a1 = Admin(username="unique_admin")
            a1.set_password("pass1")
            db.session.add(a1)
            db.session.commit()

            a2 = Admin(username="unique_admin")
            a2.set_password("pass2")
            db.session.add(a2)
            with pytest.raises(Exception):
                db.session.commit()
