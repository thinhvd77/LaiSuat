# Hướng dẫn Deploy — Nginx + Gunicorn + Flask

## Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Yêu cầu hệ thống](#2-yêu-cầu-hệ-thống)
3. [Cài đặt trên server](#3-cài-đặt-trên-server)
4. [Cấu hình Gunicorn](#4-cấu-hình-gunicorn)
5. [Cấu hình systemd](#5-cấu-hình-systemd)
6. [Cấu hình Nginx](#6-cấu-hình-nginx)
7. [SSL/HTTPS với Certbot](#7-sslhttps-với-certbot)
8. [Khởi chạy & Kiểm tra](#8-khởi-chạy--kiểm-tra)
9. [Bảo trì & Cập nhật](#9-bảo-trì--cập-nhật)
10. [Xử lý sự cố](#10-xử-lý-sự-cố)

---

## 1. Tổng quan kiến trúc

```
┌──────────┐      ┌───────────────┐      ┌──────────────────┐
│  Client   │─────▶│  Nginx (:80)  │─────▶│  Gunicorn (:8000)│
│ (Browser) │◀─────│  Reverse Proxy│◀─────│  Flask App       │
└──────────┘      └───────────────┘      └──────────────────┘
                         │
                         ├── Serve static files trực tiếp (CSS, JS, images)
                         ├── Serve uploaded PDFs trực tiếp
                         ├── SSL termination (HTTPS)
                         ├── Gzip compression
                         └── Rate limiting (bổ sung)
```

**Nginx** xử lý:
- Nhận request từ client (port 80/443)
- Serve trực tiếp static files (`/static/`) và PDF uploads — **không qua Gunicorn**
- Reverse proxy các request động đến Gunicorn
- SSL termination, gzip, caching headers

**Gunicorn** xử lý:
- Chạy Flask app với nhiều worker processes
- Nhận request từ Nginx qua Unix socket (nhanh hơn TCP)

---

## 2. Yêu cầu hệ thống

- **OS**: Ubuntu 22.04 / 24.04 LTS (hoặc Debian 12)
- **Python**: 3.10+
- **RAM**: tối thiểu 512MB (khuyến nghị 1GB)
- **Disk**: tối thiểu 1GB (+ dung lượng cho PDF uploads)
- **Domain**: trỏ A record về IP server (ví dụ: `laisuat.example.com`)

---

## 3. Cài đặt trên server

### 3.1. Cập nhật hệ thống & cài packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git
```

### 3.2. Tạo user riêng cho app (khuyến nghị)

```bash
sudo useradd -m -s /bin/bash laisuat
sudo su - laisuat
```

### 3.3. Clone project & cài dependencies

```bash
cd /home/laisuat
git clone <your-repo-url> LaiSuat
cd LaiSuat

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3.4. Tạo file `.env`

```bash
cat > .env << 'EOF'
SECRET_KEY=thay-bang-chuoi-random-dai-va-phuc-tap
DATABASE_URL=sqlite:///database.db
EOF
```

Sinh `SECRET_KEY` an toàn:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3.5. Khởi tạo database

```bash
source venv/bin/activate
export $(cat .env | xargs)
flask --app app init-db
```

### 3.6. Tạo thư mục cần thiết & phân quyền

```bash
mkdir -p uploads instance
chmod 750 uploads instance
```

---

## 4. Cấu hình Gunicorn

### 4.1. Tạo file cấu hình Gunicorn

```bash
cat > gunicorn.conf.py << 'EOF'
# gunicorn.conf.py — Cấu hình Gunicorn cho LaiSuat

import multiprocessing

# Socket
bind = "unix:/home/laisuat/LaiSuat/laisuat.sock"

# Workers
# Công thức: (2 × CPU cores) + 1
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class
worker_class = "sync"

# Timeout (giây) — tăng nếu upload file lớn
timeout = 120
graceful_timeout = 30

# Logging
accesslog = "/home/laisuat/LaiSuat/logs/gunicorn-access.log"
errorlog = "/home/laisuat/LaiSuat/logs/gunicorn-error.log"
loglevel = "info"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Process naming
proc_name = "laisuat"

# Preload app — tiết kiệm RAM
preload_app = True
EOF
```

### 4.2. Tạo thư mục logs

```bash
mkdir -p /home/laisuat/LaiSuat/logs
```

### 4.3. Test Gunicorn thủ công

```bash
source venv/bin/activate
export $(cat .env | xargs)
gunicorn --config gunicorn.conf.py "app:create_app()"
```

Kiểm tra socket được tạo:

```bash
ls -la /home/laisuat/LaiSuat/laisuat.sock
```

Nhấn `Ctrl+C` để dừng sau khi xác nhận hoạt động.

---

## 5. Cấu hình systemd

Tạo service file để Gunicorn tự khởi động cùng hệ thống.

### 5.1. Tạo service file

```bash
sudo tee /etc/systemd/system/laisuat.service << 'EOF'
[Unit]
Description=LaiSuat Gunicorn Flask App
After=network.target

[Service]
User=laisuat
Group=laisuat
WorkingDirectory=/home/laisuat/LaiSuat
EnvironmentFile=/home/laisuat/LaiSuat/.env
ExecStart=/home/laisuat/LaiSuat/venv/bin/gunicorn \
    --config gunicorn.conf.py \
    "app:create_app()"
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5

# Security hardening
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/laisuat/LaiSuat/instance
ReadWritePaths=/home/laisuat/LaiSuat/uploads
ReadWritePaths=/home/laisuat/LaiSuat/logs

[Install]
WantedBy=multi-user.target
EOF
```

### 5.2. Kích hoạt service

```bash
sudo systemctl daemon-reload
sudo systemctl enable laisuat
sudo systemctl start laisuat
sudo systemctl status laisuat
```

Kết quả mong đợi:

```
● laisuat.service - LaiSuat Gunicorn Flask App
     Active: active (running) since ...
```

---

## 6. Cấu hình Nginx

### 6.1. Tạo Nginx site config

```bash
sudo tee /etc/nginx/sites-available/laisuat << 'EOF'
# ─── Redirect HTTP → HTTPS ───
server {
    listen 80;
    listen [::]:80;
    server_name laisuat.example.com;

    # Certbot challenge (cần cho bước lấy SSL)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect tất cả sang HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

# ─── HTTPS server ───
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name laisuat.example.com;

    # SSL certificates (sẽ cấu hình ở bước 7)
    # ssl_certificate /etc/letsencrypt/live/laisuat.example.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/laisuat.example.com/privkey.pem;
    # include /etc/letsencrypt/options-ssl-nginx.conf;
    # ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # ─── Security headers ───
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; worker-src 'self' blob:;" always;

    # ─── Giới hạn upload ───
    client_max_body_size 16M;

    # ─── Gzip ───
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 1000;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/javascript
        application/json
        application/xml
        image/svg+xml;

    # ─── Static files — serve trực tiếp, không qua Gunicorn ───
    location /static/ {
        alias /home/laisuat/LaiSuat/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
        access_log off;

        # Font files CORS
        location ~* \.(woff2?|ttf|eot|otf)$ {
            add_header Access-Control-Allow-Origin "*";
            expires 365d;
        }
    }

    # ─── PDF.js library ───
    location /static/pdfjs/ {
        alias /home/laisuat/LaiSuat/static/pdfjs/;
        expires 365d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # ─── Uploaded PDFs — serve trực tiếp ───
    # (App route /pdf/<id> vẫn cần Gunicorn để check DB,
    #  nhưng Nginx cache response sẽ giảm tải)

    # ─── Reverse proxy đến Gunicorn ───
    location / {
        proxy_pass http://unix:/home/laisuat/LaiSuat/laisuat.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout cho upload lớn
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;

        # Buffer
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 16k;
    }

    # ─── Chặn truy cập file nhạy cảm ───
    location ~ /\.(env|git|gitignore) {
        deny all;
        return 404;
    }

    location ~ /(instance|logs|__pycache__|venv) {
        deny all;
        return 404;
    }

    # ─── Logging ───
    access_log /var/log/nginx/laisuat-access.log;
    error_log /var/log/nginx/laisuat-error.log;
}
EOF
```

### 6.2. Kích hoạt site

```bash
# Tạo symlink
sudo ln -s /etc/nginx/sites-available/laisuat /etc/nginx/sites-enabled/

# Xóa default site (tùy chọn)
sudo rm -f /etc/nginx/sites-enabled/default

# Kiểm tra cú pháp
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### 6.3. Tạm thời test HTTP (trước khi có SSL)

Nếu chưa có SSL, comment block `server :443` và sửa block `server :80`:

```nginx
server {
    listen 80;
    server_name laisuat.example.com;

    client_max_body_size 16M;

    location /static/ {
        alias /home/laisuat/LaiSuat/static/;
        expires 30d;
    }

    location / {
        proxy_pass http://unix:/home/laisuat/LaiSuat/laisuat.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 7. SSL/HTTPS với Certbot

### 7.1. Cài Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 7.2. Lấy certificate

```bash
sudo certbot --nginx -d laisuat.example.com
```

Certbot sẽ tự động:
- Xác thực domain
- Tạo certificate
- Cập nhật Nginx config (uncomment SSL lines)
- Thiết lập auto-renew

### 7.3. Kiểm tra auto-renew

```bash
sudo certbot renew --dry-run
```

### 7.4. Uncomment SSL trong Nginx config

Sau khi Certbot thành công, đảm bảo các dòng SSL đã được uncomment:

```nginx
ssl_certificate /etc/letsencrypt/live/laisuat.example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/laisuat.example.com/privkey.pem;
include /etc/letsencrypt/options-ssl-nginx.conf;
ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. Khởi chạy & Kiểm tra

### 8.1. Checklist trước khi chạy

```bash
# 1. Kiểm tra .env đã có SECRET_KEY thật
cat /home/laisuat/LaiSuat/.env

# 2. Kiểm tra database đã init
ls -la /home/laisuat/LaiSuat/instance/database.db

# 3. Kiểm tra quyền thư mục
ls -la /home/laisuat/LaiSuat/uploads/
ls -la /home/laisuat/LaiSuat/instance/

# 4. Kiểm tra Gunicorn đang chạy
sudo systemctl status laisuat

# 5. Kiểm tra Nginx đang chạy
sudo systemctl status nginx

# 6. Kiểm tra socket file
ls -la /home/laisuat/LaiSuat/laisuat.sock
```

### 8.2. Kiểm tra từ trình duyệt

```
https://laisuat.example.com        → Trang chủ
https://laisuat.example.com/admin  → Trang admin (redirect đến login)
```

### 8.3. Kiểm tra từ command line

```bash
# Test HTTP → HTTPS redirect
curl -I http://laisuat.example.com

# Test trang chủ
curl -s https://laisuat.example.com | head -20

# Test API
curl -s https://laisuat.example.com/api/categories | python3 -m json.tool

# Test static file caching
curl -I https://laisuat.example.com/static/css/style.css
# Kỳ vọng: Cache-Control: public, immutable; Expires: ...
```

---

## 9. Bảo trì & Cập nhật

### 9.1. Cập nhật code

```bash
sudo su - laisuat
cd /home/laisuat/LaiSuat
git pull origin main

# Cài dependencies mới (nếu có)
source venv/bin/activate
pip install -r requirements.txt

# Chạy migration (nếu có)
# python migrate_xxx.py

# Restart app (graceful — không downtime)
exit  # Thoát user laisuat
sudo systemctl reload laisuat
```

### 9.2. Xem logs

```bash
# Gunicorn logs
tail -f /home/laisuat/LaiSuat/logs/gunicorn-error.log
tail -f /home/laisuat/LaiSuat/logs/gunicorn-access.log

# Nginx logs
sudo tail -f /var/log/nginx/laisuat-access.log
sudo tail -f /var/log/nginx/laisuat-error.log

# Systemd logs
sudo journalctl -u laisuat -f
```

### 9.3. Backup database

```bash
# Backup thủ công
cp /home/laisuat/LaiSuat/instance/database.db \
   /home/laisuat/backups/database-$(date +%Y%m%d-%H%M%S).db

# Cron job backup hàng ngày (2h sáng)
sudo -u laisuat crontab -e
# Thêm dòng:
# 0 2 * * * cp /home/laisuat/LaiSuat/instance/database.db /home/laisuat/backups/database-$(date +\%Y\%m\%d).db
```

### 9.4. Log rotation

```bash
sudo tee /etc/logrotate.d/laisuat << 'EOF'
/home/laisuat/LaiSuat/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 laisuat laisuat
    postrotate
        systemctl reload laisuat > /dev/null 2>&1 || true
    endscript
}
EOF
```

---

## 10. Xử lý sự cố

### Lỗi 502 Bad Gateway

```bash
# Kiểm tra Gunicorn có đang chạy không
sudo systemctl status laisuat

# Kiểm tra socket file tồn tại
ls -la /home/laisuat/LaiSuat/laisuat.sock

# Kiểm tra quyền socket — Nginx (user www-data) phải đọc được
# Thêm www-data vào group laisuat:
sudo usermod -aG laisuat www-data
sudo systemctl restart nginx
```

### Lỗi 413 Request Entity Too Large

Đảm bảo `client_max_body_size` trong Nginx config **≥** `MAX_CONTENT_LENGTH` trong Flask (16MB).

### Lỗi Permission denied

```bash
# Kiểm tra quyền thư mục
sudo -u laisuat ls -la /home/laisuat/LaiSuat/uploads/
sudo -u laisuat ls -la /home/laisuat/LaiSuat/instance/

# Fix quyền
sudo chown -R laisuat:laisuat /home/laisuat/LaiSuat/uploads/
sudo chown -R laisuat:laisuat /home/laisuat/LaiSuat/instance/
sudo chmod 750 /home/laisuat/LaiSuat/uploads/
sudo chmod 750 /home/laisuat/LaiSuat/instance/
```

### Static files trả 404

```bash
# Kiểm tra đường dẫn alias trong Nginx
ls -la /home/laisuat/LaiSuat/static/

# Kiểm tra Nginx user có quyền đọc
sudo -u www-data ls /home/laisuat/LaiSuat/static/css/style.css

# Nếu không đọc được, thêm execute permission cho thư mục cha
chmod o+x /home/laisuat /home/laisuat/LaiSuat
```

### Database bị lock

```bash
# SQLite WAL mode đã được bật, nhưng nếu gặp lock:
# Kiểm tra có process nào đang giữ lock
fuser /home/laisuat/LaiSuat/instance/database.db

# Restart Gunicorn
sudo systemctl restart laisuat
```

---

## Tóm tắt các lệnh hay dùng

```bash
# Quản lý service
sudo systemctl start laisuat     # Khởi động
sudo systemctl stop laisuat      # Dừng
sudo systemctl restart laisuat   # Khởi động lại
sudo systemctl reload laisuat    # Reload (graceful)
sudo systemctl status laisuat    # Xem trạng thái

# Nginx
sudo nginx -t                     # Kiểm tra config
sudo systemctl reload nginx       # Reload config

# Logs
sudo journalctl -u laisuat -n 50  # 50 dòng log gần nhất
sudo journalctl -u laisuat -f     # Follow realtime
```
