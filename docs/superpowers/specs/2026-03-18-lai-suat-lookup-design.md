# Trang Web Tra Cứu Lãi Suất Ngân Hàng — Design Spec

**Ngày:** 2026-03-18
**Trạng thái:** Ready for Review

---

## 1. Tổng quan

Trang web nội bộ cho phép:

- **Khách hàng** tra cứu và xem trực tiếp các file PDF lãi suất theo danh mục
- **Nhân viên ngân hàng** đăng nhập để quản lý danh mục và upload/xóa file PDF

Triển khai trên server nội bộ, sử dụng Flask + SQLite + PDF.js.

## 2. Người dùng

| Vai trò | Quyền |
|---------|-------|
| Khách hàng (public) | Xem danh mục, xem PDF trực tiếp trên web |
| Nhân viên (admin) | Đăng nhập, quản lý danh mục (CRUD), upload/xóa PDF |

## 3. Kiến trúc

```
┌─────────────────────────────────────────────────┐
│                  Flask App (app.py)              │
│                                                   │
│  ┌──────────────┐    ┌──────────────────────┐    │
│  │  Public Routes│    │   Admin Routes        │    │
│  │  /            │    │   /admin/login        │    │
│  │  /view/<id>   │    │   /admin/dashboard    │    │
│  │  /pdf/<id>    │    │   /admin/upload       │    │
│  │               │    │   /admin/categories   │    │
│  └──────┬───────┘    └──────────┬───────────┘    │
│         │                        │  (login req)   │
│         └────────┬───────────────┘                │
│                  ▼                                 │
│          ┌──────────────┐   ┌──────────────┐      │
│          │  SQLite DB   │   │  uploads/     │      │
│          │  (metadata)  │   │  (PDF files)  │      │
│          └──────────────┘   └──────────────┘      │
└─────────────────────────────────────────────────┘
```

**Thành phần:**

