"""
SIMKEU Kecamatan Candisari 2027 — Streamlit (terhubung Google Sheets)
Entrypoint dengan st.navigation (Streamlit 1.6x).

Setup bersama di sini dijalankan pada setiap halaman:
- st.set_page_config
- Koneksi Google Sheets (@st.cache_resource)
- State login di st.session_state
- Navigasi halaman via st.navigation

Persiapan:
1. Buat service account di Google Cloud, unduh JSON key.
2. Share spreadsheet ke email service account (minimal Editor).
3. Buat .streamlit/secrets.toml (lihat secrets.toml.example).
4. Jalankan: streamlit run streamlit_app.py
"""

import streamlit as st

from db import get_conn, SPREADSHEET_URL  # noqa: E402

# --- Page config harus panggilan Streamlit pertama ---
st.set_page_config(
    page_title="SIMKEU Kecamatan Candisari 2027",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- State login ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None

# --- Bangun navigasi berdasarkan status login ---
if not st.session_state.logged_in:
    pages = {
        "Masuk": [
            st.Page("app_pages/login.py", title="Masuk", icon=":material/login:", default=True),
        ],
    }
else:
    user = st.session_state.current_user or {}
    peran = str(user.get("Peran", "")).upper()
    is_mgr = peran in ("ADMIN", "KASUBAG_PEK")

    common = [
        st.Page("app_pages/transaksi.py", title="Transaksi", icon=":material/receipt_long:"),
        st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/bar_chart:"),
    ]
    manager_pages = []
    if is_mgr:
        manager_pages = [
            st.Page("app_pages/manajerial.py", title="Manajerial", icon=":material/manage_accounts:"),
            st.Page("app_pages/perubahan_pagu.py", title="Perubahan Pagu", icon=":material/edit:"),
            st.Page("app_pages/master_data.py", title="Master Data", icon=":material/settings:"),
        ]
    pages = {
        "Utama": common,
        "Manajemen": manager_pages,
        "Akun": [
            st.Page("app_pages/logout.py", title="Keluar", icon=":material/logout:"),
        ],
    }

pg = st.navigation(pages)
pg.run()
