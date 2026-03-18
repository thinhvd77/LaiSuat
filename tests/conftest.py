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
