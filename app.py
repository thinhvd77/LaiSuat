import os
import sys
import logging
from datetime import timedelta

from flask import Flask
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
