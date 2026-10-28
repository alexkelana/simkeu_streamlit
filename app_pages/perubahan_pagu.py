"""
Halaman Perubahan Pagu — hanya untuk ADMIN / KASUBAG_PEK.
"""

import streamlit as st
import pandas as pd
from datetime import date

from app_pages import helpers  # noqa: E402

current_user = st.session_state.get("current_user") or {}

if not helpers.is_manager(current_user.get("Peran", "")):
    st.warning("Menu ini hanya untuk pengelola (ADMIN / KASUBAG_PEK).")
    st.stop()

st.header("Perubahan pagu")

df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")

st.subheader("Ajukan perubahan pagu baru")
with st.form("form_perubahan_pagu", border=True):
    subkode_opts = (
        df_kegiatan["Kode Sub Kegiatan"].dropna().tolist()
        if not df_kegiatan.empty and "Kode Sub Kegiatan" in df_kegiatan.columns
        else ["-"]
    )
    subkode = st.selectbox(
        "Sub Kegiatan",
        options=subkode_opts,
        format_func=lambda x: helpers.get_subkegiatan_full(x, df_kegiatan)
        if not df_kegiatan.empty else x,
        key="pp_subkode",
    )
    pagu_baru = st.number_input("Pagu Baru (Rp)", min_value=0, step=1000000, key="pp_pagu")
    alasan = st.text_area("Alasan Perubahan", height=100, key="pp_alasan")
    if st.form_submit_button("Ajukan Perubahan", type="primary", ):
        if subkode == "-" or pagu_baru <= 0:
            st.error("Sub Kegiatan dan Pagu Baru wajib diisi dengan benar.")
        else:
            new_row = {
                "SUB KEGIATAN": subkode,
                "PAGU BARU": pagu_baru,
                "ALASAN": alasan,
                "DIAJUKAN OLEH": current_user.get("Nama", "Admin"),
                "TANGGAL AJUAN": date.today().strftime("%d/%m/%Y"),
                "STATUS": "Menunggu Approval",
            }
            df_p = helpers.load_sheet("PERUBAHAN_PAGU")
            if df_p.empty:
                df_p = pd.DataFrame(columns=list(new_row.keys()))
            updated = pd.concat([df_p, pd.DataFrame([new_row])], ignore_index=True)
            ok = helpers.update_sheet_data("PERUBAHAN_PAGU", updated)
            if ok:
                st.success("Perubahan pagu berhasil diajukan. Menunggu approval.")
                st.rerun()
            else:
                st.error("Gagal mengajukan perubahan pagu.")

st.divider()
st.subheader("Daftar perubahan pagu")
df_perubahan = helpers.load_sheet("PERUBAHAN_PAGU")
if not df_perubahan.empty:
    st.dataframe(helpers.format_df_rupiah(df_perubahan), hide_index=True, width="stretch")
else:
    st.info("Belum ada data perubahan pagu.")
