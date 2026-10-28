"""
Halaman login SIMKEU.
Membaca sheet PENGGUNA dari Google Sheets dan memvalidasi username + password.
State disimpan di st.session_state (logged_in, current_user, pptk_filter).
"""

import secrets as pysecrets
from pathlib import Path

import streamlit as st
import pandas as pd

from db import get_conn, SPREADSHEET_URL  # noqa: E402

LOGO_PATH = Path(__file__).resolve().parent.parent / "images" / "logo.png"

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
                # Baca data pengguna (cached per ttl)
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
                            ok = pysecrets.compare_digest(
                                str(user.get("Password", "")).strip(),
                                password_clean,
                            )
                            if ok:
                                st.session_state.current_user = user.to_dict()
                                st.session_state.logged_in = True

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
                        else:
                            st.error("User Name tidak ditemukan di sheet PENGGUNA.")
                    else:
                        st.error("Sheet PENGGUNA tidak memiliki kolom User Name atau Password.")
                else:
                    st.error("Sheet PENGGUNA kosong atau tidak dapat diakses.")

st.divider()
st.caption("SIMKEU Kecamatan Candisari 2027 · Login via Google Sheets")
