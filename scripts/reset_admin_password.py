"""Reset the admin password in the local SQLite database.

Default behavior:
- database: app-compatible SQLite path from DATABASE_URL/.env, or instance/database.db
- username: admin
- password: admin123
- force_password_change: enabled
- backup: enabled
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import bcrypt


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_USERNAME = "quantri"
DEFAULT_PASSWORD = "Dientoan@6421"


class ResetPasswordError(Exception):
    """Raised for user-correctable reset failures."""


def read_dotenv_value(env_path, key):
    if not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        if name.strip() != key:
            continue

        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        return value

    return None


def database_url_to_path(database_url, root_dir=ROOT_DIR):
    if not database_url:
        return root_dir / "instance" / "database.db"

    if database_url == "sqlite:///:memory:":
        raise ResetPasswordError("In-memory SQLite databases cannot be reset by script.")

    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ResetPasswordError(
            "Only sqlite:/// DATABASE_URL values are supported by this script."
        )

    raw_path = database_url[len(prefix) :]
    if not raw_path:
        raise ResetPasswordError("DATABASE_URL does not include a SQLite file path.")

    path = Path(raw_path)
    if path.is_absolute():
        return path

    # Flask-SQLAlchemy resolves relative sqlite:/// paths from instance_path.
    return root_dir / "instance" / path


def resolve_database_path(db_arg=None, root_dir=ROOT_DIR):
    if db_arg:
        return Path(db_arg).expanduser().resolve()

    database_url = os.environ.get("DATABASE_URL") or read_dotenv_value(
        root_dir / ".env", "DATABASE_URL"
    )
    return database_url_to_path(database_url, root_dir=root_dir).resolve()


def make_backup_path(db_path):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base = db_path.with_name(f"{db_path.name}.backup-admin-reset-{timestamp}")

    candidate = base
    suffix = 1
    while candidate.exists():
        candidate = db_path.with_name(f"{base.name}-{suffix}")
        suffix += 1

    return candidate


def backup_database(db_path):
    backup_path = make_backup_path(db_path)
    source = sqlite3.connect(str(db_path))
    target = sqlite3.connect(str(backup_path))
    try:
        with source:
            with target:
                source.backup(target)
    finally:
        target.close()
        source.close()
    return backup_path


def ensure_admins_table(connection):
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'admins'"
    ).fetchone()
    if not row:
        raise ResetPasswordError("The admins table does not exist in this database.")


def reset_admin_password(
    db_path,
    username=DEFAULT_USERNAME,
    password=DEFAULT_PASSWORD,
    force_password_change=True,
    backup=True,
):
    db_path = Path(db_path)
    if not db_path.exists():
        raise ResetPasswordError(f"Database not found: {db_path}")

    backup_path = backup_database(db_path) if backup else None
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    force_value = 1 if force_password_change else 0
    created_at = datetime.now(timezone.utc).isoformat()

    connection = sqlite3.connect(str(db_path))
    try:
        ensure_admins_table(connection)
        existing = connection.execute(
            "SELECT id FROM admins WHERE username = ?", (username,)
        ).fetchone()

        if existing:
            connection.execute(
                """
                UPDATE admins
                SET password = ?, force_password_change = ?
                WHERE username = ?
                """,
                (password_hash, force_value, username),
            )
            action = "updated"
        else:
            connection.execute(
                """
                INSERT INTO admins (username, password, force_password_change, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, password_hash, force_value, created_at),
            )
            action = "created"

        connection.commit()
    finally:
        connection.close()

    return {
        "action": action,
        "username": username,
        "db_path": str(db_path),
        "backup_path": str(backup_path) if backup_path else None,
        "force_password_change": force_password_change,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Reset an admin account password in the SQLite database."
    )
    parser.add_argument("--db", help="Path to SQLite database. Defaults to app DB.")
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--no-force-password-change",
        action="store_true",
        help="Do not require password change after login.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a SQLite backup before changing the database.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    try:
        db_path = resolve_database_path(args.db)
        result = reset_admin_password(
            db_path,
            username=args.username,
            password=args.password,
            force_password_change=not args.no_force_password_change,
            backup=not args.no_backup,
        )
    except ResetPasswordError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Admin user {result['action']}: {result['username']}")
    print(f"Database: {result['db_path']}")
    if result["backup_path"]:
        print(f"Backup: {result['backup_path']}")
    if result["force_password_change"]:
        print("Password change is required on next login.")
    print("Default login is now admin / admin123 unless custom args were used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
