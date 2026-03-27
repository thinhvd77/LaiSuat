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


class TestGetClientIP:
    """Test hàm get_client_ip()."""

    def test_cf_connecting_ip_priority(self, app):
        """CF-Connecting-IP được ưu tiên."""
        from middleware import get_client_ip

        with app.test_request_context(
            headers={
                "CF-Connecting-IP": "1.1.1.1",
                "X-Real-IP": "2.2.2.2",
            }
        ):
            assert get_client_ip() == "1.1.1.1"

    def test_x_real_ip_fallback(self, app):
        """X-Real-IP khi không có CF header."""
        from middleware import get_client_ip

        with app.test_request_context(headers={"X-Real-IP": "2.2.2.2"}):
            assert get_client_ip() == "2.2.2.2"

    def test_remote_addr_last_resort(self, app):
        """remote_addr khi không có header nào."""
        from middleware import get_client_ip

        with app.test_request_context(environ_base={"REMOTE_ADDR": "3.3.3.3"}):
            assert get_client_ip() == "3.3.3.3"

    def test_strips_whitespace_from_headers(self, app):
        """Strip whitespace từ header values."""
        from middleware import get_client_ip

        with app.test_request_context(headers={"CF-Connecting-IP": "  1.1.1.1  "}):
            assert get_client_ip() == "1.1.1.1"
