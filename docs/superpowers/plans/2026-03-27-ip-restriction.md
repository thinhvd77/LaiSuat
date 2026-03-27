# IP Restriction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Giới hạn truy cập website chỉ từ các IP public của công ty, sử dụng defense-in-depth với cả Nginx và Flask.

**Architecture:** File `ip_whitelist.txt` làm nguồn dữ liệu chính. Flask middleware check IP trước mỗi request (fallback). Script Python generate Nginx config từ whitelist. Nginx chặn và drop connection cho IP không hợp lệ.

**Tech Stack:** Flask, Nginx, Cloudflare (CF-Connecting-IP header)

**Spec:** `docs/superpowers/specs/2026-03-27-ip-restriction-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `ip_whitelist.txt` | Danh sách IP được phép (nguồn dữ liệu chính) |
| `ip_whitelist.example.txt` | Template mẫu để commit vào git |
| `middleware.py` | Flask middleware: `load_ip_whitelist()`, `get_client_ip()`, `init_ip_restriction()` |
| `scripts/generate_nginx_ip.py` | Script generate `nginx/ip_whitelist.conf` từ whitelist |
| `nginx/ip_whitelist.conf` | Generated Nginx allow/deny rules |
| `templates/errors/403.html` | Trang lỗi 403 (Flask fallback) |
| `tests/test_ip_restriction.py` | Unit tests cho middleware |
| `app.py` | Sửa: thêm error handler 403, init middleware |
| `.gitignore` | Sửa: thêm `ip_whitelist.txt` |

---

## Task 1: Create IP Whitelist Files

**Files:**
- Create: `ip_whitelist.example.txt`
- Create: `ip_whitelist.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Create example whitelist file**

```bash
cat > ip_whitelist.example.txt << 'EOF'
# Danh sách IP được phép truy cập
# Mỗi dòng một IP, dòng trống và comment (#) được bỏ qua
# Copy file này thành ip_whitelist.txt và thêm IP thực của công ty

# Văn phòng chính
# 113.161.x.x

# Chi nhánh Hà Nội
# 118.70.x.x

# Chi nhánh Đà Nẵng
# 171.244.x.x
EOF
```

- [ ] **Step 2: Create actual whitelist with localhost for dev**

```bash
cat > ip_whitelist.txt << 'EOF'
# IP whitelist - DO NOT COMMIT
# Development
127.0.0.1
EOF
```

- [ ] **Step 3: Add ip_whitelist.txt to .gitignore**

Append to `.gitignore`:
```
ip_whitelist.txt
```

- [ ] **Step 4: Commit**

```bash
git add ip_whitelist.example.txt .gitignore
git commit -m "feat: add IP whitelist example file

- ip_whitelist.example.txt: template for allowed IPs
- ip_whitelist.txt added to .gitignore (contains real IPs)"
```

---

## Task 2: Create Middleware - load_ip_whitelist function

**Files:**
- Create: `middleware.py`
- Create: `tests/test_ip_restriction.py`

- [ ] **Step 1: Write failing test for load_ip_whitelist**

Create `tests/test_ip_restriction.py`:

