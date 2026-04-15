import logging
from datetime import datetime, timedelta, timezone

from flask import abort, render_template, request, session
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import SiteGateLock

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
SESSION_OK_KEY = "site_gate_ok"
SESSION_UNTIL_KEY = "site_gate_until"


def now_utc():
    return datetime.now(timezone.utc)


def _to_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_public_protected_path(path):
    return path == "/" or path.startswith("/api/") or path.startswith("/pdf/")


def get_site_gate_ip():
    remote_addr = request.remote_addr or ""

    # Trust X-Real-IP only when request comes from local reverse proxy.
    if remote_addr in ("127.0.0.1", "::1"):
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    return remote_addr


def _get_or_create_lock_row(ip):
    row = SiteGateLock.query.filter_by(ip_address=ip).first()
    if row:
        return row

    row = SiteGateLock(ip_address=ip, failed_attempts=0, locked_until=None)
    db.session.add(row)

    try:
        db.session.flush()
        return row
    except IntegrityError:
        # Another concurrent request created the row first.
        db.session.rollback()
        existing = SiteGateLock.query.filter_by(ip_address=ip).first()
        if existing:
            return existing
        raise


def is_ip_locked(ip):
    if not ip:
        return False, 0

    row = SiteGateLock.query.filter_by(ip_address=ip).first()
    if not row or not row.locked_until:
        return False, 0

    now = now_utc()
    locked_until = _to_utc(row.locked_until)

    if locked_until and locked_until > now:
        seconds_left = int((locked_until - now).total_seconds())
        return True, max(1, seconds_left)

    row.locked_until = None
    row.failed_attempts = 0
    db.session.commit()
    return False, 0


def record_failed_attempt(ip):
    if not ip:
        return False, 0

    row = _get_or_create_lock_row(ip)
    row.failed_attempts += 1

    if row.failed_attempts >= MAX_FAILED_ATTEMPTS:
        row.failed_attempts = 0
        row.locked_until = now_utc() + timedelta(seconds=LOCKOUT_SECONDS)
        db.session.commit()
        return True, LOCKOUT_SECONDS

    db.session.commit()
    return False, 0


def reset_ip_lock_state(ip):
    if not ip:
        return

    row = SiteGateLock.query.filter_by(ip_address=ip).first()
    if not row:
        return

    row.failed_attempts = 0
    row.locked_until = None
    db.session.commit()


def clear_session_gate():
    session.pop(SESSION_OK_KEY, None)
    session.pop(SESSION_UNTIL_KEY, None)


def set_session_unlocked(ttl_minutes):
    now_ts = int(now_utc().timestamp())
    session[SESSION_OK_KEY] = True
    session[SESSION_UNTIL_KEY] = now_ts + max(1, int(ttl_minutes)) * 60


def is_session_unlocked(ignore_current_request=False):
    if ignore_current_request and request.path == "/gate/unlock":
        return False

    if not session.get(SESSION_OK_KEY):
        return False

    until_ts = int(session.get(SESSION_UNTIL_KEY, 0) or 0)
    if until_ts <= int(now_utc().timestamp()):
        clear_session_gate()
        return False

    return True


def lockout_message():
    return "Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau"


def gate_config_missing_message():
    return "Hệ thống chưa cấu hình mật khẩu truy cập. Vui lòng liên hệ quản trị viên."


def render_gate_page(gate_error=None, locked_seconds=0, status_code=200):
    return (
        render_template(
            "site_gate.html",
            gate_error=gate_error,
            locked_seconds=locked_seconds,
        ),
        status_code,
    )


def init_site_gate(app):
    @app.before_request
    def enforce_site_gate():
        if not app.config.get("SITE_GATE_ENABLED", False):
            return None

        path = request.path or "/"
        if not is_public_protected_path(path):
            return None

        # Skip site gate for authenticated admin users
        if current_user.is_authenticated:
            return None

        expected_password = app.config.get("SITE_GATE_PASSWORD", "")
        if not expected_password:
            if path == "/" and request.method == "GET":
                return render_gate_page(
                    gate_error=gate_config_missing_message(),
                    locked_seconds=0,
                    status_code=403,
                )
            abort(403)

        ip = get_site_gate_ip()
        locked, seconds_left = is_ip_locked(ip)
        if locked:
            if path == "/" and request.method == "GET":
                return render_gate_page(
                    gate_error=lockout_message(),
                    locked_seconds=seconds_left,
                    status_code=403,
                )
            abort(403)

        if is_session_unlocked(ignore_current_request=True):
            return None

        if path == "/" and request.method == "GET":
            return render_gate_page(gate_error=None, locked_seconds=0, status_code=200)

        abort(403)
