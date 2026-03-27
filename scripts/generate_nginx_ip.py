#!/usr/bin/env python3
"""Generate Nginx IP whitelist config từ ip_whitelist.txt.

Usage:
    python scripts/generate_nginx_ip.py

Output:
    nginx/ip_whitelist.conf
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
WHITELIST_FILE = os.path.join(PROJECT_ROOT, "ip_whitelist.txt")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "nginx", "ip_whitelist.conf")


def load_ips(filepath):
    """Đọc danh sách IP từ file."""
    ips = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ips.append(line)
    return ips


def generate_nginx_config(ips):
    """Tạo nội dung Nginx config."""
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
    print()
    print("Next steps:")
    print("  1. Copy nginx/ip_whitelist.conf to /etc/nginx/snippets/")
    print("  2. Run: sudo nginx -t && sudo nginx -s reload")


if __name__ == "__main__":
    main()
