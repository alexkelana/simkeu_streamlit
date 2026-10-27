"""Unit tests untuk SIMKEU Kecamatan Candisari 2027."""

import sys
import os
from unittest.mock import MagicMock


class FakeSessionState(dict):
    """session_state palsu yang mendukung akses atribut dan item."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return None

    def __setattr__(self, key, value):
        self[key] = value

    def __contains__(self, key):
        return True


# ---- Mock streamlit dan dependensi eksternal sebelum impor app ----
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit_gsheets"] = MagicMock()

st_mock = sys.modules["streamlit"]
st_mock.session_state = FakeSessionState()
st_mock.session_state["logged_in"] = True
st_mock.session_state["current_user"] = {
    "nama": "Test User",
    "peran": "ADMIN",
    "user_name": "testuser",
}
st_mock.secrets = {}

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Impor app dengan semua mock sudah aktif
from app import format_rupiah, is_manager  # noqa: E402


class TestFormatRupiah:
    def test_format_rupiah_basic(self):
        assert format_rupiah(1000000) == "Rp 1,000,000"

    def test_format_rupiah_zero(self):
        assert format_rupiah(0) == "Rp 0"

    def test_format_rupiah_negative(self):
        assert format_rupiah(-500000) == "(Rp 500,000)"

    def test_format_rupiah_invalid(self):
        assert format_rupiah("abc") == "-"

    def test_format_rupiah_none(self):
        assert format_rupiah(None) == "-"


class TestIsManager:
    def test_admin_is_manager(self):
        assert is_manager("ADMIN") is True

    def test_kasubag_pek_is_manager(self):
        assert is_manager("KASUBAG_PEK") is True

    def test_pptk_not_manager(self):
        assert is_manager("PPTK") is False

    def test_lowercase_admin(self):
        assert is_manager("admin") is True
