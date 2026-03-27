# Site Gate Password Design Spec

Thêm lớp bảo mật “cổng mật khẩu” cho **public site**: khi người dùng truy cập website, chưa load nội dung/dữ liệu công khai ngay mà phải nhập đúng mật khẩu mới được truy cập. Nếu nhập sai quá 5 lần theo IP thì khóa trong 15 phút và hiển thị thời gian còn lại.

## Yêu cầu đã chốt

- Phạm vi áp dụng: **chỉ public site** (`/`, `/api/*`, `/pdf/*`)
- Không áp dụng cho admin: `/admin/*`
- Mật khẩu cổng vào: dùng biến môi trường `SITE_GATE_PASSWORD`
- Thời gian mở khóa sau khi nhập đúng: `SITE_GATE_TTL_MINUTES=1440` (24h)
- Chống brute-force theo **IP client**
- Sai quá 5 lần: khóa 15 phút
- Khi chưa unlock mà gọi `/api/*`, `/pdf/*`: trả `403`
- Khi bị khóa: trang nhập mật khẩu hiển thị còn bao lâu mới thử lại

## Mục tiêu

1. Chặn truy cập public content trước khi xác thực cổng vào
2. UX tốt trên điện thoại (form đơn giản, rõ trạng thái)
3. Fail-closed cho kịch bản cấu hình thiếu mật khẩu
4. Không ảnh hưởng flow admin hiện tại

## Kiến trúc tổng quan

### Request flow

1. Request vào route public được bảo vệ (`/`, `/api/*`, `/pdf/*`)
2. Middleware site-gate kiểm tra:
   - IP có đang lockout không
   - Session có đang unlock và còn hạn không
3. Kết quả:
   - Đang lockout:
     - `/` render gate page + countdown
     - `/api/*`, `/pdf/*` trả `403`
   - Chưa unlock:
     - `/` render gate page
     - `/api/*`, `/pdf/*` trả `403`
   - Đã unlock và còn hạn: cho request đi tiếp tới route handler hiện tại

### Unlock flow

1. User submit `POST /gate/unlock` với password
2. Server kiểm tra lockout theo IP
3. Nếu password đúng:
   - reset fail count IP
   - set session unlock với TTL 24h
   - redirect `/`
4. Nếu password sai:
   - tăng fail count theo IP
   - nếu đủ 5 lần: set lockout 15 phút
   - render lại gate page với thông báo lỗi hoặc thời gian còn lại

## Data model (runtime state)

### Session keys

- `site_gate_ok: bool`
- `site_gate_until: int` (Unix timestamp, UTC epoch)

### In-memory lockout state (process-local)

- `FAILED_ATTEMPTS[ip] = int`
- `LOCKED_UNTIL[ip] = int` (Unix timestamp)

> Ghi chú: state này nằm trong process Flask hiện tại, đủ cho deployment hiện tại (single process). Nếu scale multi-worker/multi-instance, cần chuyển sang Redis/shared store.

## Thiết kế module và file

| File | Loại | Mục đích |
|------|------|----------|
| `site_gate.py` | Mới | Chứa logic middleware + lockout + session gate |
| `templates/site_gate.html` | Mới | Form nhập mật khẩu cổng vào (mobile-first) |
| `static/js/site-gate.js` | Mới | Countdown lockout (MM:SS) và disable/enable form |
| `routes_public.py` | Sửa | Thêm endpoint `POST /gate/unlock` |
| `app.py` | Sửa | Init middleware site-gate và config defaults |
| `tests/test_site_gate.py` | Mới | Unit + integration tests cho site-gate |

## Chi tiết thiết kế thành phần

### 1) `site_gate.py`

Các hàm chính:

- `get_client_ip()`
  - Ưu tiên: `CF-Connecting-IP` → `X-Real-IP` → `remote_addr`
- `is_public_protected_path(path: str) -> bool`
  - True cho: `/`, `/api/...`, `/pdf/...`
  - False cho: `/admin/...`, `/static/...`, `/gate/unlock`
- `is_ip_locked(ip, now_ts)`
  - Trả trạng thái lock và số giây còn lại
- `record_failed_attempt(ip, now_ts)`
  - Tăng fail count, đạt ngưỡng 5 thì set lockout 15 phút
- `clear_ip_failures(ip)`
  - Reset fail count + lockout sau khi nhập đúng
- `is_session_unlocked(session, now_ts)`
  - Kiểm tra `site_gate_ok` và `site_gate_until`
