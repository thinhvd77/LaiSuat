# Site Gate Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây cổng mật khẩu cho public site để người dùng phải nhập đúng mật khẩu trước khi truy cập nội dung, có lockout 15 phút sau 5 lần nhập sai theo IP.

**Architecture:** Tạo middleware `site_gate.py` chạy ở `before_request` để chặn public routes (`/`, `/api/*`, `/pdf/*`) theo trạng thái session unlock và lockout theo IP. Route `POST /gate/unlock` xử lý nhập mật khẩu, set session TTL từ `SITE_GATE_TTL_MINUTES`, và cập nhật bộ đếm sai theo IP. Trang `site_gate.html` + `site-gate.js` hiển thị form mobile-first và countdown lockout.

**Tech Stack:** Flask, session cookie, in-memory Python dict, Jinja2 templates, vanilla JS, pytest

**Spec:** `docs/superpowers/specs/2026-03-27-site-gate-password-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `site_gate.py` (new) | Logic site gate: path matching, IP extraction, lockout, session unlock, middleware init |
| `routes_public.py` (modify) | Add `POST /gate/unlock` endpoint |
| `app.py` (modify) | Add config defaults (`SITE_GATE_TTL_MINUTES`), startup warning for missing password, init site gate middleware |
| `templates/site_gate.html` (new) | Password gate UI for `/` before unlock |
| `static/js/site-gate.js` (new) | Lockout countdown and form disable/enable behavior |
| `tests/test_site_gate.py` (new) | Unit + integration tests for gate policy and lockout behavior |

---

### Task 1: Add site_gate core utilities (path, session, lockout)

**Files:**
- Create: `site_gate.py`
- Test: `tests/test_site_gate.py`

- [ ] **Step 1: Write failing unit tests for path policy and state helpers**

Create `tests/test_site_gate.py` with initial tests:

```python
import time


def test_is_public_protected_path_matches_public_routes():
    from site_gate import is_public_protected_path

    assert is_public_protected_path("/") is True
    assert is_public_protected_path("/api/categories") is True
    assert is_public_protected_path("/pdf/1") is True


def test_is_public_protected_path_excludes_admin_static_and_gate_unlock():
    from site_gate import is_public_protected_path

    assert is_public_protected_path("/admin/login") is False
    assert is_public_protected_path("/static/css/style.css") is False
    assert is_public_protected_path("/gate/unlock") is False


def test_lockout_after_five_failed_attempts_same_ip():
    from site_gate import record_failed_attempt, is_ip_locked, clear_site_gate_state

    clear_site_gate_state()
    ip = "1.2.3.4"
    now = int(time.time())

    for _ in range(4):
        locked, _ = record_failed_attempt(ip, now)
        assert locked is False

    locked, seconds_left = record_failed_attempt(ip, now)
    assert locked is True
    assert seconds_left == 900


def test_session_unlock_and_expiry():
    from site_gate import set_session_unlocked, is_session_unlocked

    session = {}
    now = int(time.time())

    set_session_unlocked(session, now, ttl_minutes=1)
    assert is_session_unlocked(session, now) is True
    assert is_session_unlocked(session, now + 61) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'site_gate'`

- [ ] **Step 3: Implement minimal `site_gate.py` utilities**

Create `site_gate.py`:

```python
import time
from flask import request

FAILED_ATTEMPTS = {}
LOCKED_UNTIL = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60


def clear_site_gate_state():
    FAILED_ATTEMPTS.clear()
    LOCKED_UNTIL.clear()


def get_client_ip():
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return request.remote_addr


def is_public_protected_path(path):
    if path == "/":
        return True
    if path.startswith("/api/"):
        return True
    if path.startswith("/pdf/"):
        return True
    return False


def is_ip_locked(ip, now_ts=None):
    if now_ts is None:
        now_ts = int(time.time())

    locked_until = LOCKED_UNTIL.get(ip, 0)
    if locked_until > now_ts:
        return True, locked_until - now_ts

    if ip in LOCKED_UNTIL:
        LOCKED_UNTIL.pop(ip, None)
    return False, 0


