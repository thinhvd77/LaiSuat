"""IP restriction middleware for Flask."""
import os
import logging

from flask import request

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
