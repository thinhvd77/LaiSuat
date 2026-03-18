# Interest Rate Lookup Website — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an internal web app where customers view interest rate PDFs by category and bank staff manage (upload/delete) those PDFs through an admin panel.

**Architecture:** Flask monolith with SQLite for metadata storage, file-system storage for PDFs, and PDF.js for in-browser rendering. Public side is a sidebar-plus-viewer layout driven by AJAX calls to internal JSON endpoints. Admin side is a sidebar-plus-list layout with category management and PDF upload/delete.

**Tech Stack:** Python 3, Flask 3.x, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Limiter, bcrypt, SQLite 3 (WAL mode), PDF.js 4.x, vanilla HTML/CSS/JS

**Spec:** `docs/superpowers/specs/2026-03-18-lai-suat-lookup-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `requirements.txt` | Python dependencies |
| `extensions.py` | Shared Flask extensions: db, login_manager, csrf, limiter |
| `models.py` | SQLAlchemy models: Category, Pdf, Admin |
| `app.py` | Flask app factory, config, CLI commands, route registration |
| `routes_public.py` | Blueprint: `GET /`, `/api/categories`, `/api/categories/<id>/pdfs`, `/pdf/<id>` |
| `routes_admin.py` | Blueprint: login, logout, admin dashboard, category CRUD, PDF upload/delete, change password |
| `templates/base.html` | Shared HTML layout (header, flash messages, scripts) |
| `templates/index.html` | Public page — sidebar + PDF.js viewer |
| `templates/login.html` | Admin login form |
| `templates/admin.html` | Admin dashboard — sidebar categories + PDF list |
| `templates/change_password.html` | Change password form |
| `static/css/style.css` | All styles for public + admin |
| `static/js/app.js` | Public page logic: fetch categories, fetch PDFs, render PDF.js |
| `static/js/admin.js` | Admin logic: category CRUD, PDF upload/delete via fetch() |
| `static/pdfjs/` | PDF.js 4.x library files (downloaded) |
| `tests/conftest.py` | Pytest fixtures: test client, test DB, test uploads dir |
| `tests/test_models.py` | Model unit tests |
| `tests/test_public.py` | Public route tests |
| `tests/test_admin.py` | Admin route tests (auth, categories, PDFs, change password) |

> **Note on spec §8:** The spec listed a single `app.py` for all routes. This plan splits routes into `routes_public.py` and `routes_admin.py` blueprints for better separation — each file stays focused and small. `app.py` becomes the factory that wires them together. The behavior and URL paths remain identical to the spec.

> **Note on PDF.js files:** The spec lists `pdf.min.js` / `pdf.worker.min.js`, but PDF.js 4.x ships as ES modules (`.mjs`). This plan downloads the `.min.mjs` versions which are the correct modern format.

---

## Task 1: Project Setup & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore` (update existing)

- [ ] **Step 1: Create requirements.txt**

```txt
Flask==3.1.1
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-WTF==1.2.2
Flask-Limiter==3.12
bcrypt==4.3.0
gunicorn==23.0.0
pytest==8.3.5
```

- [ ] **Step 2: Create Python virtual environment and install**

