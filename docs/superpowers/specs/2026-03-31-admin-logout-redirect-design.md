# Admin Logout Redirect & Cache Prevention

## Problem

Sau khi logout admin, trình duyệt vẫn cho phép bấm Back để xem trang admin đã cache. Ngoài ra, logout hiện redirect về `/admin/login` thay vì trang chủ.

## Solution

1. **Redirect về trang chủ:** Đổi logout redirect từ `/admin/login` sang `/`
2. **Ngăn cache trang admin:** Thêm `after_request` handler trong admin blueprint để set no-cache headers

## Changes

### File: `routes_admin.py`

**1. Thêm `after_request` handler (sau dòng khai báo blueprint):**

```python
@admin_bp.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
```

**2. Sửa logout route (dòng 56):**

```python
# Before
return redirect(url_for("admin.login"))

# After
return redirect(url_for("public.index"))
```

## Testing

1. Login admin → navigate qua các trang admin
2. Logout → verify redirect về `/` (trang chủ)
3. Bấm Back trên trình duyệt → verify không thấy cached admin page, bị redirect về `/admin/login`
4. Verify các trang admin khác (dashboard, change-password) cũng không bị cache

## Files Affected

- `routes_admin.py` (2 changes)
