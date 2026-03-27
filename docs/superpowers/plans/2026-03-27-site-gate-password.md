# Site Gate Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm cổng mật khẩu cho public site, chặn brute-force theo IP với lockout 15 phút sau 5 lần sai, và chỉ cho truy cập public nội dung sau khi unlock thành công.

**Architecture:** Site gate được bật/tắt bằng `SITE_GATE_ENABLED`. Middleware `before_request` bảo vệ `/`, `/api/*`, `/pdf/*` (không ảnh hưởng `/admin/*`). Trạng thái lockout lưu trong DB qua SQLAlchemy (không dùng in-memory) để an toàn với Gunicorn nhiều worker; unlock state lưu trong session với TTL từ `SITE_GATE_TTL_MINUTES`.

**Tech Stack:** Flask, Flask-WTF CSRF, SQLAlchemy (SQLite hiện tại), session cookie, Jinja2, vanilla JS, pytest

**Spec:** `docs/superpowers/specs/2026-03-27-site-gate-password-design.md` (plan này đã cập nhật theo review trước khi implement)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `models.py` (modify) | Thêm model DB lưu lockout theo IP (`SiteGateLock`) |
| `site_gate.py` (new) | Policy public-path, DB lockout helpers, session helpers, middleware init |
| `routes_public.py` (modify) | Thêm `POST /gate/unlock` dùng CSRF + compare_digest |
| `templates/site_gate.html` (new) | Trang form nhập mật khẩu, có CSRF hidden field |
| `static/js/site-gate.js` (new) | Countdown lockout trên client |
| `static/css/style.css` (modify) | Style nhỏ cho gate page/error inline |
| `app.py` (modify) | Config defaults + bật middleware khi `SITE_GATE_ENABLED=true` |
| `tests/test_site_gate.py` (new) | Unit + integration tests cho site gate |

---

### Task 1: Add DB model for IP lockout state

**Files:**
- Modify: `models.py`
- Create: `tests/test_site_gate.py`

- [ ] **Step 1: Write failing test for lockout model persistence**

Create `tests/test_site_gate.py` initial test:

```python
from datetime import datetime, timezone


def test_site_gate_lock_model_persists(app):
    from models import SiteGateLock
    from extensions import db

    with app.app_context():
        row = SiteGateLock(
            ip_address="1.2.3.4",
            failed_attempts=3,
            locked_until=datetime.now(timezone.utc),
        )
        db.session.add(row)
        db.session.commit()

        fetched = SiteGateLock.query.filter_by(ip_address="1.2.3.4").first()
        assert fetched is not None
        assert fetched.failed_attempts == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_site_gate_lock_model_persists -v
```

Expected: FAIL (`ImportError: cannot import name 'SiteGateLock'`).

- [ ] **Step 3: Add `SiteGateLock` model in `models.py`**

Add model:

```python
class SiteGateLock(db.Model):
    __tablename__ = "site_gate_locks"

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.Text, unique=True, nullable=False, index=True)
    failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_site_gate_lock_model_persists -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_site_gate.py
git commit -m "feat: add SiteGateLock model for IP lockout state"
```

---

### Task 2: Implement `site_gate.py` helpers (reuse existing get_client_ip)

**Files:**
- Create: `site_gate.py`
- Modify: `tests/test_site_gate.py`

- [ ] **Step 1: Write failing unit tests for helper behavior**

Append tests:

```python
from datetime import datetime, timedelta, timezone


def test_is_public_protected_path_matches_scope():
    from site_gate import is_public_protected_path

    assert is_public_protected_path("/") is True
    assert is_public_protected_path("/api/categories") is True
    assert is_public_protected_path("/pdf/1") is True
    assert is_public_protected_path("/admin/login") is False
    assert is_public_protected_path("/gate/unlock") is False


def test_record_failed_attempt_and_lockout(app):
    from site_gate import record_failed_attempt, is_ip_locked, reset_ip_lock_state

    with app.app_context():
        ip = "1.2.3.4"
        reset_ip_lock_state(ip)
        for _ in range(4):
            locked, _ = record_failed_attempt(ip)
            assert locked is False

        locked, seconds_left = record_failed_attempt(ip)
        assert locked is True
        assert 1 <= seconds_left <= 900

        locked_now, _ = is_ip_locked(ip)
        assert locked_now is True
```

- [ ] **Step 2: Run tests to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: FAIL (`ModuleNotFoundError: No module named 'site_gate'`).

