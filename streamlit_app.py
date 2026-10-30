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

import time
from datetime import datetime

import streamlit as st

from db import get_conn, SPREADSHEET_URL  # noqa: E402
from app_pages import helpers  # noqa: E402
from app_pages.helpers import menu_visibility  # noqa: E402

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

# --- Session timeout (lihat 10.5 Temuan) ---
SESSION_TIMEOUT_SECONDS = 4 * 60 * 60  # 4 jam
if st.session_state.logged_in:
    login_time = st.session_state.get("login_time")
    if login_time is None:
        st.session_state.login_time = time.time()
    elif time.time() - float(login_time) > SESSION_TIMEOUT_SECONDS:
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.pop("pptk_filter", None)
        st.session_state.pop("login_time", None)
        st.rerun()

# --- Bangun navigasi berdasarkan status login ---
if not st.session_state.logged_in:
    pages = {
        "Masuk": [
            st.Page("app_pages/login.py", title="Masuk", icon=":material/login:", default=True),
        ],
    }

    # Sembunyikan indikator "Running …" bawaan Streamlit di halaman login.
    # Tanpa ini, saat memverifikasi kredensial muncul teks internal seperti
    # "GSheetsServiceAccountClient.read.<locals>._get_as_dataframe(...)".
    # Spinner "Memuat data pengguna…" di login.py tetap tampil sebagai gantinya.
    st.html(
        """
        <style>
        [data-testid="stStatusWidget"] { display: none; }
        </style>
        """
    )
else:
    user = st.session_state.current_user or {}
    peran = str(user.get("Peran", "")).upper()
    menu = menu_visibility(peran)

    # Dashboard selalu menjadi halaman awal setelah login.
    utama = [
        st.Page(
            "app_pages/dashboard.py",
            title="Dashboard",
            icon=":material/bar_chart:",
            default=True,
        ),
    ]
    # ADMIN tidak boleh melihat menu Transaksi (hanya Dashboard + Master Data).
    if menu["transaksi"]:
        utama.append(
            st.Page(
                "app_pages/transaksi.py",
                title="Transaksi",
                icon=":material/receipt_long:",
            )
        )

    # Menu manajemen berbeda per peran: Kasubag (antrian approval),
    # PPTK (pengajuan pagu), ADMIN (master data).
    manajemen = []
    if menu["manajerial"]:
        manajemen.append(
            st.Page(
                "app_pages/manajerial.py",
                title="Manajerial",
                icon=":material/manage_accounts:",
            )
        )
    if menu["pengajuan_pagu"]:
        manajemen.append(
            st.Page(
                "app_pages/perubahan_pagu.py",
                title="Pengajuan Pagu",
                icon=":material/edit:",
            )
        )
    if menu["master_data"]:
        manajemen.append(
            st.Page(
                "app_pages/master_data.py",
                title="Master Data",
                icon=":material/settings:",
            )
        )

    pages = {"Utama": utama}
    if manajemen:
        pages["Manajemen"] = manajemen
    # Keluar tidak lagi di sidebar; tombolnya ada di header area utama.

# --- Header aplikasi: sapaan, info user, dan tombol Keluar (sticky di area utama) ---
if st.session_state.logged_in:
    # Inisialisasi pengaturan Telegram untuk semua user (dari file JSON)
    # agar nilai OFF yang disetel admin di Dashboard berlaku juga untuk
    # PPTK dan Kasubag saat membuka halaman Transaksi.
    if "telegram_enabled" not in st.session_state:
        st.session_state.telegram_enabled = helpers.load_telegram_setting()

    user = st.session_state.current_user or {}
    nama = user.get("Nama") or "-"
    peran = str(user.get("Peran", "")).replace("_", " ")
    uname = user.get("User Name") or user.get("username") or "-"

    jam = datetime.now().hour
    if 4 <= jam < 11:
        sapaan = "Selamat pagi"
    elif 11 <= jam < 15:
        sapaan = "Selamat siang"
    elif 15 <= jam < 18:
        sapaan = "Selamat sore"
    else:
        sapaan = "Selamat malam"

    BULAN_ID = (
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    )
    sekarang = datetime.now()
    tanggal = f"{sekarang.day} {BULAN_ID[sekarang.month - 1]} {sekarang.year}"

    # Warna header mengikuti tema aktif agar konten tidak tembus saat menempel di atas.
    tema = getattr(st.context.theme, "type", None) or "dark"
    warna_bg = st.get_option(f"theme.{tema}.backgroundColor") or st.get_option(
        "theme.backgroundColor"
    )
    warna_border = (
        st.get_option(f"theme.{tema}.borderColor")
        or st.get_option("theme.borderColor")
        or "transparent"
    )

    # Sticky dipasang pada wrapper pembungkus (bukan elemen header itu sendiri),
    # karena wrapper itulah yang setinggi konten induk sehingga bisa menempel saat scroll.
    # top: 3.75rem = tinggi toolbar Streamlit, agar header tidak tertutup toolbar.
    st.html(
        f"""
        <style>
        div[data-testid="stLayoutWrapper"]:has(> .st-key-app_header) {{
            position: sticky;
            top: 3.75rem;
            z-index: 999;
            background-color: {warna_bg};
            border-bottom: 1px solid {warna_border};
            padding: 0.75rem 0;
            margin-bottom: 1.25rem;
        }}
        @media (max-width: 640px) {{
            div[data-testid="stLayoutWrapper"]:has(> .st-key-app_header) {{
                padding: 0.5rem 0;
                margin-bottom: 0.75rem;
            }}
            div[data-testid="stLayoutWrapper"]:has(> .st-key-app_header) h1 {{
                font-size: 1.5rem;
                line-height: 1.3;
            }}
        }}
        </style>
        """
    )

    with st.container(key="app_header", horizontal=True, vertical_alignment="center"):
        with st.container(width="content"):
            st.title(f"{sapaan}, {nama}", width="content")
            st.caption(
                f"{peran} · User: {uname} · {tanggal}",
                width="content",
            )
        st.space("stretch")
        if st.button(
            "Keluar",
            type="tertiary",
            key="header_logout",
            icon=":material/logout:",
        ):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            st.session_state.pop("pptk_filter", None)
            st.session_state.pop("login_time", None)
            st.rerun()

pg = st.navigation(pages)
pg.run()