```python
"""Tests cho IP restriction middleware."""
import pytest


class TestLoadIPWhitelist:
    """Test đọc file whitelist."""

    def test_load_valid_file(self, tmp_path):
        """Đọc file với IP hợp lệ."""
        from middleware import load_ip_whitelist

        whitelist = tmp_path / "whitelist.txt"
        whitelist.write_text("113.161.1.1\n118.70.2.2\n")

        ips = load_ip_whitelist(str(whitelist))

        assert ips == {"113.161.1.1", "118.70.2.2"}

    def test_ignore_comments_and_blank_lines(self, tmp_path):
        """Bỏ qua comment và dòng trống."""
        from middleware import load_ip_whitelist

        whitelist = tmp_path / "whitelist.txt"
        whitelist.write_text("# Comment\n113.161.1.1\n\n# Another\n118.70.2.2\n")

        ips = load_ip_whitelist(str(whitelist))

        assert ips == {"113.161.1.1", "118.70.2.2"}

    def test_missing_file_returns_empty(self, tmp_path):
        """File không tồn tại trả về set rỗng."""
        from middleware import load_ip_whitelist

        ips = load_ip_whitelist(str(tmp_path / "nonexistent.txt"))

        assert ips == set()

    def test_strips_whitespace(self, tmp_path):
        """Strip whitespace từ IP."""
        from middleware import load_ip_whitelist

        whitelist = tmp_path / "whitelist.txt"
        whitelist.write_text("  113.161.1.1  \n\t118.70.2.2\t\n")

        ips = load_ip_whitelist(str(whitelist))

        assert ips == {"113.161.1.1", "118.70.2.2"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./venv/bin/pytest tests/test_ip_restriction.py::TestLoadIPWhitelist -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'middleware'`

- [ ] **Step 3: Write minimal implementation**

Create `middleware.py`:

```python
"""IP restriction middleware for Flask."""
import os
import logging

logger = logging.getLogger(__name__)


def load_ip_whitelist(filepath="ip_whitelist.txt"):
    """Đọc danh sách IP từ file, bỏ qua comment và dòng trống."""
    ips = set()
    if not os.path.exists(filepath):
        logger.warning("IP whitelist file not found: %s", filepath)
        return ips

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ips.add(line)
    return ips
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./venv/bin/pytest tests/test_ip_restriction.py::TestLoadIPWhitelist -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add middleware.py tests/test_ip_restriction.py
git commit -m "feat: add load_ip_whitelist function

Reads IP addresses from file, ignoring comments and blank lines.
Returns empty set if file doesn't exist."
```

---

## Task 3: Create Middleware - get_client_ip function

**Files:**
- Modify: `middleware.py`
- Modify: `tests/test_ip_restriction.py`

- [ ] **Step 1: Write failing tests for get_client_ip**

Append to `tests/test_ip_restriction.py`:

```python
class TestGetClientIP:
    """Test hàm get_client_ip()."""

    def test_cf_connecting_ip_priority(self, app):
        """CF-Connecting-IP được ưu tiên."""
        from middleware import get_client_ip

        with app.test_request_context(
            headers={
                "CF-Connecting-IP": "1.1.1.1",
                "X-Real-IP": "2.2.2.2",
            }
        ):
            assert get_client_ip() == "1.1.1.1"

    def test_x_real_ip_fallback(self, app):
        """X-Real-IP khi không có CF header."""
        from middleware import get_client_ip

        with app.test_request_context(headers={"X-Real-IP": "2.2.2.2"}):
            assert get_client_ip() == "2.2.2.2"

    def test_remote_addr_last_resort(self, app):
        """remote_addr khi không có header nào."""
        from middleware import get_client_ip

        with app.test_request_context(environ_base={"REMOTE_ADDR": "3.3.3.3"}):
            assert get_client_ip() == "3.3.3.3"

    def test_strips_whitespace_from_headers(self, app):
        """Strip whitespace từ header values."""
        from middleware import get_client_ip

        with app.test_request_context(headers={"CF-Connecting-IP": "  1.1.1.1  "}):
            assert get_client_ip() == "1.1.1.1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./venv/bin/pytest tests/test_ip_restriction.py::TestGetClientIP -v
```

Expected: FAIL with `ImportError: cannot import name 'get_client_ip'`

- [ ] **Step 3: Write minimal implementation**

Add to `middleware.py`:

```python
from flask import request


def get_client_ip():
    """Lấy IP thực của client từ Cloudflare/Nginx."""
    # Ưu tiên CF-Connecting-IP (Cloudflare gửi trực tiếp)
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    # Fallback: X-Real-IP từ Nginx
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Cuối cùng: remote_addr
    return request.remote_addr
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./venv/bin/pytest tests/test_ip_restriction.py::TestGetClientIP -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add middleware.py tests/test_ip_restriction.py
git commit -m "feat: add get_client_ip function

Extracts real client IP from headers with priority:
CF-Connecting-IP > X-Real-IP > remote_addr"
```

