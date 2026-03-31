# Admin Logout Redirect & Cache Prevention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sau khi logout admin, redirect về trang chủ `/` và ngăn trình duyệt cache trang admin.

**Architecture:** Thêm `after_request` handler trong admin blueprint để set no-cache headers cho tất cả responses. Sửa logout route redirect từ `/admin/login` sang `/`.

**Tech Stack:** Flask, Flask-Login

---

## File Structure

- **Modify:** `routes_admin.py` - thêm `after_request` handler và sửa logout redirect

---

### Task 1: Thêm no-cache headers cho admin blueprint

**Files:**
- Modify: `routes_admin.py:23-24` (sau khai báo blueprint)
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write the failing test for no-cache headers**

Thêm test vào `tests/test_admin.py`:

```python
class TestNoCacheHeaders:
    """Test cache prevention headers on admin routes."""

    def test_admin_dashboard_has_no_cache_headers(self, auth_client):
        """Admin dashboard should have no-cache headers."""
        response = auth_client.get("/admin")
        assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate, max-age=0"
        assert response.headers.get("Pragma") == "no-cache"
        assert response.headers.get("Expires") == "0"

    def test_admin_login_page_has_no_cache_headers(self, client):
        """Admin login page should have no-cache headers."""
        response = client.get("/admin/login")
        assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate, max-age=0"
        assert response.headers.get("Pragma") == "no-cache"
        assert response.headers.get("Expires") == "0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_admin.py::TestNoCacheHeaders -v`

Expected: FAIL với `AssertionError` vì headers chưa được set

- [ ] **Step 3: Add after_request handler**

Thêm vào `routes_admin.py` sau dòng `admin_bp = Blueprint(...)` (khoảng dòng 23-24):

```python
@admin_bp.after_request
def add_no_cache_headers(response):
    """Prevent browser from caching admin pages."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_admin.py::TestNoCacheHeaders -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add routes_admin.py tests/test_admin.py
git commit -m "feat: add no-cache headers to admin routes

Prevents browser from caching admin pages, so pressing Back
after logout won't show cached content.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Redirect logout về trang chủ

**Files:**
- Modify: `routes_admin.py:56` (logout route)
- Test: `tests/test_admin.py`

- [ ] **Step 1: Write the failing test for logout redirect**

Thêm test vào `tests/test_admin.py`:

```python
class TestLogoutRedirect:
    """Test logout redirects to homepage."""

    def test_logout_redirects_to_homepage(self, auth_client):
        """Logout should redirect to homepage, not login page."""
        response = auth_client.post("/admin/logout")
        assert response.status_code == 302
        assert response.headers.get("Location") == "/"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_admin.py::TestLogoutRedirect -v`

Expected: FAIL với `AssertionError: assert '/admin/login' == '/'`

- [ ] **Step 3: Change logout redirect to homepage**

Sửa `routes_admin.py` dòng 56, trong function `logout()`:

```python
# Before:
return redirect(url_for("admin.login"))

# After:
return redirect(url_for("public.index"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_admin.py::TestLogoutRedirect -v`

Expected: PASS

- [ ] **Step 5: Run all tests to ensure no regression**

Run: `./venv/bin/pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add routes_admin.py tests/test_admin.py
git commit -m "feat: redirect logout to homepage instead of login page

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Manual Testing

- [ ] **Step 1: Start dev server**

Run: `python app.py`

- [ ] **Step 2: Test logout flow**

1. Mở browser, vào `http://localhost:5000/admin/login`
2. Login với admin/admin123
3. Navigate qua các trang admin (dashboard, change-password)
4. Click "Đăng xuất"
5. Verify: redirect về `http://localhost:5000/` (trang chủ)
6. Bấm Back trên browser
7. Verify: không thấy cached admin page, bị redirect về `/admin/login`

- [ ] **Step 3: Verify cache headers in DevTools**

1. Mở DevTools (F12) → Network tab
2. Login admin và vào `/admin`
3. Check Response Headers của request `/admin`
4. Verify có:
   - `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`
   - `Pragma: no-cache`
   - `Expires: 0`
