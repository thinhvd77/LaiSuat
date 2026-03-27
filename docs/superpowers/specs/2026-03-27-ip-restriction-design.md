# IP Restriction Design Spec

Giới hạn truy cập website chỉ từ các IP public của công ty, chặn mọi truy cập từ internet bên ngoài.

## Yêu cầu

- Chỉ các thiết bị sử dụng mạng internet từ router công ty mới được truy cập
- Hỗ trợ nhiều văn phòng/chi nhánh với các IP public khác nhau
- Defense-in-depth: chặn ở cả tầng Nginx và Flask
- IP không được phép: drop connection (không tiết lộ website tồn tại)
- Danh sách IP lưu trong file riêng, reload thủ công khi thay đổi
- Admin cũng bị giới hạn IP như public routes

## Môi trường deploy

- Server công ty với IP tĩnh
- Nginx reverse proxy
- Domain + Cloudflare proxy (SSL)
- Traffic flow: Client → Cloudflare → Nginx → Flask

## Kiến trúc

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CLOUDFLARE PROXY                            │
│  • SSL termination                                              │
│  • Thêm header CF-Connecting-IP: <real client IP>               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX                                   │
│  • Restore real IP từ CF-Connecting-IP (realip module)          │
│  • Check IP whitelist (allow/deny)                              │
│  • IP không hợp lệ → return 444 (drop connection)               │
│  • IP hợp lệ → proxy_pass to Flask                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FLASK APP                                  │
│  • Middleware check IP (defense-in-depth)                       │
│  • IP không hợp lệ → 403 Forbidden                              │
│  • IP hợp lệ → xử lý request bình thường                        │
└─────────────────────────────────────────────────────────────────┘
```

## Files

| File | Loại | Mô tả |
|------|------|-------|
| `ip_whitelist.txt` | Mới | Danh sách IP được phép (nguồn dữ liệu chính) |
| `middleware.py` | Mới | Flask middleware check IP |
| `scripts/generate_nginx_ip.py` | Mới | Script generate Nginx config từ whitelist |
| `nginx/ip_whitelist.conf` | Mới (generated) | Nginx whitelist config |
| `templates/errors/403.html` | Mới | Trang lỗi 403 |
| `tests/test_ip_restriction.py` | Mới | Unit tests |
| `app.py` | Sửa | Thêm error handler 403, init middleware |

## Chi tiết implementation

### 1. File `ip_whitelist.txt`

Format đơn giản, mỗi dòng một IP. Hỗ trợ comment (#) và dòng trống:

```
# Danh sách IP được phép truy cập
# Mỗi dòng một IP, dòng trống và comment (#) được bỏ qua

# Văn phòng chính
113.161.x.x

# Chi nhánh Hà Nội
118.70.x.x

# Chi nhánh Đà Nẵng
171.244.x.x
```

### 2. File `middleware.py`

Module chứa:
- `load_ip_whitelist(filepath)`: Đọc danh sách IP từ file, trả về `set`
- `get_client_ip()`: Lấy IP thực từ headers (ưu tiên `CF-Connecting-IP` → `X-Real-IP` → `remote_addr`)
- `init_ip_restriction(app)`: Đăng ký `@app.before_request` middleware

```python
import os
import logging
from flask import request, abort

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

def init_ip_restriction(app):
    """Khởi tạo middleware check IP cho Flask app."""
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

### 3. Tích hợp vào `app.py`

Trong `create_app()`, sau khi register blueprints:

```python
from middleware import init_ip_restriction

# Chỉ áp dụng IP restriction khi không phải test
if not test_config:
    init_ip_restriction(app)

# Error handler cho 403
@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403
```

### 4. File `scripts/generate_nginx_ip.py`

Script đọc `ip_whitelist.txt` và generate `nginx/ip_whitelist.conf`:

```python
#!/usr/bin/env python3
"""Generate Nginx IP whitelist config từ ip_whitelist.txt"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
WHITELIST_FILE = os.path.join(PROJECT_ROOT, "ip_whitelist.txt")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "nginx", "ip_whitelist.conf")

def load_ips(filepath):
    ips = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ips.append(line)
    return ips

def generate_nginx_config(ips):
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
    print("\nNext steps:")
    print("  1. Copy nginx/ip_whitelist.conf to /etc/nginx/snippets/")
    print("  2. Run: sudo nginx -t && sudo nginx -s reload")

if __name__ == "__main__":
    main()
```

### 5. Nginx configuration

Cấu hình `/etc/nginx/sites-available/laisuat`:

```nginx
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

    error_page 403 = @drop;
    location @drop {
        return 444;
    }

    # Forward headers to Flask
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header Host $host;

    location / {
        proxy_pass http://127.0.0.1:5000;
    }

    location /static/ {
        alias /path/to/LaiSuat/static/;
        expires 7d;
    }
}
```

### 6. File `templates/errors/403.html`

```html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Truy cập bị từ chối</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="error-page">
        <h1>403</h1>
        <p>Truy cập bị từ chối</p>
        <small>Bạn không có quyền truy cập trang này.</small>
    </div>
</body>
</html>
```

### 7. Tests

File `tests/test_ip_restriction.py` bao gồm:
- `TestLoadIPWhitelist`: Test đọc file whitelist (valid, comments, missing file)
- `TestIPRestrictionMiddleware`: Test chặn/cho phép IP
- `TestGetClientIP`: Test lấy IP từ các headers (CF-Connecting-IP, X-Real-IP, remote_addr)

## Quy trình cập nhật IP whitelist

```bash
# 1. Sửa danh sách IP
nano ip_whitelist.txt

# 2. Generate Nginx config
python scripts/generate_nginx_ip.py

# 3. Copy và reload Nginx
sudo cp nginx/ip_whitelist.conf /etc/nginx/snippets/
sudo nginx -t && sudo nginx -s reload

# 4. Restart Flask
sudo systemctl restart laisuat
```

## Checklist triển khai

- [ ] Tạo `ip_whitelist.txt` với IP công ty thực tế
- [ ] Tạo `middleware.py`
- [ ] Cập nhật `app.py` (error handler + init middleware)
- [ ] Tạo `templates/errors/403.html`
- [ ] Tạo `scripts/generate_nginx_ip.py`
- [ ] Tạo thư mục `nginx/`
- [ ] Chạy script generate Nginx config
- [ ] Cập nhật Nginx config (realip + include whitelist)
- [ ] Viết tests
- [ ] Test trên môi trường staging
- [ ] Deploy production

## Lưu ý bảo mật

- Cloudflare IP ranges cần cập nhật định kỳ từ https://www.cloudflare.com/ips/
- Không commit IP thực của công ty vào git (thêm `ip_whitelist.txt` vào `.gitignore` hoặc dùng file example)
- Nginx drop connection (444) không tiết lộ website tồn tại cho IP bên ngoài
- Flask 403 chỉ là fallback khi request bypass Nginx