def record_failed_attempt(ip, now_ts=None):
    if now_ts is None:
        now_ts = int(time.time())

    failed_count = FAILED_ATTEMPTS.get(ip, 0) + 1
    FAILED_ATTEMPTS[ip] = failed_count

    if failed_count >= MAX_FAILED_ATTEMPTS:
        FAILED_ATTEMPTS.pop(ip, None)
        LOCKED_UNTIL[ip] = now_ts + LOCKOUT_SECONDS
        return True, LOCKOUT_SECONDS

    return False, 0


def clear_ip_failures(ip):
    FAILED_ATTEMPTS.pop(ip, None)
    LOCKED_UNTIL.pop(ip, None)


def set_session_unlocked(session, now_ts, ttl_minutes):
    session["site_gate_ok"] = True
    session["site_gate_until"] = now_ts + (ttl_minutes * 60)


def is_session_unlocked(session, now_ts):
    if not session.get("site_gate_ok"):
        return False

    until = session.get("site_gate_until", 0)
    return until > now_ts
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: PASS for 4 tests.

- [ ] **Step 5: Commit**

```bash
git add site_gate.py tests/test_site_gate.py
git commit -m "feat: add site gate core state and helper functions"
```

---

### Task 2: Add middleware enforcement for public routes

**Files:**
- Modify: `site_gate.py`
- Test: `tests/test_site_gate.py`

- [ ] **Step 1: Add failing integration tests for middleware behavior**

Append to `tests/test_site_gate.py`:

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
            "SITE_GATE_PASSWORD": "abc123",
            "SITE_GATE_TTL_MINUTES": 1440,
        }
    )

    from site_gate import init_site_gate, clear_site_gate_state
    clear_site_gate_state()
    init_site_gate(app)

    return app


def test_root_shows_gate_page_when_not_unlocked(gate_app):
    client = gate_app.test_client()
    resp = client.get("/")

    assert resp.status_code == 200
    assert "Xác thực truy cập" in resp.get_data(as_text=True)


def test_public_api_returns_403_when_not_unlocked(gate_app):
    client = gate_app.test_client()
    resp = client.get("/api/categories")

    assert resp.status_code == 403


def test_admin_login_not_blocked_by_site_gate(gate_app):
    client = gate_app.test_client()
    resp = client.get("/admin/login")

    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_root_shows_gate_page_when_not_unlocked -v
```

Expected: FAIL because `init_site_gate` is not defined.

- [ ] **Step 3: Implement `init_site_gate(app)` middleware**

Add to `site_gate.py`:

```python
from flask import abort, render_template


def init_site_gate(app):
    @app.before_request
    def enforce_site_gate():
        path = request.path or "/"

        if not is_public_protected_path(path):
            return None

        now_ts = int(time.time())
        ip = get_client_ip()

        locked, seconds_left = is_ip_locked(ip, now_ts)
        if locked:
            if path == "/" and request.method == "GET":
                return render_template(
                    "site_gate.html",
                    gate_error="Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau.",
                    locked_seconds=seconds_left,
                )
            abort(403)

        if is_session_unlocked(request.session if hasattr(request, "session") else {}, now_ts):
            return None

        # Flask session should come from flask.session, not request.session
        from flask import session
        if is_session_unlocked(session, now_ts):
            return None

        if path == "/" and request.method == "GET":
            return render_template("site_gate.html", gate_error=None, locked_seconds=0)

        abort(403)
```

Then simplify to avoid `request.session` check:

```python
from flask import abort, render_template, session


def init_site_gate(app):
    @app.before_request
    def enforce_site_gate():
        path = request.path or "/"

        if not is_public_protected_path(path):
            return None

        now_ts = int(time.time())
        ip = get_client_ip()

        locked, seconds_left = is_ip_locked(ip, now_ts)
        if locked:
            if path == "/" and request.method == "GET":
                return render_template(
                    "site_gate.html",
                    gate_error="Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau.",
                    locked_seconds=seconds_left,
                )
            abort(403)

        if is_session_unlocked(session, now_ts):
            return None

        if path == "/" and request.method == "GET":
            return render_template("site_gate.html", gate_error=None, locked_seconds=0)

        abort(403)
