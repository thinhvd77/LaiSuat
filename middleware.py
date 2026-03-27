"""IP restriction middleware for Flask."""
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