Run:
```bash
cd /home/thinh77/Projects/LaiSuat
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Expected: All packages install successfully.

- [ ] **Step 3: Update .gitignore**

Append to existing `.gitignore`:
```
venv/
*.pyc
database.db
uploads/*.pdf
```

- [ ] **Step 4: Download PDF.js 4.x**

```bash
mkdir -p static/pdfjs
cd static/pdfjs
curl -L -o pdf.min.mjs "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.9.155/build/pdf.min.mjs"
curl -L -o pdf.worker.min.mjs "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.9.155/build/pdf.worker.min.mjs"
cd /home/thinh77/Projects/LaiSuat
```

- [ ] **Step 5: Create uploads directory**

```bash
mkdir -p uploads
touch uploads/.gitkeep
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore static/pdfjs/ uploads/.gitkeep
git commit -m "chore: project setup — dependencies, PDF.js, uploads dir"
```

---

## Task 2: Database Models

**Files:**
- Create: `models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write model tests**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Write test fixtures**

Create `tests/__init__.py` (empty) and `tests/conftest.py`:

```python
import os
import shutil
import tempfile
import pytest
from app import create_app
from models import db as _db


@pytest.fixture
def app():
    """Create a test Flask app with an in-memory SQLite database."""
    db_fd, db_path = tempfile.mkstemp()
    upload_dir = tempfile.mkdtemp()

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "UPLOAD_FOLDER": upload_dir,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
        }
    )

    with app.app_context():
        _db.create_all()

    yield app

    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(upload_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    """A test client that is logged in as admin."""
    from models import Admin

    with app.app_context():
        admin = Admin(username="admin")
        admin.set_password("admin123")
        admin.force_password_change = False
        _db.session.add(admin)
        _db.session.commit()

    client.post(
        "/admin/login", data={"username": "admin", "password": "admin123"}
    )
    return client
```

- [ ] **Step 3: Run tests — expect FAIL (no models/app yet)**

Run: `cd /home/thinh77/Projects/LaiSuat && source venv/bin/activate && python -m pytest tests/test_models.py -v`
Expected: ImportError — `models` and `app` don't exist yet.

- [ ] **Step 4: Create models.py**

```python
from datetime import datetime, timezone

import bcrypt
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    icon = db.Column(db.Text, default="📄")
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    pdfs = db.relationship(
        "Pdf", backref="category", lazy="dynamic", passive_deletes=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "sort_order": self.sort_order,
            "pdf_count": self.pdfs.count(),
        }


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
```

- [ ] **Step 5: Create minimal app.py (factory only, no routes yet)**

```python
import os
import sys
import logging
from datetime import timedelta

from flask import Flask, render_template
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from models import db, Admin

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


def create_app(test_config=None):
    app = Flask(__name__)

    # Default config
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///database.db"
    )
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    if test_config:
        app.config.update(test_config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "admin.login"
    csrf.init_app(app)
    limiter.init_app(app)

    # Enable WAL mode for SQLite
    with app.app_context():
        from sqlalchemy import event

        @event.listens_for(db.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Logging
    logging.basicConfig(level=logging.INFO)

    # CLI: init-db
    @app.cli.command("init-db")
    def init_db():
        """Create tables and default admin user."""
        db.create_all()
        if not Admin.query.filter_by(username="admin").first():
            admin = Admin(username="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            app.logger.info("Default admin created: admin / admin123")
        app.logger.info("Database initialized.")

    # Ensure upload dir exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app


if __name__ == "__main__":
    app = create_app()
    if "--init-db" in sys.argv:
        with app.app_context():
            db.create_all()
            if not Admin.query.filter_by(username="admin").first():
                admin = Admin(username="admin")
                admin.set_password("admin123")
                db.session.add(admin)
                db.session.commit()
                print("Default admin created: admin / admin123")
            print("Database initialized.")
    else:
        app.run(debug=True)
```

- [ ] **Step 6: Run tests — expect PASS**

Run: `cd /home/thinh77/Projects/LaiSuat && source venv/bin/activate && python -m pytest tests/test_models.py -v`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add models.py app.py tests/
git commit -m "feat: database models — Category, Pdf, Admin with tests"
```

---

## Task 3: Admin Authentication Routes

**Files:**
- Create: `routes_admin.py`
- Create: `templates/base.html`
- Create: `templates/login.html`
- Create: `templates/change_password.html`
- Create: `tests/test_admin.py`
- Modify: `app.py` (register blueprint)

- [ ] **Step 1: Write auth tests**

Create `tests/test_admin.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_admin.py -v`
Expected: FAIL — routes don't exist yet.

- [ ] **Step 3: Create templates/base.html**

```html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Tra cứu lãi suất{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
    <div class="flash-messages">
        {% for category, message in messages %}
        <div class="flash flash-{{ category }}">{{ message }}</div>
        {% endfor %}
    </div>
    {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}

    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Create templates/login.html**

```html
{% extends "base.html" %}
{% block title %}Đăng nhập — Admin{% endblock %}

{% block content %}
<div class="login-container">
    <div class="login-card">
        <h1>Đăng nhập</h1>
        <p class="login-subtitle">Quản lý lãi suất ngân hàng</p>

        <form method="POST" action="{{ url_for('admin.login') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="form-group">
                <label for="username">Tên đăng nhập</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Mật khẩu</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Đăng nhập</button>
        </form>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Create templates/change_password.html**

```html
{% extends "base.html" %}
{% block title %}Đổi mật khẩu — Admin{% endblock %}

{% block content %}
<div class="login-container">
    <div class="login-card">
        <h1>Đổi mật khẩu</h1>
        {% if force %}
        <p class="login-subtitle">Bạn cần đổi mật khẩu mặc định trước khi tiếp tục.</p>
        {% endif %}

        <form method="POST" action="{{ url_for('admin.change_password') }}">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="form-group">
                <label for="current_password">Mật khẩu hiện tại</label>
                <input type="password" id="current_password" name="current_password" required>
            </div>
            <div class="form-group">
                <label for="new_password">Mật khẩu mới</label>
                <input type="password" id="new_password" name="new_password" required minlength="6">
            </div>
            <div class="form-group">
                <label for="confirm_password">Xác nhận mật khẩu mới</label>
                <input type="password" id="confirm_password" name="confirm_password" required minlength="6">
            </div>
            <button type="submit" class="btn btn-primary btn-full">Đổi mật khẩu</button>
        </form>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Create routes_admin.py**

```python
import logging

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from flask_login import login_user, logout_user, login_required, current_user

from models import db, Admin

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            session.permanent = True
            logger.info("Admin login: %s", username)

            if admin.force_password_change:
                return redirect(url_for("admin.change_password"))
            return redirect(url_for("admin.dashboard"))

        flash("Sai tên đăng nhập hoặc mật khẩu", "error")

    return render_template("login.html")


@admin_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logger.info("Admin logout: %s", current_user.username)
    logout_user()
    return redirect(url_for("admin.login"))


@admin_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    force = current_user.force_password_change

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Mật khẩu hiện tại không đúng", "error")
        elif new_password != confirm_password:
            flash("Mật khẩu mới không khớp", "error")
        elif len(new_password) < 6:
            flash("Mật khẩu mới phải có ít nhất 6 ký tự", "error")
        else:
            current_user.set_password(new_password)
            current_user.force_password_change = False
            db.session.commit()
            logger.info("Admin changed password: %s", current_user.username)
            flash("Đổi mật khẩu thành công", "success")
            return redirect(url_for("admin.dashboard"))

    return render_template("change_password.html", force=force)


@admin_bp.route("")
@login_required
def dashboard():
    if current_user.force_password_change:
        return redirect(url_for("admin.change_password"))
    return render_template("admin.html")
```

- [ ] **Step 7: Create placeholder templates/admin.html**

```html
{% extends "base.html" %}
{% block title %}Admin Panel{% endblock %}

{% block content %}
<div class="admin-container">
    <h1>Admin Panel</h1>
    <p>Dashboard placeholder — will be built in Task 6.</p>
</div>
{% endblock %}
```

- [ ] **Step 8: Register blueprint in app.py**

Add before `return app` in `create_app()`:

```python
    # Register blueprints
    from routes_admin import admin_bp

    app.register_blueprint(admin_bp)
```

- [ ] **Step 9: Create minimal static/css/style.css**

```css
/* Reset */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f5f5;
    color: #333;
    line-height: 1.6;
}