```

- [ ] **Step 4: Run tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: middleware tests pass.

- [ ] **Step 5: Commit**

```bash
git add site_gate.py tests/test_site_gate.py
git commit -m "feat: enforce site gate on public routes"
```

---

### Task 3: Add gate unlock endpoint

**Files:**
- Modify: `routes_public.py`
- Modify: `site_gate.py`
- Test: `tests/test_site_gate.py`

- [ ] **Step 1: Add failing tests for `/gate/unlock`**

Append tests:

```python
def test_unlock_with_correct_password_sets_session(gate_app):
    client = gate_app.test_client()

    resp = client.post("/gate/unlock", data={"password": "abc123"}, follow_redirects=False)
    assert resp.status_code in (302, 303)

    api_resp = client.get("/api/categories")
    assert api_resp.status_code == 200


def test_unlock_wrong_password_keeps_blocked(gate_app):
    client = gate_app.test_client()

    resp = client.post("/gate/unlock", data={"password": "wrong"})
    assert resp.status_code == 200
    assert "Mật khẩu không đúng" in resp.get_data(as_text=True)

    api_resp = client.get("/api/categories")
    assert api_resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_unlock_with_correct_password_sets_session -v
```

Expected: FAIL with 404 on `/gate/unlock`.

- [ ] **Step 3: Implement `POST /gate/unlock` in `routes_public.py`**

Add imports:

```python
import time
from flask import session, redirect, url_for
from site_gate import (
    get_client_ip,
    is_ip_locked,
    record_failed_attempt,
    clear_ip_failures,
    set_session_unlocked,
)
```

Add route:

```python
@public_bp.route("/gate/unlock", methods=["POST"])
def gate_unlock():
    now_ts = int(time.time())
    ip = get_client_ip()

    locked, seconds_left = is_ip_locked(ip, now_ts)
    if locked:
        return render_template(
            "site_gate.html",
            gate_error="Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau.",
            locked_seconds=seconds_left,
        ), 200

    input_password = request.form.get("password", "")
    expected_password = current_app.config.get("SITE_GATE_PASSWORD", "")

    if expected_password and input_password == expected_password:
        clear_ip_failures(ip)
        ttl_minutes = int(current_app.config.get("SITE_GATE_TTL_MINUTES", 1440))
        set_session_unlocked(session, now_ts, ttl_minutes)
        session.permanent = True
        return redirect(url_for("public.index"))

    locked, seconds_left = record_failed_attempt(ip, now_ts)
    if locked:
        return render_template(
            "site_gate.html",
            gate_error="Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau.",
            locked_seconds=seconds_left,
        ), 200

    return render_template(
        "site_gate.html",
        gate_error="Mật khẩu không đúng",
        locked_seconds=0,
    ), 200
```

- [ ] **Step 4: Run tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: unlock tests pass.

- [ ] **Step 5: Commit**

```bash
git add routes_public.py site_gate.py tests/test_site_gate.py
git commit -m "feat: add site gate unlock endpoint"
```

---

### Task 4: Add lockout behavior tests and implementation hardening

**Files:**
- Modify: `tests/test_site_gate.py`
- Modify: `site_gate.py`

- [ ] **Step 1: Add failing tests for 5-attempt lockout and countdown**

Append:

```python
def test_lockout_after_five_wrong_attempts(gate_app):
    client = gate_app.test_client()

    for _ in range(5):
        client.post("/gate/unlock", data={"password": "wrong"})

    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Vui lòng thử lại sau" in html

    api_resp = client.get("/api/categories")
    assert api_resp.status_code == 403


def test_locked_ip_cannot_unlock_even_with_correct_password(gate_app):
    client = gate_app.test_client()

    for _ in range(5):
        client.post("/gate/unlock", data={"password": "wrong"})

    resp = client.post("/gate/unlock", data={"password": "abc123"})
    assert resp.status_code == 200
    assert "Vui lòng thử lại sau" in resp.get_data(as_text=True)
```

- [ ] **Step 2: Run tests to verify fail (if needed)**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_lockout_after_five_wrong_attempts -v
```

Expected: If failing, adjust lockout rendering context.

- [ ] **Step 3: Harden helper functions and middleware response context**

Ensure consistent template context helper in `site_gate.py`:

