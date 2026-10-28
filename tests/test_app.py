"""Unit / integrasi tes untuk SIMKEU Kecamatan Candisari 2027 (AppTest)."""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def _run_app():
    return AppTest.from_file(ROOT / "streamlit_app.py").run(timeout=60)


class TestAppRuns:
    def test_entrypoint_no_exception(self):
        at = _run_app()
        assert not at.exception, f"App error: {at.exception}"

    def test_format_rupiah(self):
        # Impor fungsi murni tanpa menjalankan UI
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import format_rupiah, is_manager

        assert format_rupiah(1000000) == "Rp 1.000.000"
        assert format_rupiah(0) == "Rp 0"
        assert format_rupiah(-500000) == "(Rp 500.000)"
        assert format_rupiah("500,000.00") == "Rp 500.000"
        assert format_rupiah("abc") == "-"
        assert format_rupiah(None) == "-"

    def test_parse_number(self):
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import parse_number

        assert parse_number("500,000.00") == 500000.0
        assert parse_number("50,000,000.00") == 50000000.0
        assert parse_number("1.234.567,89") == 1234567.89
        assert parse_number("1,234,567.89") == 1234567.89
        assert parse_number("") is None
        assert parse_number("abc") is None

    def test_is_manager(self):
        sys.path.insert(0, str(ROOT))
        from app_pages.helpers import is_manager

        assert is_manager("ADMIN") is True
        assert is_manager("KASUBAG_PEK") is True
        assert is_manager("PPTK") is False
        assert is_manager("admin") is True

    def test_login_page_no_exception(self):
        at = AppTest.from_file(ROOT / "app_pages/login.py").run(timeout=60)
        assert not at.exception, f"Login page error: {at.exception}"
