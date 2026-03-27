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