/* Flash messages */
.flash-messages { padding: 0 20px; }
.flash {
    padding: 12px 16px;
    margin: 10px 0;
    border-radius: 6px;
    font-size: 14px;
}
.flash-error { background: #fee2e2; color: #b91c1c; }
.flash-success { background: #d1fae5; color: #065f46; }

/* Login */
.login-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: #f0f2f5;
}
.login-card {
    background: white;
    padding: 40px;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    width: 100%;
    max-width: 400px;
}
.login-card h1 { font-size: 24px; margin-bottom: 8px; }
.login-subtitle { color: #666; margin-bottom: 24px; font-size: 14px; }
.form-group { margin-bottom: 16px; }
.form-group label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 6px;
}
.form-group input {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
}
.form-group input:focus {
    outline: none;
    border-color: #4f46e5;
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}
.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    font-weight: 500;
}
.btn-primary { background: #4f46e5; color: white; }
.btn-primary:hover { background: #4338ca; }
.btn-full { width: 100%; }
.btn-danger { background: #ef4444; color: white; }
.btn-danger:hover { background: #dc2626; }
.btn-sm { padding: 6px 12px; font-size: 12px; }
```

- [ ] **Step 10: Run tests — expect PASS**

Run: `python -m pytest tests/test_admin.py -v`
Expected: All auth tests pass.

- [ ] **Step 11: Commit**

```bash
git add routes_admin.py templates/ static/css/style.css tests/test_admin.py app.py
git commit -m "feat: admin authentication — login, logout, change password"
```

---

## Task 4: Admin Category CRUD

**Files:**
- Modify: `routes_admin.py`
- Modify: `tests/test_admin.py`

- [ ] **Step 1: Write category CRUD tests**

Append to `tests/test_admin.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_admin.py::TestCategoryCRUD -v`
Expected: FAIL — routes don't exist yet.

- [ ] **Step 3: Add category routes to routes_admin.py**

Append to `routes_admin.py`:

```python
from models import db, Admin, Category, Pdf


@admin_bp.route("/categories", methods=["POST"])
@login_required
def create_category():
    data = request.get_json()
    if not data or not data.get("name"):
        return {"error": "Tên danh mục là bắt buộc"}, 400

    max_order = db.session.query(db.func.max(Category.sort_order)).scalar() or 0
    cat = Category(
        name=data["name"],
        icon=data.get("icon", "📄"),
        sort_order=max_order + 1,
    )
    db.session.add(cat)
    db.session.commit()
    logger.info("Category created: %s (by %s)", cat.name, current_user.username)
    return cat.to_dict(), 201


@admin_bp.route("/categories/<int:cat_id>", methods=["PUT"])
@login_required
def update_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    data = request.get_json()
    if data.get("name"):
        cat.name = data["name"]
    if data.get("icon"):
        cat.icon = data["icon"]
    if "sort_order" in data:
        cat.sort_order = data["sort_order"]

    db.session.commit()
    logger.info("Category updated: %s (by %s)", cat.name, current_user.username)
    return cat.to_dict(), 200


@admin_bp.route("/categories/<int:cat_id>", methods=["DELETE"])
@login_required
def delete_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    if cat.pdfs.count() > 0:
        return {"error": "Không thể xóa danh mục còn tài liệu"}, 400

    db.session.delete(cat)
    db.session.commit()
    logger.info("Category deleted: %s (by %s)", cat.name, current_user.username)
    return {"message": "Đã xóa danh mục"}, 200
```

Also update the import at the top of `routes_admin.py`: add `Category, Pdf` to the import from `models`.

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_admin.py::TestCategoryCRUD -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add routes_admin.py tests/test_admin.py
git commit -m "feat: admin category CRUD — create, update, delete"
```

---

## Task 5: Admin PDF Upload & Delete

**Files:**
- Modify: `routes_admin.py`
- Modify: `tests/test_admin.py`

- [ ] **Step 1: Write PDF upload/delete tests**

Append to `tests/test_admin.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_admin.py::TestPdfUploadDelete -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Add PDF upload/delete routes to routes_admin.py**

Append to `routes_admin.py`:

```python
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


def _validate_pdf(file_storage):
    """Validate file is a PDF by extension and magic bytes."""
    if not file_storage or not file_storage.filename:
        return False, "Không có file"

    filename = file_storage.filename.lower()
    if not filename.endswith(".pdf"):
        return False, "Chỉ chấp nhận file PDF"

    # Check magic bytes
    header = file_storage.read(5)
    file_storage.seek(0)
    if header != b"%PDF-":
        return False, "Chỉ chấp nhận file PDF"

    return True, None


@admin_bp.route("/pdfs", methods=["POST"])
@login_required
def upload_pdf():
    title = request.form.get("title", "").strip()
    category_id = request.form.get("category_id")
    file = request.files.get("file")

    if not title:
        return {"error": "Tên tài liệu là bắt buộc"}, 400

    if not category_id:
        return {"error": "Danh mục là bắt buộc"}, 400

    cat = db.session.get(Category, int(category_id))
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    valid, error_msg = _validate_pdf(file)
    if not valid:
        return {"error": error_msg}, 400

    # Sanitize filename with UUID prefix
    original = secure_filename(file.filename)
    safe_filename = f"{uuid.uuid4().hex[:8]}-{original}"

    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], safe_filename)
    file.save(filepath)
    file_size = os.path.getsize(filepath)

    pdf = Pdf(
        category_id=cat.id,
        title=title,
        filename=safe_filename,
        file_size=file_size,
        uploaded_by=current_user.id,
    )
    db.session.add(pdf)
    db.session.commit()

    logger.info(
        "PDF uploaded: %s → %s (by %s)",
        title,
        safe_filename,
        current_user.username,
    )
    return pdf.to_dict(), 201


@admin_bp.route("/pdfs/<int:pdf_id>", methods=["DELETE"])
@login_required
def delete_pdf(pdf_id):
    pdf = db.session.get(Pdf, pdf_id)
    if not pdf:
        return {"error": "Không tìm thấy tài liệu"}, 404

    # Remove file from disk
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], pdf.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    logger.info(
        "PDF deleted: %s / %s (by %s)",
        pdf.title,
        pdf.filename,
        current_user.username,
    )
    db.session.delete(pdf)
    db.session.commit()

    return {"message": "Đã xóa tài liệu"}, 200
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_admin.py::TestPdfUploadDelete -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add routes_admin.py tests/test_admin.py
git commit -m "feat: admin PDF upload/delete with validation"
```

---

## Task 6: Public Routes & JSON API

**Files:**
- Create: `routes_public.py`
- Create: `templates/index.html`
- Create: `tests/test_public.py`
- Modify: `app.py` (register blueprint)

- [ ] **Step 1: Write public route tests**

Create `tests/test_public.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_public.py -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 3: Create routes_public.py**

```python
import os
import logging

from flask import Blueprint, render_template, send_file, current_app

from models import db, Category, Pdf

logger = logging.getLogger(__name__)

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/api/categories")
def list_categories():
    categories = Category.query.order_by(Category.sort_order.asc()).all()
    return [cat.to_dict() for cat in categories]


@public_bp.route("/api/categories/<int:cat_id>/pdfs")
def list_pdfs(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    pdfs = (
        Pdf.query.filter_by(category_id=cat_id)
        .order_by(Pdf.uploaded_at.desc())
        .all()
    )
    return [pdf.to_dict() for pdf in pdfs]


@public_bp.route("/pdf/<int:pdf_id>")
def serve_pdf(pdf_id):
    pdf = db.session.get(Pdf, pdf_id)
    if not pdf:
        return {"error": "Không tìm thấy tài liệu"}, 404

    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], pdf.filename)
    if not os.path.exists(filepath):
        logger.warning("PDF file missing from disk: %s", pdf.filename)
        return {"error": "Không tìm thấy tài liệu"}, 404

    return send_file(
        filepath,
        mimetype="application/pdf",
        download_name=pdf.filename,
        as_attachment=False,
    )
```

- [ ] **Step 4: Create templates/index.html**

```html
{% extends "base.html" %}
{% block title %}Tra cứu lãi suất{% endblock %}

{% block content %}
<div class="public-container">
    <header class="public-header">
        <h1>📊 Tra cứu lãi suất</h1>
    </header>

    <div class="public-layout">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-title">Danh mục</div>
            <div id="category-list">
                <p class="empty-state">Đang tải...</p>
            </div>
        </aside>

        <main class="viewer">
            <div class="viewer-toolbar" id="viewer-toolbar" style="display:none;">
                <span id="category-name" class="viewer-category-name"></span>
                <select id="pdf-select" class="pdf-select"></select>
            </div>
            <div id="pdf-viewer" class="pdf-viewer">
                <p class="empty-state" id="viewer-empty">
                    Chưa có danh mục lãi suất nào.
                </p>
            </div>
        </main>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='pdfjs/pdf.min.mjs') }}" type="module"></script>
<script src="{{ url_for('static', filename='js/app.js') }}" type="module"></script>
{% endblock %}
```

- [ ] **Step 5: Register public blueprint in app.py**

Add to `create_app()`:

```python
    from routes_public import public_bp
    app.register_blueprint(public_bp)
```

- [ ] **Step 6: Create placeholder static/js/app.js**

```javascript
// Public page logic — will be fully implemented in Task 8
console.log("app.js loaded");
```

- [ ] **Step 7: Run tests — expect PASS**

Run: `python -m pytest tests/test_public.py -v`
Expected: All tests pass.

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add routes_public.py templates/index.html static/js/app.js tests/test_public.py app.py
git commit -m "feat: public routes — homepage, categories API, PDF serving"
```

---

## Task 7: Admin Dashboard Frontend (HTML + JS)

**Files:**
- Modify: `templates/admin.html` (replace placeholder)
- Create: `static/js/admin.js`
- Modify: `static/css/style.css` (add admin styles)

- [ ] **Step 1: Build templates/admin.html**

```html
{% extends "base.html" %}
{% block title %}Admin Panel{% endblock %}

{% block content %}
<div class="admin-container">
    <header class="admin-header">
        <h1>🔧 Admin Panel</h1>
        <div class="admin-header-right">
            <span class="admin-user">{{ current_user.username }}</span>
            <a href="{{ url_for('admin.change_password') }}" class="btn btn-sm">Đổi mật khẩu</a>
            <form method="POST" action="{{ url_for('admin.logout') }}" style="display:inline">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button type="submit" class="btn btn-sm btn-danger">Đăng xuất</button>
            </form>
        </div>
    </header>

    <div class="admin-layout">
        <aside class="sidebar" id="admin-sidebar">
            <div class="sidebar-header">
                <span class="sidebar-title">Danh mục</span>
                <button class="btn btn-sm btn-primary" id="btn-add-category">+ Thêm</button>
            </div>
            <div id="admin-category-list"></div>
        </aside>

        <main class="admin-main" id="admin-main">
            <div id="admin-content">
                <p class="empty-state">Chọn danh mục để quản lý</p>
            </div>
        </main>
    </div>
</div>

<!-- Modal: Add/Edit Category -->
<div class="modal-overlay" id="category-modal" style="display:none">
    <div class="modal">
        <h2 id="category-modal-title">Thêm danh mục</h2>
        <form id="category-form">
            <div class="form-group">
                <label for="cat-name">Tên danh mục</label>
                <input type="text" id="cat-name" required>
            </div>
            <div class="form-group">
                <label for="cat-icon">Icon</label>
                <input type="text" id="cat-icon" value="📄" maxlength="4">
            </div>
            <input type="hidden" id="cat-id">
            <div class="modal-actions">
                <button type="button" class="btn" id="btn-cancel-category">Hủy</button>
                <button type="submit" class="btn btn-primary">Lưu</button>
            </div>
        </form>
    </div>
</div>

<!-- Modal: Upload PDF -->
<div class="modal-overlay" id="upload-modal" style="display:none">
    <div class="modal">
        <h2>Upload PDF</h2>
        <form id="upload-form">
            <div class="form-group">
                <label for="pdf-title">Tên hiển thị</label>
                <input type="text" id="pdf-title" required>
            </div>
            <div class="form-group">
                <label for="pdf-file">Chọn file PDF</label>
                <input type="file" id="pdf-file" accept=".pdf" required>
            </div>
            <input type="hidden" id="upload-category-id">
            <div class="modal-actions">
                <button type="button" class="btn" id="btn-cancel-upload">Hủy</button>
                <button type="submit" class="btn btn-primary">Upload</button>
            </div>
        </form>
    </div>
</div>
{% endblock %}

{% block scripts %}
<meta name="csrf-token" content="{{ csrf_token() }}">
<script src="{{ url_for('static', filename='js/admin.js') }}"></script>
{% endblock %}
```

- [ ] **Step 2: Build static/js/admin.js**

```javascript
const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]').content;

