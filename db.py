"""
Konfigurasi dan koneksi bersama untuk SIMKEU.
Tidak memanggil st.set_page_config / st.navigation (hanya di entrypoint).
Safe diimpor oleh semua halaman di pages/.
"""

from streamlit_gsheets import GSheetsConnection
import streamlit as st

# SPREADSHEET_URL diambil dari st.secrets ([connections.gsheets] spreadsheet)
# agar kredensial/koneksi tidak hardcode di kode sumber (lihat 10.5 Temuan).
# Fallback ke URL lama bila secrets belum diisi (development lokal tanpa secrets).
try:
    _SECRET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
except Exception:
    _SECRET_URL = ""

SPREADSHEET_URL = _SECRET_URL or "https://docs.google.com/spreadsheets/d/1MMi0ABevTztyCfuzje6JLqNFeYt9octD_GKA0R2Xic8/edit"


def get_conn():
    """st.connection() sudah di-cache internal — jangan wrap dengan @st.cache_resource."""
    return st.connection("gsheets", type=GSheetsConnection)
