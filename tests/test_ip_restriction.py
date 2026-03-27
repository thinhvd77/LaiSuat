"""Tests cho IP restriction middleware."""
import pytest


class TestLoadIPWhitelist:
    """Test đọc file whitelist."""

    def test_load_valid_file(self, tmp_path):
        """Đọc file với IP hợp lệ."""
        from middleware import load_ip_whitelist

        whitelist = tmp_path / "whitelist.txt"
        whitelist.write_text("113.161.1.1\n118.70.2.2\n")

        ips = load_ip_whitelist(str(whitelist))

        assert ips == {"113.161.1.1", "118.70.2.2"}

    def test_ignore_comments_and_blank_lines(self, tmp_path):
        """Bỏ qua comment và dòng trống."""
        from middleware import load_ip_whitelist

        whitelist = tmp_path / "whitelist.txt"
        whitelist.write_text("# Comment\n113.161.1.1\n\n# Another\n118.70.2.2\n")

        ips = load_ip_whitelist(str(whitelist))

        assert ips == {"113.161.1.1", "118.70.2.2"}

    def test_missing_file_returns_empty(self, tmp_path):
        """File không tồn tại trả về set rỗng."""
        from middleware import load_ip_whitelist

        ips = load_ip_whitelist(str(tmp_path / "nonexistent.txt"))

        assert ips == set()

    def test_strips_whitespace(self, tmp_path):
        """Strip whitespace từ IP."""
        from middleware import load_ip_whitelist

        whitelist = tmp_path / "whitelist.txt"
        whitelist.write_text("  113.161.1.1  \n\t118.70.2.2\t\n")

        ips = load_ip_whitelist(str(whitelist))

        assert ips == {"113.161.1.1", "118.70.2.2"}