let currentCategoryId = null;

// ─── Helpers ───
async function api(url, options = {}) {
    const headers = { "X-CSRFToken": CSRF_TOKEN, ...options.headers };
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${resp.status}`);
    }
    return resp.json();
}

function showModal(id) {
    document.getElementById(id).style.display = "flex";
}
function hideModal(id) {
    document.getElementById(id).style.display = "none";
}

// ─── Categories ───
async function loadCategories() {
    const cats = await api("/api/categories");
    const list = document.getElementById("admin-category-list");
    if (cats.length === 0) {
        list.innerHTML = '<p class="empty-state">Chưa có danh mục nào</p>';
        return;
    }
    list.innerHTML = cats
        .map(
            (c) => `
        <div class="sidebar-item ${c.id === currentCategoryId ? "active" : ""}"
             data-id="${c.id}">
            <span class="sidebar-item-text">${c.icon} ${c.name}</span>
            <span class="sidebar-item-count">${c.pdf_count}</span>
            <div class="sidebar-item-actions">
                <button class="btn-icon" title="Lên" onclick="moveCategory(${c.id}, -1, event)">▲</button>
                <button class="btn-icon" title="Xuống" onclick="moveCategory(${c.id}, 1, event)">▼</button>
                <button class="btn-icon" title="Sửa" onclick="editCategory(${c.id}, event)">✏️</button>
                <button class="btn-icon btn-icon-danger" title="Xóa" onclick="deleteCategory(${c.id}, event)">🗑️</button>
            </div>
        </div>`
        )
        .join("");

    // Click to select
    list.querySelectorAll(".sidebar-item").forEach((el) => {
        el.addEventListener("click", () => {
            currentCategoryId = parseInt(el.dataset.id);
            loadCategories();
            loadPdfs(currentCategoryId);
        });
    });
}

async function moveCategory(id, direction, event) {
    event.stopPropagation();
    const cats = await api("/api/categories");
    const idx = cats.findIndex((c) => c.id === id);
    const swapIdx = idx + direction;
    if (swapIdx < 0 || swapIdx >= cats.length) return;

    // Swap sort_order
    await api(`/admin/categories/${cats[idx].id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: cats[swapIdx].sort_order }),
    });
    await api(`/admin/categories/${cats[swapIdx].id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sort_order: cats[idx].sort_order }),
    });
    loadCategories();
}

async function editCategory(id, event) {
    event.stopPropagation();
    const cats = await api("/api/categories");
    const cat = cats.find((c) => c.id === id);
    if (!cat) return;

    document.getElementById("category-modal-title").textContent = "Sửa danh mục";
    document.getElementById("cat-name").value = cat.name;
    document.getElementById("cat-icon").value = cat.icon;
    document.getElementById("cat-id").value = id;
    showModal("category-modal");
}

async function deleteCategory(id, event) {
    event.stopPropagation();
    if (!confirm("Bạn có chắc muốn xóa danh mục này?")) return;
    try {
        await api(`/admin/categories/${id}`, { method: "DELETE" });
        if (currentCategoryId === id) {
            currentCategoryId = null;
            document.getElementById("admin-content").innerHTML =
                '<p class="empty-state">Chọn danh mục để quản lý</p>';
        }
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
}

// ─── Add/Edit Category Form ───
document.getElementById("btn-add-category").addEventListener("click", () => {
    document.getElementById("category-modal-title").textContent = "Thêm danh mục";
    document.getElementById("cat-name").value = "";
    document.getElementById("cat-icon").value = "📄";
    document.getElementById("cat-id").value = "";
    showModal("category-modal");
});

document.getElementById("btn-cancel-category").addEventListener("click", () => {
    hideModal("category-modal");
});

document.getElementById("category-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("cat-name").value.trim();
    const icon = document.getElementById("cat-icon").value.trim();
    const id = document.getElementById("cat-id").value;

    try {
        if (id) {
            await api(`/admin/categories/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, icon }),
            });
        } else {
            await api("/admin/categories", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, icon }),
            });
        }
        hideModal("category-modal");
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
});

