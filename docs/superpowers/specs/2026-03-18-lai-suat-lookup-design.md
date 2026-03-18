# Trang Web Tra Cứu Lãi Suất Ngân Hàng — Design Spec

**Ngày:** 2026-03-18
**Trạng thái:** Draft

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

## 4. Database Schema

```sql
-- Bảng danh mục lãi suất
categories
├── id          INTEGER PRIMARY KEY
├── name        TEXT NOT NULL        -- "Lãi suất tiết kiệm"
├── icon        TEXT                 -- "💰"
├── sort_order  INTEGER DEFAULT 0   -- thứ tự hiển thị trên sidebar
├── created_at  DATETIME

-- Bảng file PDF
pdfs
├── id          INTEGER PRIMARY KEY
├── category_id INTEGER FK → categories.id
├── title       TEXT NOT NULL        -- tên hiển thị
├── filename    TEXT NOT NULL        -- tên file trên disk (sanitized)
├── file_size   INTEGER              -- bytes
├── uploaded_at DATETIME
├── uploaded_by TEXT                  -- tên admin upload

-- Bảng admin users
admins
├── id          INTEGER PRIMARY KEY
├── username    TEXT UNIQUE NOT NULL
├── password    TEXT NOT NULL        -- bcrypt hash
├── created_at  DATETIME
```

**Ràng buộc:**

- `pdfs.category_id` → foreign key tới `categories.id`
- Không cho xóa danh mục nếu còn PDF bên trong
- `filename` được sanitize khi lưu (tránh path traversal)

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
- **Sửa danh mục** → đổi tên, đổi icon, đổi thứ tự
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
- Upload chỉ chấp nhận file `.pdf`, giới hạn **16MB**
- Tên file sanitize khi lưu trên disk (tránh path traversal)
- Session tự hết hạn sau **8 giờ**

## 7. Tech Stack

| Thành phần | Công nghệ | Lý do |
|-----------|-----------|-------|
| Backend | Flask 3.x | Nhẹ, đơn giản, dễ triển khai |
| Database | SQLite 3 | Không cần cài DB server, 1 file |
| ORM | Flask-SQLAlchemy | Thao tác DB bằng Python |
| Auth | Flask-Login + bcrypt | Session management + password hashing |
| PDF Viewer | PDF.js (Mozilla) | Open-source, render PDF trên browser |
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
│   └── admin.html          # Trang quản lý admin
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

# Production
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

- **Admin mặc định:** `admin` / `admin123` — bắt buộc đổi password sau lần đăng nhập đầu
- **Backup:** Copy `database.db` + thư mục `uploads/`

## 10. Ngoài phạm vi

- ❌ Tìm kiếm full-text bên trong nội dung PDF
- ❌ Phân quyền nhiều cấp (chỉ 1 role: admin)
- ❌ REST API riêng (chỉ server-rendered HTML)
- ❌ Hệ thống thông báo / email
- ❌ Lịch sử chỉnh sửa / audit log
