"""
Halaman login SIMKEU.
Membaca sheet PENGGUNA dari Google Sheets dan memvalidasi username + password.
State disimpan di st.session_state (logged_in, current_user, pptk_filter, login_time).
"""

import secrets as pysecrets
import time
from pathlib import Path

import streamlit as st
import pandas as pd

from app_pages import helpers  # noqa: E402
from db import get_conn, SPREADSHEET_URL  # noqa: E402

LOGO_PATH = Path(__file__).resolve().parent.parent / "images" / "logo.png"

# --- Rate limiting login (lihat 10.5 Temuan) ---
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 5 * 60  # 5 menit


def _record_login_failure():
    """Catat kegagalan login dan kunci sementara bila melebihi batas (10.5 Temuan)."""
    count = st.session_state.get("login_fail_count", 0) + 1
    st.session_state.login_fail_count = count
    if count >= MAX_LOGIN_ATTEMPTS:
        st.session_state.login_lockout_until = time.time() + LOGIN_LOCKOUT_SECONDS
        st.error(
            f"Terlalu banyak percobaan login gagal. Coba lagi dalam "
            f"{LOGIN_LOCKOUT_SECONDS // 60} menit."
        )

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.title("Simkeu 2027", text_alignment="right")
    logo_left, logo_center, logo_right = st.columns([1, 2, 1])
    with logo_right:
        st.image(LOGO_PATH, width=340)

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("User Name", placeholder="Masukkan username", key="login_username")
        password = st.text_input("Password", type="password", placeholder="Masukkan password", key="login_password")
        submitted = st.form_submit_button("Masuk", type="primary")

        if submitted:
            username_clean = username.strip().lower()
            password_clean = password.strip()

            if not username_clean or not password_clean:
                st.error("User Name dan password tidak boleh kosong.")
            elif len(username_clean) > 100 or len(password_clean) > 100:
                st.error("Input terlalu panjang.")
            else:
                # Rate limiting: cek apakah masih dalam masa lockout (lihat 10.5 Temuan)
                now = time.time()
                lockout_until = st.session_state.get("login_lockout_until", 0)
                if now < lockout_until:
                    st.error(
                        f"Terlalu banyak percobaan login gagal. Coba lagi dalam "
                        f"{int(lockout_until - now)} detik."
                    )
                else:
                    # Baca data pengguna (cached per ttl)
                    # st.spinner menyembunyikan pesan internal GSheetsServiceAccountClient
                    with st.spinner("Memuat data pengguna…"):
                        try:
                            conn = get_conn()
                            df_pengguna = conn.read(
                                spreadsheet=SPREADSHEET_URL,
                                worksheet="PENGGUNA",
                                ttl=300,
                            )
                        except Exception:
                            df_pengguna = pd.DataFrame()
                            st.error("❌ Tidak dapat membaca sheet PENGGUNA dari Google Sheets.")

                    if df_pengguna is not None and not df_pengguna.empty:
                        if "User Name" in df_pengguna.columns and "Password" in df_pengguna.columns:
                            user_row = df_pengguna[
                                df_pengguna["User Name"].astype(str).str.strip().str.lower() == username_clean
                            ]
                            if not user_row.empty:
                                user = user_row.iloc[0]
                                ok = helpers.verify_password(
                                    password_clean, str(user.get("Password", ""))
                                )
                                if ok:
                                    # Reset hitungan gagal dan buat sesi login
                                    st.session_state.login_fail_count = 0
                                    st.session_state.login_lockout_until = 0
                                    st.session_state.current_user = user.to_dict()
                                    st.session_state.logged_in = True
                                    st.session_state.login_time = now

                                    # Inisialisasi filter PPTK otomatis setelah login
                                    user_peran = str(user.get("Peran", "")).upper()
                                    if user_peran == "PPTK":
                                        nama_login = str(user.get("Nama", "")).strip()
                                        uname_login = str(user.get("User Name", "")).strip()
                                        st.session_state.pptk_filter = (
                                            f"{nama_login} ({uname_login})" if uname_login else nama_login
                                        )
                                    else:
                                        st.session_state.pptk_filter = "Semua PPTK"

                                    st.rerun()
                                else:
                                    st.error("User Name atau password salah.")
                                    _record_login_failure()
                            else:
                                st.error("User Name tidak ditemukan di sheet PENGGUNA.")
                                _record_login_failure()
                        else:
                            st.error("Sheet PENGGUNA tidak memiliki kolom User Name atau Password.")
                    else:
                        st.error("Sheet PENGGUNA kosong atau tidak dapat diakses.")

st.divider()
st.caption("SIMKEU Kecamatan Candisari 2027 · Login via Google Sheets")