// ─── PDFs ───
async function loadPdfs(categoryId) {
    const cats = await api("/api/categories");
    const cat = cats.find((c) => c.id === categoryId);
    if (!cat) return;

    const pdfs = await api(`/api/categories/${categoryId}/pdfs`);
    const content = document.getElementById("admin-content");

    let html = `
        <div class="admin-content-header">
            <h2>${cat.icon} ${cat.name} (${pdfs.length} file)</h2>
            <button class="btn btn-primary btn-sm" onclick="openUploadModal(${categoryId})">+ Upload PDF</button>
        </div>
    `;

    if (pdfs.length === 0) {
        html += '<p class="empty-state">Chưa có tài liệu nào trong danh mục này.</p>';
    } else {
        html += pdfs
            .map(
                (p) => `
            <div class="pdf-item">
                <div class="pdf-item-info">
                    <span class="pdf-item-title">📄 ${p.title}</span>
                    <span class="pdf-item-meta">${formatDate(p.uploaded_at)} · ${formatSize(p.file_size)}</span>
                </div>
                <div class="pdf-item-actions">
                    <a href="/pdf/${p.id}" target="_blank" class="btn btn-sm">Xem</a>
                    <button class="btn btn-sm btn-danger" onclick="deletePdf(${p.id})">Xóa</button>
                </div>
            </div>`
            )
            .join("");
    }

    content.innerHTML = html;
}