---

## Task 4: Create Middleware - init_ip_restriction function

**Files:**
- Modify: `middleware.py`
- Modify: `tests/test_ip_restriction.py`

- [ ] **Step 1: Write failing tests for init_ip_restriction**

Append to `tests/test_ip_restriction.py`:

```python
from app import create_app
from extensions import db as _db
import tempfile
import os


class TestIPRestrictionMiddleware:
    """Test middleware chặn IP."""

    @pytest.fixture
    def app_with_ip_restriction(self, tmp_path):
        """App với IP restriction enabled."""
        # Tạo whitelist với IP được phép
        whitelist = tmp_path / "ip_whitelist.txt"
        whitelist.write_text("1.1.1.1\n2.2.2.2\n")

        db_fd, db_path = tempfile.mkstemp()
        upload_dir = tempfile.mkdtemp()

        app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
                "UPLOAD_FOLDER": upload_dir,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret-key",
                "IP_WHITELIST_PATH": str(whitelist),
            }
        )

        # Manually init IP restriction (since test_config disables it)
        from middleware import init_ip_restriction
        init_ip_restriction(app, str(whitelist))

        with app.app_context():
            _db.create_all()

        yield app

        os.close(db_fd)
        os.unlink(db_path)

    def test_allowed_ip_can_access(self, app_with_ip_restriction):
        """IP trong whitelist truy cập được."""
        client = app_with_ip_restriction.test_client()

        response = client.get(
            "/",
            headers={"CF-Connecting-IP": "1.1.1.1"}
        )

        assert response.status_code == 200

    def test_blocked_ip_gets_403(self, app_with_ip_restriction):
        """IP không trong whitelist bị chặn."""
        client = app_with_ip_restriction.test_client()

        response = client.get(
            "/",
            headers={"CF-Connecting-IP": "9.9.9.9"}
        )

        assert response.status_code == 403

    def test_blocked_ip_on_admin_route(self, app_with_ip_restriction):
        """Admin route cũng bị chặn."""
        client = app_with_ip_restriction.test_client()

        response = client.get(
            "/admin/login",
            headers={"CF-Connecting-IP": "9.9.9.9"}
        )

        assert response.status_code == 403

    def test_allowed_ip_on_api_route(self, app_with_ip_restriction):
        """API route cho phép IP hợp lệ."""
        client = app_with_ip_restriction.test_client()

        response = client.get(
            "/api/categories",
            headers={"CF-Connecting-IP": "2.2.2.2"}
        )

        assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
./venv/bin/pytest tests/test_ip_restriction.py::TestIPRestrictionMiddleware -v
```

Expected: FAIL with `ImportError: cannot import name 'init_ip_restriction'`

- [ ] **Step 3: Write minimal implementation**

Add to `middleware.py`:

```python
from flask import abort


def init_ip_restriction(app, whitelist_path=None):
    """Khởi tạo middleware check IP cho Flask app."""
    if whitelist_path is None:
        whitelist_path = os.path.join(app.root_path, "ip_whitelist.txt")

    allowed_ips = load_ip_whitelist(whitelist_path)

    logger.info("Loaded %d IPs from whitelist", len(allowed_ips))

    @app.before_request
    def check_ip():
        client_ip = get_client_ip()

        if client_ip not in allowed_ips:
            logger.warning("Blocked access from IP: %s to %s", client_ip, request.path)
            abort(403)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
./venv/bin/pytest tests/test_ip_restriction.py::TestIPRestrictionMiddleware -v
```

Expected: 4 passed

- [ ] **Step 5: Run all middleware tests**

```bash
./venv/bin/pytest tests/test_ip_restriction.py -v
```