- `set_session_unlocked(session, now_ts, ttl_minutes)`
  - Set unlock state theo TTL env
- `init_site_gate(app)`
  - Register `@app.before_request` để enforce policy

### 2) Middleware policy (`before_request`)

Pseudo policy:

1. Nếu path không thuộc protected public scope → return None
2. Lấy IP client
3. Nếu IP đang lock:
   - `/` GET → render `site_gate.html` + `locked_seconds`
   - còn lại → `abort(403)`
4. Nếu session unlocked + chưa hết hạn → return None
5. Nếu chưa unlocked:
   - `/` GET → render `site_gate.html`
   - còn lại → `abort(403)`

### 3) `POST /gate/unlock` trong `routes_public.py`

Input: `password` (form-urlencoded)

Flow:

1. Lấy client IP
2. Nếu đang lock → render gate page với countdown
3. Đọc `SITE_GATE_PASSWORD` từ config
4. So sánh password:
   - Đúng:
     - clear_ip_failures(ip)
     - set session unlock theo `SITE_GATE_TTL_MINUTES`
     - redirect `/`
   - Sai:
     - record_failed_attempt(ip)
     - render gate page với thông báo phù hợp

Response behavior:
- Không trả JSON chi tiết cho API unlock sai
- Không leak thêm metadata nhạy cảm

## UX/UI chi tiết cho `site_gate.html`

- Tiêu đề: `Xác thực truy cập`
- Mô tả: `Vui lòng nhập mật khẩu để tiếp tục`
- Form: 1 password input + submit button
- Error state:
  - Sai mật khẩu: `Mật khẩu không đúng`
  - Lockout: `Bạn đã nhập sai quá 5 lần. Vui lòng thử lại sau MM:SS`
- Lockout state:
  - Disable input + button
  - JS countdown realtime
  - Hết giờ tự enable lại form

Ràng buộc:
- Không load `app.js` public viewer khi ở gate page
- Chỉ khi unlock và vào `index.html` mới load logic viewer

## Error handling

1. `SITE_GATE_PASSWORD` không cấu hình:
   - log warning ở startup
   - fail-closed cho protected public routes (`403` / gate deny)
2. Session hết hạn:
   - clear gate session keys
   - yêu cầu nhập lại
3. In-memory state bị mất sau restart:
   - lockout reset (chấp nhận được cho scope hiện tại)
4. Time handling:
   - dùng Unix timestamp UTC để so sánh nhất quán

## Tương thích với IP restriction hiện có

Hệ thống hiện có đang có IP whitelist middleware trong `app.py`. Site-gate là lớp bảo mật bổ sung ở tầng ứng dụng cho public routes.

Thứ tự đề xuất:
1. IP restriction middleware (nếu bật) xử lý trước
2. Site-gate middleware xử lý tiếp

Khi công ty tắt IP restriction toàn bộ, site-gate vẫn hoạt động độc lập.

## Test plan

### Unit tests

1. `is_public_protected_path()`
   - `/`, `/api/categories`, `/pdf/1` => True
   - `/admin/login`, `/static/css/style.css`, `/gate/unlock` => False
2. Lockout logic
   - Sai 1..4 lần: chưa lock
   - Lần 5: lock 15 phút
   - Trong lock: blocked
   - Hết lock: cho thử lại
3. Session unlock logic
   - Set unlock đúng TTL
   - Hết TTL thì invalidate

### Integration tests (Flask client)

1. `GET /` chưa unlock => 200 + có form gate
2. `GET /api/categories` chưa unlock => 403
3. `POST /gate/unlock` đúng password => session set + redirect
4. Sau unlock, `GET /api/categories` => 200
5. Sai 5 lần cùng IP => lockout active
6. Trong lockout, `POST /gate/unlock` đúng password vẫn không cho
7. Hết lockout (mock time), nhập đúng => cho qua
8. `/admin/login` không bị ảnh hưởng

### Regression

- Chạy full test suite hiện có + `tests/test_site_gate.py`

## Security notes

- So sánh mật khẩu bằng so sánh server-side; không lộ thông tin nhạy cảm ra client
- Chỉ hiển thị thông báo tối thiểu, không trả metadata brute-force cho API
- Không ghi password vào log
- Có thể mở rộng sang shared store (Redis) nếu scale nhiều worker

## Out-of-scope (giai đoạn này)

- Quản lý mật khẩu gate qua Admin UI
- Nhiều mật khẩu theo nhóm
- CAPTCHA
- Shared lockout store (Redis)