async function deletePdf(id) {
    if (!confirm("Bạn có chắc muốn xóa tài liệu này?")) return;
    try {
        await api(`/admin/pdfs/${id}`, { method: "DELETE" });
        loadPdfs(currentCategoryId);
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
}

// ─── Upload Modal ───
function openUploadModal(categoryId) {
    document.getElementById("upload-category-id").value = categoryId;
    document.getElementById("pdf-title").value = "";
    document.getElementById("pdf-file").value = "";
    showModal("upload-modal");
}

document.getElementById("btn-cancel-upload").addEventListener("click", () => {
    hideModal("upload-modal");
});

document.getElementById("upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("pdf-title").value.trim();
    const file = document.getElementById("pdf-file").files[0];
    const categoryId = document.getElementById("upload-category-id").value;

    if (!title || !file) return;

    const formData = new FormData();
    formData.append("title", title);
    formData.append("file", file);
    formData.append("category_id", categoryId);

    try {
        await fetch("/admin/pdfs", {
            method: "POST",
            headers: { "X-CSRFToken": CSRF_TOKEN },
            body: formData,
        }).then((r) => {
            if (!r.ok) return r.json().then((d) => Promise.reject(new Error(d.error)));
            return r.json();
        });
        hideModal("upload-modal");
        loadPdfs(parseInt(categoryId));
        loadCategories();
    } catch (e) {
        alert(e.message);
    }
});

