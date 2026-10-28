"""
Konfigurasi dan koneksi bersama untuk SIMKEU.
Tidak memanggil st.set_page_config / st.navigation (hanya di entrypoint).
Safe diimpor oleh semua halaman di pages/.
"""

from streamlit_gsheets import GSheetsConnection
import streamlit as st

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1MMi0ABevTztyCfuzje6JLqNFeYt9octD_GKA0R2Xic8/edit"


def get_conn():
    """st.connection() sudah di-cache internal — jangan wrap dengan @st.cache_resource."""
    return st.connection("gsheets", type=GSheetsConnection)