Expected: 12 passed

- [ ] **Step 6: Commit**

```bash
git add middleware.py tests/test_ip_restriction.py
git commit -m "feat: add init_ip_restriction middleware

Registers before_request handler that blocks non-whitelisted IPs
with 403 Forbidden response."
```

---

## Task 5: Create 403 Error Page

**Files:**
- Create: `templates/errors/403.html`

- [ ] **Step 1: Create 403 error template**

Create `templates/errors/403.html`:

```html
{% extends "base.html" %}
{% block title %}403 — Truy cập bị từ chối{% endblock %}
{% block content %}
<div class="error-page">
    <img src="{{ url_for('static', filename='images/logo_2.png') }}" alt="" class="error-page-logo">
    <h1>403</h1>
    <p>Truy cập bị từ chối</p>
    <small>Bạn không có quyền truy cập trang này.</small>
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/errors/403.html
git commit -m "feat: add 403 error page template

Consistent styling with other error pages (404, 500)."
```

---

## Task 6: Integrate Middleware into app.py

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add 403 error handler to app.py**

Add after line 99 (after the 500 error handler):

```python
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403
```

- [ ] **Step 2: Add IP restriction initialization to app.py**

Add after line 87 (after registering blueprints, before error handlers):

```python
    # IP restriction middleware (disabled in test mode)
    if not test_config:
        from middleware import init_ip_restriction
        init_ip_restriction(app)
```

- [ ] **Step 3: Run existing tests to verify no regression**

```bash
./venv/bin/pytest tests/ -v
```

Expected: All tests pass (existing tests use test_config so IP restriction is disabled)

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: integrate IP restriction middleware