// ─── Helpers ───
function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("vi-VN");
}
function formatSize(bytes) {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// ─── Init ───
loadCategories();
```

- [ ] **Step 3: Add admin styles to static/css/style.css**

Append to `style.css`:

```css
/* Admin layout */
.admin-container { min-height: 100vh; display: flex; flex-direction: column; }
.admin-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 20px; background: white; border-bottom: 1px solid #e5e7eb;
}
.admin-header h1 { font-size: 18px; }
.admin-header-right { display: flex; align-items: center; gap: 8px; }
.admin-user { font-size: 13px; color: #666; }
.admin-layout { display: flex; flex: 1; }

/* Sidebar shared */
.sidebar {
    width: 280px; min-width: 280px;
    background: white; border-right: 1px solid #e5e7eb;
    padding: 16px; overflow-y: auto;
}
.sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.sidebar-title { font-weight: 600; font-size: 14px; }
.sidebar-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 12px; border-radius: 6px; cursor: pointer;
    margin-bottom: 4px; font-size: 14px;
}
.sidebar-item:hover { background: #f3f4f6; }
.sidebar-item.active { background: #eef2ff; color: #4f46e5; }
.sidebar-item-text { flex: 1; }
.sidebar-item-count { font-size: 12px; color: #999; margin: 0 8px; }
.sidebar-item-actions { display: none; gap: 2px; }
.sidebar-item:hover .sidebar-item-actions { display: flex; }
.sidebar-item:hover .sidebar-item-count { display: none; }
.btn-icon {
    background: none; border: none; cursor: pointer;
    padding: 2px 4px; border-radius: 4px; font-size: 12px;
}
.btn-icon:hover { background: #e5e7eb; }
.btn-icon-danger:hover { background: #fee2e2; }

/* Admin main */
.admin-main { flex: 1; padding: 20px; overflow-y: auto; }
.admin-content-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 16px;
}
.admin-content-header h2 { font-size: 18px; }

/* PDF items */
.pdf-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 16px; background: white; border-radius: 8px;
    margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.pdf-item-info { display: flex; flex-direction: column; gap: 4px; }
.pdf-item-title { font-size: 14px; font-weight: 500; }
.pdf-item-meta { font-size: 12px; color: #999; }
.pdf-item-actions { display: flex; gap: 6px; }

/* Modal */
.modal-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5); display: flex;
    justify-content: center; align-items: center; z-index: 100;
}
.modal {
    background: white; border-radius: 12px; padding: 24px;
    width: 100%; max-width: 440px; box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}
.modal h2 { margin-bottom: 16px; font-size: 18px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

/* Empty state */
.empty-state {
    text-align: center; color: #999; padding: 40px 20px; font-size: 14px;
}
```

- [ ] **Step 4: Manually test the admin panel in browser**

Run: `source venv/bin/activate && python app.py --init-db && python app.py`
Open: `http://localhost:5000/admin/login`
Login: `admin` / `admin123`
Test: Change password → add categories → upload PDFs → delete PDFs → delete categories.

- [ ] **Step 5: Commit**

```bash
git add templates/admin.html static/js/admin.js static/css/style.css
git commit -m "feat: admin dashboard frontend — category management & PDF upload"
```

---

## Task 8: Public Page Frontend (PDF.js Viewer)

**Files:**
- Modify: `templates/index.html` (already created, may need tweaks)
- Modify: `static/js/app.js` (replace placeholder)
- Modify: `static/css/style.css` (add public styles)

- [ ] **Step 1: Build static/js/app.js**

```javascript
let currentCategoryId = null;
let currentPdfId = null;
let pdfDoc = null;

// ─── PDF.js Setup ───
const pdfjsLib = await import("/static/pdfjs/pdf.min.mjs");
pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.mjs";

// ─── Categories ───
async function loadCategories() {
    const resp = await fetch("/api/categories");
    const cats = await resp.json();

    const list = document.getElementById("category-list");
    if (cats.length === 0) {
        list.innerHTML = '<p class="empty-state">Chưa có danh mục lãi suất nào.</p>';
        document.getElementById("viewer-empty").textContent = "Chưa có danh mục lãi suất nào.";
        return;
    }

    list.innerHTML = cats
        .map(
            (c) => `
        <div class="sidebar-item ${c.id === currentCategoryId ? "active" : ""}"
             data-id="${c.id}">
            <span class="sidebar-item-text">${c.icon} ${c.name}</span>
            <span class="sidebar-item-count">${c.pdf_count}</span>
        </div>`
        )
        .join("");

    list.querySelectorAll(".sidebar-item").forEach((el) => {
        el.addEventListener("click", () => {
            currentCategoryId = parseInt(el.dataset.id);
            loadCategories();
            loadPdfs(currentCategoryId);
        });
    });

    // Auto-select first if none selected
    if (!currentCategoryId && cats.length > 0) {
        currentCategoryId = cats[0].id;
        loadCategories();
        loadPdfs(currentCategoryId);
    }
}

// ─── PDFs ───
async function loadPdfs(categoryId) {
    const toolbar = document.getElementById("viewer-toolbar");
    const viewerEmpty = document.getElementById("viewer-empty");
    const select = document.getElementById("pdf-select");
    const catName = document.getElementById("category-name");

    const catsResp = await fetch("/api/categories");
    const cats = await catsResp.json();
    const cat = cats.find((c) => c.id === categoryId);
    if (cat) catName.textContent = `${cat.icon} ${cat.name}`;

    const resp = await fetch(`/api/categories/${categoryId}/pdfs`);
    const pdfs = await resp.json();

    if (pdfs.length === 0) {
        toolbar.style.display = "none";
        viewerEmpty.textContent = "Chưa có tài liệu nào trong danh mục này.";
        viewerEmpty.style.display = "block";
        clearPdfViewer();
        return;
    }

    toolbar.style.display = "flex";
    viewerEmpty.style.display = "none";

    select.innerHTML = pdfs
        .map((p) => `<option value="${p.id}">${p.title}</option>`)
        .join("");

    select.onchange = () => renderPdf(parseInt(select.value));

    // Auto-render first (newest)
    renderPdf(pdfs[0].id);
}

// ─── PDF Rendering ───
async function renderPdf(pdfId) {
    currentPdfId = pdfId;
    const container = document.getElementById("pdf-viewer");
    clearPdfViewer();

    try {
        pdfDoc = await pdfjsLib.getDocument(`/pdf/${pdfId}`).promise;

        for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
            const page = await pdfDoc.getPage(pageNum);
            const scale = 1.5;
            const viewport = page.getViewport({ scale });

            const canvas = document.createElement("canvas");
            canvas.className = "pdf-page";
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            container.appendChild(canvas);

            const ctx = canvas.getContext("2d");
            await page.render({ canvasContext: ctx, viewport }).promise;
        }
    } catch (err) {
        container.innerHTML =
            '<p class="empty-state">Không tìm thấy tài liệu. Vui lòng liên hệ quản trị viên.</p>';
    }
}

function clearPdfViewer() {
    const container = document.getElementById("pdf-viewer");
    container.querySelectorAll("canvas").forEach((c) => c.remove());
    if (pdfDoc) {
        pdfDoc.destroy();
        pdfDoc = null;
    }
}

// ─── Init ───
loadCategories();
```

- [ ] **Step 2: Add public styles to static/css/style.css**

Append to `style.css`:

```css
/* Public layout */
.public-container { min-height: 100vh; display: flex; flex-direction: column; }
.public-header {
    padding: 16px 20px; background: white;
    border-bottom: 1px solid #e5e7eb;
}
.public-header h1 { font-size: 20px; }
.public-layout { display: flex; flex: 1; }

/* Viewer */
.viewer { flex: 1; display: flex; flex-direction: column; background: #e5e7eb; }
.viewer-toolbar {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 16px; background: white; border-bottom: 1px solid #e5e7eb;
}
.viewer-category-name { font-weight: 600; font-size: 14px; }
.pdf-select {
    padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px;
    font-size: 13px; background: white;
}
.pdf-viewer {
    flex: 1; overflow-y: auto; padding: 16px;
    display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.pdf-page {
    max-width: 100%; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    border-radius: 4px;
}
```

- [ ] **Step 3: Manually test the public page in browser**

Run: `python app.py` (if not running)
Open: `http://localhost:5000`
Test: sidebar navigation → PDF rendering → dropdown switching → empty states.

- [ ] **Step 4: Commit**

```bash
git add static/js/app.js static/css/style.css templates/index.html
git commit -m "feat: public page frontend — PDF.js viewer with category sidebar"
```

---

## Task 9: Rate Limiting & Final Security

**Files:**
- Create: `extensions.py`
- Modify: `app.py` (import extensions from `extensions.py`)
- Modify: `routes_admin.py` (import limiter from `extensions.py`, add rate limit decorator)
- Modify: `tests/test_admin.py` (add rate limit test)

- [ ] **Step 1: Write rate limit test**

Append to `tests/test_admin.py`:

```python
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
```

- [ ] **Step 2: Extract extensions to avoid circular imports**

Create `extensions.py`:

```python
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
```

Update `models.py` — change `from flask_sqlalchemy import SQLAlchemy` / `db = SQLAlchemy()` to:

```python
from extensions import db
```

Update `app.py` — change extension imports to:

```python
from extensions import db, login_manager, csrf, limiter
from models import Admin
```

Remove the `db`, `login_manager`, `csrf`, `limiter` definitions from `app.py` (they're now in `extensions.py`).

- [ ] **Step 3: Add rate limit to login route**

In `routes_admin.py`, add import and decorator:

```python
from extensions import limiter

@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            session.permanent = True
            logger.info("Admin login: %s", username)

            if admin.force_password_change:
                return redirect(url_for("admin.change_password"))
            return redirect(url_for("admin.dashboard"))

        flash("Sai tên đăng nhập hoặc mật khẩu", "error")

    return render_template("login.html")
```

- [ ] **Step 4: Run all tests — expect PASS**

Run: `python -m pytest tests/ -v`
Expected: All tests pass including rate limit test (429 on 6th attempt).

- [ ] **Step 5: Commit**

```bash
git add extensions.py app.py models.py routes_admin.py tests/test_admin.py
git commit -m "refactor: extract extensions.py, add rate limiting on login"
```

---

## Task 10: Error Pages & Final Polish

**Files:**
- Create: `templates/errors/404.html`
- Create: `templates/errors/413.html`
- Create: `templates/errors/500.html`
- Modify: `app.py` (register error handlers)
- Modify: `tests/test_public.py` (add error page tests)

- [ ] **Step 1: Write error page tests**

Append to `tests/test_public.py`:

```python
class TestErrorPages:
    def test_404_page(self, client):
        resp = client.get("/nonexistent-page")
        assert resp.status_code == 404
        assert "Không tìm thấy".encode() in resp.data

    def test_404_missing_pdf(self, client):
        resp = client.get("/pdf/99999")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_public.py::TestErrorPages -v`
Expected: FAIL — error templates don't exist yet (default Flask 404).

- [ ] **Step 3: Create error templates**

Create `templates/errors/404.html`:

```html
{% extends "base.html" %}
{% block title %}404 — Không tìm thấy{% endblock %}
{% block content %}
<div class="error-page">
    <h1>404</h1>
    <p>Không tìm thấy tài liệu</p>
    <a href="/" class="btn btn-primary">Về trang chủ</a>
</div>
{% endblock %}
```

Create `templates/errors/413.html`:

```html
{% extends "base.html" %}
{% block title %}413 — File quá lớn{% endblock %}
{% block content %}
<div class="error-page">
    <h1>413</h1>
    <p>File vượt quá 16MB</p>
    <a href="javascript:history.back()" class="btn btn-primary">Quay lại</a>
</div>
{% endblock %}
```

Create `templates/errors/500.html`:

```html
{% extends "base.html" %}
{% block title %}500 — Lỗi server{% endblock %}
{% block content %}
<div class="error-page">
    <h1>500</h1>
    <p>Đã xảy ra lỗi. Vui lòng thử lại sau.</p>
    <a href="/" class="btn btn-primary">Về trang chủ</a>
</div>
{% endblock %}
```

- [ ] **Step 4: Register error handlers in app.py**

Add inside `create_app()`:

```python
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500
```

Add `render_template` to the existing import from `flask` in `app.py`.

- [ ] **Step 5: Add error page styles to style.css**

Append:

```css
/* Error pages */
.error-page {
    display: flex; flex-direction: column;
    justify-content: center; align-items: center;
    min-height: 100vh; text-align: center;
}
.error-page h1 { font-size: 72px; color: #ddd; margin-bottom: 8px; }
.error-page p { color: #666; margin-bottom: 20px; }
```

- [ ] **Step 6: Run error page tests — expect PASS**

Run: `python -m pytest tests/test_public.py::TestErrorPages -v`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add templates/errors/ app.py static/css/style.css tests/test_public.py
git commit -m "feat: error pages — 404, 413, 500 with tests"
```

---

## Task 11: Full Integration Test & Manual Smoke Test

**Files:**
- No new files — run all tests and manual check

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Manual smoke test**

```bash
# Start fresh
rm -f database.db
python app.py --init-db
python app.py
```

Open browser and test the full flow:
1. `http://localhost:5000` — should show empty public page
2. `http://localhost:5000/admin/login` — login with `admin`/`admin123`
3. Forced to change password → change it
4. Create 3 categories (Tiết kiệm, Cho vay, Thẻ tín dụng)
5. Upload a real PDF to each category
6. Reorder categories with ▲▼
7. Go to `http://localhost:5000` — verify sidebar, PDF viewer, dropdown all work
8. Delete a PDF, delete an empty category
9. Test error: try to delete a category with PDFs → should show error
10. Test error: upload a `.txt` file renamed to `.pdf` → should reject

- [ ] **Step 3: Commit any fixes from smoke test**

```bash
git add -A
git commit -m "fix: smoke test fixes"
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete interest rate lookup website v1.0"
```
