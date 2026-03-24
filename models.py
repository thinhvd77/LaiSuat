from datetime import datetime, timezone

import bcrypt
from flask_login import UserMixin

from extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_default = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    children = db.relationship(
        "Category",
        backref=db.backref("parent", remote_side="Category.id"),
        lazy="dynamic",
        passive_deletes=True,
    )
    pdfs = db.relationship(
        "Pdf", backref="category", lazy="dynamic", passive_deletes=True
    )

    @property
    def depth(self):
        """0 = root, 1 = level 1, 2 = level 2."""
        if self.parent_id is None:
            return 0
        if self.parent and self.parent.parent_id is None:
            return 1
        return 2

    @property
    def is_leaf(self):
        """True if category has no children. Only leaves can hold PDFs."""
        return self.children.count() == 0

    @property
    def can_have_children(self):
        """True if depth < 2 (root and level 1 can have children)."""
        return self.depth < 2

    def to_dict(self):
        d = {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "is_default": self.is_default,
            "sort_order": self.sort_order,
            "depth": self.depth,
            "is_leaf": self.is_leaf,
            "can_have_children": self.can_have_children,
        }
        if not self.is_leaf:
            d["children"] = [
                child.to_dict()
                for child in self.children.order_by(Category.sort_order.asc())
            ]
        else:
            d["pdf_count"] = self.pdfs.count()
        return d


class Pdf(db.Model):
    __tablename__ = "pdfs"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title = db.Column(db.Text, nullable=False)
    filename = db.Column(db.Text, unique=True, nullable=False)
    file_size = db.Column(db.Integer)
    uploaded_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    uploaded_by = db.Column(
        db.Integer,
        db.ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "filename": self.filename,
            "file_size": self.file_size,
            "uploaded_at": self.uploaded_at.isoformat()
            if self.uploaded_at
            else None,
        }


class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text, unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    force_password_change = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def set_password(self, raw_password):
        self.password = bcrypt.hashpw(
            raw_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.checkpw(
            raw_password.encode("utf-8"), self.password.encode("utf-8")
        )