```python
def lockout_message():
    return "Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau"
```

Use same message for both middleware and unlock route, and always pass `locked_seconds`.

Also add session cleanup helper:

```python
def clear_gate_session(session):
    session.pop("site_gate_ok", None)
    session.pop("site_gate_until", None)
```

Then update `is_session_unlocked` usage in middleware to clear expired session keys.

- [ ] **Step 4: Run all site gate tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
```

Expected: all site gate tests pass.

- [ ] **Step 5: Commit**

```bash
git add site_gate.py tests/test_site_gate.py
git commit -m "feat: add per-IP lockout behavior for site gate"
```

---

### Task 5: Create gate template and countdown script (mobile-first)

**Files:**
- Create: `templates/site_gate.html`
- Create: `static/js/site-gate.js`
- Modify: `static/css/style.css`

- [ ] **Step 1: Add failing integration test for gate page UI**

Append in `tests/test_site_gate.py`:

```python
def test_root_gate_page_contains_password_form(gate_app):
    client = gate_app.test_client()
    resp = client.get("/")

    html = resp.get_data(as_text=True)
    assert "<form" in html
    assert "name=\"password\"" in html
    assert "Xác thực truy cập" in html
```

- [ ] **Step 2: Run test to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_root_gate_page_contains_password_form -v
```

Expected: FAIL because template does not exist yet.

- [ ] **Step 3: Implement `templates/site_gate.html`**

Create template:

```html
{% extends "base.html" %}
{% block title %}Xác thực truy cập{% endblock %}

{% block content %}
<div class="login-container site-gate-container">
    <div class="login-brand">
        <img src="{{ url_for('static', filename='images/logo_2.png') }}" alt="Logo" class="login-brand-logo">
        <h2 class="login-brand-text">Agribank Chi nhánh Bắc TPHCM</h2>
        <p class="login-brand-sub">Bảo mật truy cập tài liệu lãi suất</p>
    </div>

    <div class="login-form-side">
        <div class="login-card site-gate-card">
            <img src="{{ url_for('static', filename='images/logo_2.png') }}" alt="Logo" class="login-card-logo-mobile">
            <h1>Xác thực truy cập</h1>
            <p class="login-subtitle">Vui lòng nhập mật khẩu để tiếp tục</p>

            {% if gate_error %}
            <div class="flash flash-error site-gate-inline-error" id="gate-error" data-locked-seconds="{{ locked_seconds|default(0) }}">
                {% if locked_seconds and locked_seconds > 0 %}
                    {{ gate_error }} <strong id="site-gate-countdown"></strong>
                {% else %}
                    {{ gate_error }}
                {% endif %}
            </div>
            {% endif %}

            <form method="post" action="{{ url_for('public.gate_unlock') }}" id="site-gate-form">
                <div class="form-group">
                    <label for="password">Mật khẩu <span class="required">*</span></label>
                    <input
                        type="password"
                        id="password"
                        name="password"
                        placeholder="Nhập mật khẩu truy cập"
                        required
                        autocomplete="current-password"
                    >
                </div>

                <button type="submit" class="btn btn-primary btn-full" id="site-gate-submit">
                    Truy cập
                </button>
            </form>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='js/site-gate.js') }}"></script>
{% endblock %}
```

- [ ] **Step 4: Implement countdown script and minor CSS additions**

Create `static/js/site-gate.js`:

```javascript
(function () {
    const errorBox = document.getElementById("gate-error");
    const form = document.getElementById("site-gate-form");
    const submitBtn = document.getElementById("site-gate-submit");
    const passwordInput = document.getElementById("password");
    const countdownEl = document.getElementById("site-gate-countdown");

    if (!errorBox) return;

    let lockedSeconds = parseInt(errorBox.dataset.lockedSeconds || "0", 10);
    if (!lockedSeconds || lockedSeconds <= 0) return;

    function formatMMSS(totalSeconds) {
        const m = Math.floor(totalSeconds / 60);
        const s = totalSeconds % 60;
        return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }

    function setLockedState(locked) {
        if (passwordInput) passwordInput.disabled = locked;
        if (submitBtn) submitBtn.disabled = locked;
    }

    setLockedState(true);

    const tick = () => {
        if (lockedSeconds <= 0) {
            if (countdownEl) countdownEl.textContent = "";
            setLockedState(false);
            return;
        }

        if (countdownEl) countdownEl.textContent = formatMMSS(lockedSeconds);
        lockedSeconds -= 1;
        setTimeout(tick, 1000);
    };

    tick();
})();
```