- [ ] **Step 3: Implement `site_gate.py` helpers**

Create `site_gate.py` with:

```python
from datetime import datetime, timedelta, timezone
from flask import session
from extensions import db
from middleware import get_client_ip
from models import SiteGateLock

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60


def now_utc():
    return datetime.now(timezone.utc)


def is_public_protected_path(path):
    return path == "/" or path.startswith("/api/") or path.startswith("/pdf/")


def get_or_create_lock(ip):
    row = SiteGateLock.query.filter_by(ip_address=ip).first()
    if row:
        return row
    row = SiteGateLock(ip_address=ip, failed_attempts=0, locked_until=None)
    db.session.add(row)
    db.session.flush()
    return row


def is_ip_locked(ip):
    row = SiteGateLock.query.filter_by(ip_address=ip).first()
    if not row or not row.locked_until:
        return False, 0

    now = now_utc()
    if row.locked_until > now:
        seconds_left = int((row.locked_until - now).total_seconds())
        return True, max(1, seconds_left)

    row.locked_until = None
    row.failed_attempts = 0
    db.session.commit()
    return False, 0


def record_failed_attempt(ip):
    row = get_or_create_lock(ip)
    row.failed_attempts += 1

    if row.failed_attempts >= MAX_FAILED_ATTEMPTS:
        row.failed_attempts = 0
        row.locked_until = now_utc() + timedelta(seconds=LOCKOUT_SECONDS)
        db.session.commit()
        return True, LOCKOUT_SECONDS

    db.session.commit()
    return False, 0


def reset_ip_lock_state(ip):
    row = SiteGateLock.query.filter_by(ip_address=ip).first()
    if not row:
        return
    row.failed_attempts = 0
    row.locked_until = None
    db.session.commit()


def set_session_unlocked(ttl_minutes):
    now_ts = int(now_utc().timestamp())
    session["site_gate_ok"] = True
    session["site_gate_until"] = now_ts + ttl_minutes * 60


def clear_session_gate():
    session.pop("site_gate_ok", None)
    session.pop("site_gate_until", None)


def is_session_unlocked():
    if not session.get("site_gate_ok"):
        return False

    now_ts = int(now_utc().timestamp())
    until = int(session.get("site_gate_until", 0))
    if until <= now_ts:
        clear_session_gate()
        return False

    return True
```

- [ ] **Step 4: Run helper tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: helper tests PASS.

- [ ] **Step 5: Commit**

```bash
git add site_gate.py tests/test_site_gate.py
git commit -m "feat: add DB-backed site gate helper functions"
```

---

### Task 3: Add middleware enforcement with 403 on locked `/`

**Files:**
- Modify: `site_gate.py`
- Modify: `tests/test_site_gate.py`

- [ ] **Step 1: Add failing integration tests for middleware policy**

Append tests:

```python
import pytest
from app import create_app


@pytest.fixture
def gate_app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret-key",
            "SITE_GATE_ENABLED": True,
            "SITE_GATE_PASSWORD": "abc123",
            "SITE_GATE_TTL_MINUTES": 1440,
        }
    )
    return app


def test_root_returns_gate_page_when_not_unlocked(gate_app):
    client = gate_app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Xác thực truy cập" in resp.get_data(as_text=True)


def test_api_returns_403_when_not_unlocked(gate_app):
    client = gate_app.test_client()
    resp = client.get("/api/categories")
    assert resp.status_code == 403


def test_locked_root_returns_403_with_gate_message(gate_app):
    client = gate_app.test_client()
    for _ in range(5):
        client.post("/gate/unlock", data={"password": "wrong"})

    resp = client.get("/")
    assert resp.status_code == 403
    assert "Vui lòng thử lại sau" in resp.get_data(as_text=True)
```

- [ ] **Step 2: Run tests to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_api_returns_403_when_not_unlocked -v
```

Expected: FAIL until middleware init exists.

- [ ] **Step 3: Implement `init_site_gate(app)` and policy**

Add to `site_gate.py`:

```python
import logging
from flask import abort, render_template, request

logger = logging.getLogger(__name__)


def lockout_message():
    return "Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau"


