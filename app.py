import os
import sys
import logging
from datetime import timedelta

from flask import Flask, render_template

from extensions import db, login_manager, csrf, limiter
from models import Admin, Category


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
    app.config["SITE_GATE_ENABLED"] = os.environ.get("SITE_GATE_ENABLED", "false").lower() == "true"
    app.config["SITE_GATE_PASSWORD"] = os.environ.get("SITE_GATE_PASSWORD", "")
    app.config["SITE_GATE_TTL_MINUTES"] = int(os.environ.get("SITE_GATE_TTL_MINUTES", "1440"))

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

        # Seed default parent categories
        default_parents = [
            "Lãi suất",
            "Các chương trình tín dụng ưu đãi",
            "Phí dịch vụ",
        ]
        for i, name in enumerate(default_parents, start=1):
            if not Category.query.filter_by(name=name, parent_id=None, is_default=True).first():
                cat = Category(name=name, is_default=True, sort_order=i)
                db.session.add(cat)
        db.session.commit()

        app.logger.info("Database initialized.")

    # Ensure upload dir exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Register blueprints
    from routes_admin import admin_bp
    app.register_blueprint(admin_bp)

    from routes_public import public_bp
    app.register_blueprint(public_bp)

    # IP restriction middleware (disabled in test mode)
    # if not test_config:
    #     from middleware import init_ip_restriction
    #     init_ip_restriction(app)

    from site_gate import init_site_gate
    init_site_gate(app)

    if app.config["SITE_GATE_ENABLED"] and not app.config.get("SITE_GATE_PASSWORD"):
        app.logger.warning(
            "SITE_GATE_ENABLED=true but SITE_GATE_PASSWORD is empty; site gate will deny unlock"
        )

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    return app


if __name__ == "__main__":
    app = create_app()
    if "--init-db" in sys.argv:
        with app.app_context():
            db.create_all()
            if not Admin.query.filter_by(username="quantri").first():
                admin = Admin(username="quantri")
                admin.set_password("admin123")
                db.session.add(admin)
                db.session.commit()
                print("Default admin created: quantri / admin123")

            default_parents = [
                "Lãi suất",
                "Các chương trình tín dụng ưu đãi",
                "Phí dịch vụ",
            ]
            for i, name in enumerate(default_parents, start=1):
                if not Category.query.filter_by(name=name, parent_id=None, is_default=True).first():
                    cat = Category(name=name, is_default=True, sort_order=i)
                    db.session.add(cat)
            db.session.commit()

            print("Database initialized.")
    else:
        app.run(debug=True)