Append to `static/css/style.css`:

```css
.site-gate-container .login-form-side {
    min-height: 100vh;
}

.site-gate-inline-error {
    position: static;
    width: 100%;
    margin-bottom: 16px;
    box-shadow: none;
}

#site-gate-submit:disabled,
#password:disabled {
    opacity: 0.65;
    cursor: not-allowed;
}
```

- [ ] **Step 5: Run gate UI tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_root_gate_page_contains_password_form -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/site_gate.html static/js/site-gate.js static/css/style.css tests/test_site_gate.py
git commit -m "feat: add mobile-first site gate password page"
```

---

### Task 6: Integrate site gate into app factory config

**Files:**
- Modify: `app.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_site_gate.py`

- [ ] **Step 1: Add failing test for app config defaults**

Append to `tests/test_site_gate.py`:

```python
def test_site_gate_ttl_default_exists(app):
    assert app.config.get("SITE_GATE_TTL_MINUTES") is not None
```

- [ ] **Step 2: Run test to verify fail**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py::test_site_gate_ttl_default_exists -v
```

Expected: FAIL (default missing).

- [ ] **Step 3: Update `app.py` config and middleware initialization**

In `create_app()` default config block add:

```python
app.config["SITE_GATE_TTL_MINUTES"] = int(os.environ.get("SITE_GATE_TTL_MINUTES", "1440"))
app.config["SITE_GATE_PASSWORD"] = os.environ.get("SITE_GATE_PASSWORD", "")
```

After existing middleware init blocks, initialize site gate:

```python
from site_gate import init_site_gate
init_site_gate(app)
```

Add startup warning once:

```python
if not app.config.get("SITE_GATE_PASSWORD"):
    app.logger.warning("SITE_GATE_PASSWORD is not configured; public gate will fail closed")
```

For tests, ensure fixture app config includes gate password in `tests/conftest.py` app fixture config:

```python
"SITE_GATE_PASSWORD": "test-gate-password",
"SITE_GATE_TTL_MINUTES": 1440,
```

- [ ] **Step 4: Run tests**

Run:
```bash
./venv/bin/pytest tests/test_site_gate.py -v
./venv/bin/pytest tests/ -v
```

Expected: site gate tests pass, full regression pass.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/conftest.py tests/test_site_gate.py
git commit -m "feat: wire site gate configuration into app factory"
```

---

### Task 7: Final verification and cleanup

**Files:**
- None (verification)

- [ ] **Step 1: Run full test suite**

Run:
```bash
./venv/bin/pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Manual local verification**

Run:
```bash
SITE_GATE_PASSWORD=abc123 SITE_GATE_TTL_MINUTES=1440 python app.py
```

In another terminal:
```bash
# 1) Should show gate page
curl -i http://localhost:5000/

# 2) API should be blocked before unlock
curl -i http://localhost:5000/api/categories

# 3) Unlock with correct password
curl -i -X POST http://localhost:5000/gate/unlock -d "password=abc123"
```

Expected:
- `/` returns gate page before unlock
- `/api/categories` returns 403 before unlock
- `POST /gate/unlock` redirects to `/` after correct password

- [ ] **Step 3: Verify commit sequence**

Run:
```bash
git log --oneline -10
```

Expected: commits for tasks 1-6 present and ordered.

- [ ] **Step 4: Optional docs update note**

If team wants deployment notes in repo docs, add a small section to existing ops docs (only if explicitly requested by reviewer/user). For this plan, skip extra docs by default (YAGNI).

---

## Execution notes

- Keep lockout state process-local (as spec)
- Do not add Redis in this scope
- Do not gate `/admin/*`
- Keep `/api/*` and `/pdf/*` as strict 403 when not unlocked
- Use exact Vietnamese texts from spec for user-facing messages