- Add 403 error handler
- Initialize IP restriction (disabled in test mode)"
```

---

## Task 7: Create Nginx Config Generator Script

**Files:**
- Create: `scripts/generate_nginx_ip.py`
- Create: `nginx/.gitkeep`

- [ ] **Step 1: Create scripts directory and generator**

```bash
mkdir -p scripts nginx
touch nginx/.gitkeep
```

Create `scripts/generate_nginx_ip.py`:

```python
#!/usr/bin/env python3
"""Generate Nginx IP whitelist config từ ip_whitelist.txt.

Usage:
    python scripts/generate_nginx_ip.py

Output:
    nginx/ip_whitelist.conf
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
WHITELIST_FILE = os.path.join(PROJECT_ROOT, "ip_whitelist.txt")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "nginx", "ip_whitelist.conf")


def load_ips(filepath):
    """Đọc danh sách IP từ file."""
    ips = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ips.append(line)
    return ips


def generate_nginx_config(ips):
    """Tạo nội dung Nginx config."""
    lines = [
        "# Auto-generated from ip_whitelist.txt - DO NOT EDIT",
        "# Regenerate: python scripts/generate_nginx_ip.py",
        "",
    ]

    for ip in ips:
        lines.append(f"allow {ip};")

    lines.append("deny all;")
    lines.append("")

    return "\n".join(lines)


def main():
    if not os.path.exists(WHITELIST_FILE):
        print(f"ERROR: {WHITELIST_FILE} not found")
        sys.exit(1)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    ips = load_ips(WHITELIST_FILE)
    print(f"Loaded {len(ips)} IPs from {WHITELIST_FILE}")

    config = generate_nginx_config(ips)

    with open(OUTPUT_FILE, "w") as f:
        f.write(config)

    print(f"Generated: {OUTPUT_FILE}")
    print()
    print("Next steps:")
    print("  1. Copy nginx/ip_whitelist.conf to /etc/nginx/snippets/")
    print("  2. Run: sudo nginx -t && sudo nginx -s reload")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x scripts/generate_nginx_ip.py
```

- [ ] **Step 3: Test script runs correctly**

```bash
python scripts/generate_nginx_ip.py
cat nginx/ip_whitelist.conf
```

Expected output:
```
# Auto-generated from ip_whitelist.txt - DO NOT EDIT
# Regenerate: python scripts/generate_nginx_ip.py

allow 127.0.0.1;
deny all;
```

- [ ] **Step 4: Add nginx/ip_whitelist.conf to .gitignore**

Append to `.gitignore`:
```
nginx/ip_whitelist.conf
```

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_nginx_ip.py nginx/.gitkeep .gitignore
git commit -m "feat: add Nginx IP whitelist generator script

Reads ip_whitelist.txt and generates nginx/ip_whitelist.conf
with allow/deny rules for Nginx."
```

---

## Task 8: Create Nginx Config Example

**Files:**
- Create: `nginx/laisuat.conf.example`

- [ ] **Step 1: Create Nginx config example**

Create `nginx/laisuat.conf.example`:

```nginx
# Example Nginx configuration for LaiSuat with IP restriction
# Copy to /etc/nginx/sites-available/laisuat and customize

server {
    listen 80;
    server_name laisuat.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name laisuat.example.com;

    # Cloudflare SSL cert
    ssl_certificate /etc/nginx/ssl/cloudflare.crt;
    ssl_certificate_key /etc/nginx/ssl/cloudflare.key;

    # === CLOUDFLARE REAL IP RESTORE ===
    # Source: https://www.cloudflare.com/ips/
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 131.0.72.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;

    # IPv6
    set_real_ip_from 2400:cb00::/32;
    set_real_ip_from 2606:4700::/32;
    set_real_ip_from 2803:f800::/32;
    set_real_ip_from 2405:b500::/32;
    set_real_ip_from 2405:8100::/32;
    set_real_ip_from 2a06:98c0::/29;
    set_real_ip_from 2c0f:f248::/32;

    real_ip_header CF-Connecting-IP;

    # === IP RESTRICTION ===
    include /etc/nginx/snippets/ip_whitelist.conf;

    # Drop connection for blocked IPs (don't reveal site exists)
    error_page 403 = @drop;
    location @drop {
        return 444;
    }

    # Forward headers to Flask
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $host;

    # Flask app
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_read_timeout 60s;
    }

    # Static files
    location /static/ {
        alias /path/to/LaiSuat/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Uploads (PDFs)
    location /uploads/ {
        alias /path/to/LaiSuat/uploads/;
        expires 1d;
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add nginx/laisuat.conf.example
git commit -m "docs: add Nginx config example with IP restriction

Includes Cloudflare real IP restoration and IP whitelist."
```

---

## Task 9: Final Integration Test

**Files:**
- None (verification only)

- [ ] **Step 1: Run all tests**

```bash
./venv/bin/pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 2: Test dev server manually**

```bash
python app.py
```

In another terminal:
```bash
# Should work (127.0.0.1 is in whitelist)
curl http://localhost:5000/

# Verify IP restriction is active in logs
# Should see: "Loaded 1 IPs from whitelist"
```

- [ ] **Step 3: Create final commit with summary**

```bash
git add -A
git status
# If there are any uncommitted changes, commit them

git log --oneline -10
# Verify all commits are in place
```

---

## Deployment Checklist (Manual)

After implementation is complete, deploy to production:

- [ ] Copy `ip_whitelist.example.txt` to `ip_whitelist.txt` on server
- [ ] Add real company IP addresses to `ip_whitelist.txt`
- [ ] Run `python scripts/generate_nginx_ip.py`
- [ ] Copy `nginx/ip_whitelist.conf` to `/etc/nginx/snippets/`
- [ ] Update Nginx config based on `nginx/laisuat.conf.example`
- [ ] Test Nginx config: `sudo nginx -t`
- [ ] Reload Nginx: `sudo nginx -s reload`
- [ ] Restart Flask app: `sudo systemctl restart laisuat`
- [ ] Test from allowed IP: should work
- [ ] Test from outside IP: should drop connection