- **Flask App** — 1 file Python chính chạy web server
- **SQLite Database** — lưu metadata: danh mục, PDF info, admin users
- **uploads/** — thư mục chứa file PDF thực tế
- **PDF.js** — thư viện Mozilla embed PDF trực tiếp trên browser

### 3b. Routes

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| GET | `/` | Không | Trang chủ tra cứu lãi suất |
| GET | `/api/categories` | Không | Danh sách danh mục (JSON) |
| GET | `/api/categories/<id>/pdfs` | Không | Danh sách PDF của danh mục (JSON) |
| GET | `/pdf/<id>` | Không | Serve file PDF (`Content-Type: application/pdf`, `Content-Disposition: inline`) |
| GET | `/admin/login` | Không | Trang đăng nhập |
| POST | `/admin/login` | Không | Xử lý đăng nhập (username + password, rate limit: 5 lần/phút) |
| POST | `/admin/logout` | Admin | Đăng xuất (POST + CSRF token) |
| GET | `/admin` | Admin | Trang quản lý chính |
| POST | `/admin/categories` | Admin | Thêm danh mục mới (name, icon) |
| PUT | `/admin/categories/<id>` | Admin | Sửa danh mục (name, icon, sort_order) |
| DELETE | `/admin/categories/<id>` | Admin | Xóa danh mục (chỉ khi rỗng) |
| POST | `/admin/pdfs` | Admin | Upload PDF (file + title + category_id) |
| DELETE | `/admin/pdfs/<id>` | Admin | Xóa PDF (xóa cả file trên disk) |
| GET | `/admin/change-password` | Admin | Form đổi mật khẩu |
| POST | `/admin/change-password` | Admin | Xử lý đổi mật khẩu |

> **Ghi chú:** PUT/DELETE routes được gọi qua JavaScript `fetch()` từ admin panel. Các `/api/*` routes trả JSON phục vụ frontend AJAX, không phải public REST API cho bên thứ ba.

## 4. Database Schema

```sql
-- Bảng danh mục lãi suất
categories
├── id          INTEGER PRIMARY KEY
├── name        TEXT NOT NULL        -- "Lãi suất tiết kiệm"
├── icon        TEXT                 -- "💰"
├── sort_order  INTEGER DEFAULT 0   -- thứ tự hiển thị trên sidebar
├── created_at  DATETIME DEFAULT CURRENT_TIMESTAMP

-- Bảng file PDF
pdfs
├── id          INTEGER PRIMARY KEY
├── category_id INTEGER FK → categories.id ON DELETE RESTRICT
├── title       TEXT NOT NULL        -- tên hiển thị
├── filename    TEXT UNIQUE NOT NULL -- tên file trên disk (sanitized, UUID prefix)
├── file_size   INTEGER              -- bytes
├── uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
├── uploaded_by INTEGER FK → admins.id ON DELETE SET NULL

-- Bảng admin users
admins
├── id                    INTEGER PRIMARY KEY
├── username              TEXT UNIQUE NOT NULL
├── password              TEXT NOT NULL        -- bcrypt hash
├── force_password_change BOOLEAN DEFAULT 1   -- bắt đổi pass lần đầu
├── created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
```

**Ràng buộc:**

- `pdfs.category_id` → FK tới `categories.id` với `ON DELETE RESTRICT`
- `pdfs.uploaded_by` → FK tới `admins.id` với `ON DELETE SET NULL` (nullable)
- `pdfs.filename` là `UNIQUE`, prefix UUID khi lưu để tránh trùng
- Không cho xóa danh mục nếu còn PDF bên trong
- `filename` được sanitize khi lưu (tránh path traversal)
- SQLite chạy ở chế độ **WAL** (`PRAGMA journal_mode=WAL`) để hỗ trợ concurrent reads

## 5. Giao diện

### 5a. Trang công khai — Tra cứu lãi suất (Layout: Sidebar + Viewer)

```
┌─────────────────────────────────────────┐
│  Header: Tên ngân hàng / Logo           │
├──────────────┬──────────────────────────┤
│  Sidebar     │  PDF Viewer              │
│              │                           │
│  💰 Tiết kiệm│  [Dropdown chọn file]   │
│  🏦 Cho vay   │                          │
│  💳 Thẻ TD   │  ┌──────────────────┐    │
│  🏠 Vay nhà  │  │                  │    │
│  🚗 Vay xe   │  │   PDF.js embed   │    │
│  📊 Liên NH  │  │                  │    │
│              │  └──────────────────┘    │
└──────────────┴──────────────────────────┘
```

**Hành vi:**

- Vào trang → tự động chọn danh mục đầu tiên, hiện PDF mới nhất
- Click danh mục → PDF viewer reload file mới nhất của danh mục đó
- Danh mục có nhiều PDF → dropdown phía trên viewer để chọn file
- Sidebar hiện số lượng PDF mỗi danh mục
- Không cho phép download PDF (ẩn nút download của PDF.js)

**Trạng thái rỗng:**

- Chưa có danh mục nào → hiện "Chưa có danh mục lãi suất nào."
- Danh mục không có PDF → hiện "Chưa có tài liệu nào trong danh mục này."
- File PDF bị mất trên disk → hiện "Không tìm thấy tài liệu. Vui lòng liên hệ quản trị viên."

### 5b. Admin Panel — Quản lý theo danh mục (Layout: Sidebar + List)

```
┌─────────────────────────────────────────┐
│  Header: Admin Panel    [Đăng xuất]     │
├──────────────┬──────────────────────────┤
│  Sidebar     │  Danh sách PDF           │
│              │                           │
│  [+ Thêm]   │  Tên danh mục (n file)   │
│  💰 Tiết kiệm 3│  [+ Upload PDF]       │
│  🏦 Cho vay   5│                        │
│  💳 Thẻ TD   2│  📄 file1.pdf          │
│              │     Xem · Xóa            │
│  Sửa / Xóa  │  📄 file2.pdf           │
│  danh mục    │     Xem · Xóa            │
└──────────────┴──────────────────────────┘
```

**Hành vi:**

- **Thêm danh mục** → modal nhập tên + chọn icon
- **Sửa danh mục** → đổi tên, đổi icon, đổi thứ tự (nút ▲▼ di chuyển lên/xuống)
- **Xóa danh mục** → chỉ khi không còn PDF bên trong
- **Upload PDF** → form chọn file + nhập tên hiển thị, tự detect kích thước
- **Xóa PDF** → confirm trước khi xóa, xóa cả file trên disk

### 5c. Trang đăng nhập

- Form đơn giản: username + password
- Hiện lỗi nếu sai thông tin
- Redirect về admin dashboard sau khi login thành công

## 6. Bảo mật

- Admin password hash bằng **bcrypt**
- Flask `SECRET_KEY` cho session encryption
- **CSRF protection** bằng Flask-WTF (tất cả form và state-changing routes đều có CSRF token, bao gồm logout)
- Upload chỉ chấp nhận file `.pdf` + validate magic bytes (`%PDF-` header), giới hạn **16MB**
- Tên file sanitize khi lưu trên disk (tránh path traversal), prefix UUID
- Session tự hết hạn sau **8 giờ**
- **Rate limiting** trên `/admin/login`: tối đa 5 lần/phút bằng Flask-Limiter
- **HTTPS** — triển khai qua reverse proxy (nginx/caddy) với TLS certificate, không expose Flask trực tiếp
- Admin mặc định có `force_password_change=1`, bắt buộc đổi password trước khi dùng các tính năng khác

## 6b. Xử lý lỗi

| Tình huống | HTTP Status | Hiển thị |
|-----------|------------|----------|
| Upload file không phải PDF | 400 | Flash message: "Chỉ chấp nhận file PDF" |
| Upload file quá 16MB | 413 | Flash message: "File vượt quá 16MB" |
| PDF không tìm thấy trong DB | 404 | Trang "Không tìm thấy tài liệu" |
| File PDF bị mất trên disk | 404 | Thông báo lỗi + log warning |
| Xóa danh mục còn PDF | 400 | Flash message: "Không thể xóa danh mục còn tài liệu" |
| Lỗi server | 500 | Trang lỗi chung "Đã xảy ra lỗi" |

## 7. Tech Stack

| Thành phần | Công nghệ | Lý do |
|-----------|-----------|-------|
| Backend | Flask 3.x | Nhẹ, đơn giản, dễ triển khai |
| Database | SQLite 3 | Không cần cài DB server, 1 file |
| ORM | Flask-SQLAlchemy | Thao tác DB bằng Python |
| Auth | Flask-Login + Flask-WTF + Flask-Limiter + bcrypt | Session, CSRF, rate limiting, password hashing |
| PDF Viewer | PDF.js 4.x (Mozilla) | Open-source, render PDF trên browser |
| Frontend | HTML/CSS/JS thuần | Không framework, nhẹ, nhanh |

## 8. Cấu trúc Project

```
LaiSuat/
├── app.py                  # Flask app chính (routes, config)
├── models.py               # SQLAlchemy models
├── database.db             # SQLite database (auto-created)
├── requirements.txt        # Python dependencies
│
├── uploads/                # Thư mục chứa PDF files
│
├── templates/
│   ├── base.html           # Layout chung
│   ├── index.html          # Trang chủ tra cứu (public)
│   ├── login.html          # Trang đăng nhập admin
│   ├── admin.html          # Trang quản lý admin
│   └── change_password.html # Form đổi mật khẩu
│
└── static/
    ├── css/
    │   └── style.css       # Stylesheet chung
    ├── js/
    │   ├── app.js          # Logic trang chủ
    │   └── admin.js        # Logic admin
    └── pdfjs/              # Thư viện PDF.js
        ├── pdf.min.js
        └── pdf.worker.min.js
```

## 9. Triển khai

```bash
# Cài đặt
pip install -r requirements.txt
python app.py --init-db          # Tạo database + admin mặc định

# Development
python app.py                    # http://localhost:5000

# Production (qua reverse proxy nginx với HTTPS)
pip install gunicorn
gunicorn -w 1 --threads 4 -b 127.0.0.1:8080 app:app
```

- **Admin mặc định:** `admin` / `admin123` — bắt buộc đổi password sau lần đăng nhập đầu (redirect tự động tới `/admin/change-password`)
- **Backup:** Copy `database.db` + thư mục `uploads/`
- **Logging:** Flask logging ở mức `INFO` ra stdout, ghi lại login/upload/delete events

## 10. Ngoài phạm vi

- ❌ Tìm kiếm full-text bên trong nội dung PDF
- ❌ Phân quyền nhiều cấp (chỉ 1 role: admin)
- ❌ REST API riêng cho bên thứ ba (internal JSON endpoints cho frontend AJAX vẫn có)
- ❌ Hệ thống thông báo / email
- ❌ Lịch sử chỉnh sửa / audit log