def init_site_gate(app):
    @app.before_request
    def enforce_site_gate():
        if not app.config.get("SITE_GATE_ENABLED", False):
            return None

        path = request.path or "/"
        if not is_public_protected_path(path):
            return None

        ip = get_client_ip()
        locked, seconds_left = is_ip_locked(ip)

        if locked:
            if path == "/" and request.method == "GET":
                return render_template(
                    "site_gate.html",
                    gate_error=lockout_message(),
                    locked_seconds=seconds_left,
                ), 403
            abort(403)

        if is_session_unlocked():
            return None

        if path == "/" and request.method == "GET":
            return render_template(
                "site_gate.html",
                gate_error=None,
                locked_seconds=0,
            ), 200

        abort(403)
```

- [ ] **Step 4: Run middleware tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: middleware tests PASS.

- [ ] **Step 5: Commit**

```bash
git add site_gate.py tests/test_site_gate.py
git commit -m "feat: enforce site gate middleware on public routes"
```

---

### Task 4: Add `/gate/unlock` route with CSRF + compare_digest

**Files:**
- Modify: `routes_public.py`
- Modify: `templates/site_gate.html`
- Modify: `tests/test_site_gate.py`

- [ ] **Step 1: Add failing tests for unlock endpoint**

Append tests:

```python
def test_unlock_correct_password_allows_api(gate_app):
    client = gate_app.test_client()

    with gate_app.test_request_context():
        from flask_wtf.csrf import generate_csrf
        token = generate_csrf()

    resp = client.post(
        "/gate/unlock",
        data={"password": "abc123", "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)


def test_unlock_wrong_password_shows_error(gate_app):
    client = gate_app.test_client()

    resp = client.post(
        "/gate/unlock",
        data={"password": "wrong"},
    )
    # in gate_app fixture CSRF disabled, so this reaches handler
    assert resp.status_code == 200
    assert "Mật khẩu không đúng" in resp.get_data(as_text=True)
```

- [ ] **Step 2: Run test to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_unlock_correct_password_allows_api -v
```

Expected: FAIL with 404 on `/gate/unlock`.

- [ ] **Step 3: Implement route in `routes_public.py`**

Update imports:

```python
import hmac
from flask import session, redirect, url_for, request
from site_gate import (
    get_client_ip,
    is_ip_locked,
    record_failed_attempt,
    reset_ip_lock_state,
    set_session_unlocked,
    lockout_message,
)
```

Add route:

```python
@public_bp.route("/gate/unlock", methods=["POST"])
def gate_unlock():
    if not current_app.config.get("SITE_GATE_ENABLED", False):
        return redirect(url_for("public.index"))

    ip = get_client_ip()
    locked, seconds_left = is_ip_locked(ip)
    if locked:
        return render_template(
            "site_gate.html",
            gate_error=lockout_message(),
            locked_seconds=seconds_left,
        ), 403

    input_password = request.form.get("password", "")
    expected_password = current_app.config.get("SITE_GATE_PASSWORD", "")

    if expected_password and hmac.compare_digest(input_password, expected_password):
        reset_ip_lock_state(ip)
        ttl = int(current_app.config.get("SITE_GATE_TTL_MINUTES", 1440))
        set_session_unlocked(ttl)
        session.permanent = True
        return redirect(url_for("public.index"))

    locked, seconds_left = record_failed_attempt(ip)
    if locked:
        return render_template(
            "site_gate.html",
            gate_error=lockout_message(),
            locked_seconds=seconds_left,
        ), 403

    return render_template(
        "site_gate.html",
        gate_error="Mật khẩu không đúng",
        locked_seconds=0,
    ), 200
```

- [ ] **Step 4: Add CSRF hidden input in template form**

In `templates/site_gate.html` form add:

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

- [ ] **Step 5: Run tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: unlock tests PASS.

- [ ] **Step 6: Commit**

```bash
git add routes_public.py templates/site_gate.html tests/test_site_gate.py
git commit -m "feat: add secure site gate unlock endpoint with CSRF"
```

---

### Task 5: Build gate UI and countdown

**Files:**
- Create: `templates/site_gate.html` (if not already created)
- Create: `static/js/site-gate.js`
- Modify: `static/css/style.css`
- Modify: `tests/test_site_gate.py`

- [ ] **Step 1: Add failing test for gate form and countdown hooks**

Append:

```python
def test_gate_page_contains_password_form_and_countdown_hook(gate_app):
    client = gate_app.test_client()
    resp = client.get("/")

    html = resp.get_data(as_text=True)
    assert "name=\"password\"" in html
    assert "name=\"csrf_token\"" in html
    assert "site-gate-countdown" in html or "locked_seconds" in html
```

- [ ] **Step 2: Run test to verify fail (if UI not complete yet)**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_gate_page_contains_password_form_and_countdown_hook -v
```

- [ ] **Step 3: Implement/complete `templates/site_gate.html`**

Use login-like layout, include:
- title `Xác thực truy cập`
- inline error area
- `data-locked-seconds` attribute
- password form + CSRF hidden input
- submit button `Truy cập`

- [ ] **Step 4: Implement countdown script**

Create `static/js/site-gate.js`:
- read `data-locked-seconds`
- disable input/button while `>0`
- render MM:SS to `#site-gate-countdown`
- re-enable form at 0

- [ ] **Step 5: Add minimal CSS adjustments**

Append styles in `static/css/style.css` for `.site-gate-inline-error` and disabled states.

- [ ] **Step 6: Run UI test + site gate tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add templates/site_gate.html static/js/site-gate.js static/css/style.css tests/test_site_gate.py
git commit -m "feat: add mobile-first site gate UI with lockout countdown"
```

---

### Task 6: Wire app config and enable flag (without breaking existing tests)

**Files:**
- Modify: `app.py`
- Modify: `tests/test_site_gate.py`

- [ ] **Step 1: Add failing config tests**

Append tests:

```python
def test_site_gate_enabled_default_is_false(app):
    assert app.config["SITE_GATE_ENABLED"] is False


def test_site_gate_ttl_default_is_1440(app):
    assert app.config["SITE_GATE_TTL_MINUTES"] == 1440
```

- [ ] **Step 2: Run tests to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_site_gate_enabled_default_is_false -v
```

Expected: FAIL if config keys not present.

- [ ] **Step 3: Update `app.py` config + middleware init**

In config defaults add:

```python
app.config["SITE_GATE_ENABLED"] = os.environ.get("SITE_GATE_ENABLED", "false").lower() == "true"
app.config["SITE_GATE_PASSWORD"] = os.environ.get("SITE_GATE_PASSWORD", "")
app.config["SITE_GATE_TTL_MINUTES"] = int(os.environ.get("SITE_GATE_TTL_MINUTES", "1440"))
```

After blueprints/middleware registration, add:

```python
from site_gate import init_site_gate
init_site_gate(app)

if app.config["SITE_GATE_ENABLED"] and not app.config.get("SITE_GATE_PASSWORD"):
    app.logger.warning("SITE_GATE_ENABLED=true but SITE_GATE_PASSWORD is empty; site gate will deny unlock")
```

Do **not** modify `tests/conftest.py` to globally enable gate.
Only `tests/test_site_gate.py` should set `SITE_GATE_ENABLED=True` in its own fixture.

- [ ] **Step 4: Run full test suite**

Run:
```bash
./venv/bin/pytest tests/ -v
```

Expected: existing tests still pass; new site-gate tests pass.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_site_gate.py
git commit -m "feat: add SITE_GATE_ENABLED config and app integration"
```

---

### Task 7: Final verification and deployment notes

**Files:**
- None (verification only)

- [ ] **Step 1: Run full tests one more time**

Run:
```bash
./venv/bin/pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Manual verification locally**

Run app:
```bash
SITE_GATE_ENABLED=true SITE_GATE_PASSWORD=abc123 SITE_GATE_TTL_MINUTES=1440 python app.py
```

In another terminal:
```bash
# Root should show gate form
curl -i http://localhost:5000/

# API should be forbidden before unlock
curl -i http://localhost:5000/api/categories

# Submit wrong password 5 times then root should be 403 with gate+lock message
for i in 1 2 3 4 5; do curl -i -X POST http://localhost:5000/gate/unlock -d "password=wrong"; done
curl -i http://localhost:5000/
```

Expected:
- Before unlock: `/` -> 200 gate form; `/api/*` -> 403
- After 5 wrong attempts: `/` -> 403 (locked state), `/api/*` -> 403

- [ ] **Step 3: DB table creation step for production**

Run on server:
```bash
flask --app app init-db
```

Expected: new table `site_gate_locks` is created.

- [ ] **Step 4: Verify commit history**

Run:
```bash
git log --oneline -12
```

Expected: task commits present in sequence.

---

## Execution notes

- Use DB-backed lockout (no in-memory state)
- Reuse `middleware.get_client_ip()` (no duplicate IP extraction logic)
- Use `hmac.compare_digest` for password check
- Include CSRF hidden field in gate form
- Keep `/admin/*` unaffected
- Keep gate off by default (`SITE_GATE_ENABLED=false`) to avoid breaking existing behavior/tests
