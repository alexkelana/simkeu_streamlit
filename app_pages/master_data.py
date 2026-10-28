"""
Halaman Master Data — CRUD Wilayah, Sub Kegiatan, Rekening, Pengguna, dan Audit Log.
Hanya untuk ADMIN / KASUBAG_PEK.
"""

import streamlit as st
import pandas as pd

from app_pages import helpers  # noqa: E402

current_user = st.session_state.get("current_user") or {}

if not helpers.is_manager(current_user.get("Peran", "")):
    st.warning("Menu ini hanya untuk pengelola (ADMIN / KASUBAG_PEK).")
    st.stop()

# Muat master data (cached)
df_wilayah = helpers.load_sheet("MASTER_WILAYAH")
df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")
df_rekening = helpers.load_sheet("MASTER_REKENING")
df_pengguna = helpers.load_sheet("PENGGUNA")

st.header("Master data")
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Wilayah", "Sub Kegiatan", "Rekening", "Pengguna", "Audit Log"],
    on_change="rerun",
)

# ---------- Tab Wilayah ----------
if tab1.open:
    with tab1:
        st.subheader("Data wilayah")
        if not df_wilayah.empty:
            st.dataframe(df_wilayah, hide_index=True, width="stretch")
            st.divider()
            with st.form("form_add_wilayah", border=True):
                st.markdown("**Tambah Wilayah**")
                w_nama = st.text_input("Nama Wilayah", key="w_nama")
                w_kode = st.text_input("Kode Wilayah", key="w_kode")
                if st.form_submit_button("Simpan Wilayah", type="primary"):
                    if helpers.add_master_wilayah(
                        w_nama, w_kode, user=current_user.get("Nama", "Sistem")
                    ):
                        st.success("Wilayah berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("Gagal menambahkan wilayah.")
        else:
            st.info("Belum ada data wilayah.")

# ---------- Tab Sub Kegiatan ----------
if tab2.open:
    with tab2:
        st.subheader("Data sub kegiatan")
        if not df_kegiatan.empty:
            st.dataframe(
                helpers.format_df_rupiah(df_kegiatan),
                hide_index=True,
                width="stretch",
            )
            st.divider()
            with st.form("form_add_kegiatan", border=True):
                st.markdown("**Tambah Sub Kegiatan**")
                k_sub = st.text_input("Kode Sub Kegiatan", key="k_sub")
                k_nama = st.text_input("Nama Kegiatan", key="k_nama")
                k_pagu = st.number_input(
                    "Pagu Awal (Rp)", min_value=0, step=1000000, key="k_pagu"
                )
                if st.form_submit_button("Simpan Kegiatan", type="primary"):
                    if helpers.add_master_kegiatan(
                        k_sub, k_nama, k_pagu, user=current_user.get("Nama", "Sistem")
                    ):
                        st.success("Sub kegiatan berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("Gagal menambahkan sub kegiatan.")
        else:
            st.info("Belum ada data sub kegiatan.")

# ---------- Tab Rekening ----------
if tab3.open:
    with tab3:
        st.subheader("Data rekening belanja")
        if not df_rekening.empty:
            st.dataframe(df_rekening, hide_index=True, width="stretch")
            st.divider()
            col_add, col_edit = st.columns(2)
            with col_add:
                with st.form("form_add_rekening", border=True):
                    st.markdown("**Tambah Rekening**")
                    r_kode = st.text_input("Kode Rekening", key="r_kode")
                    r_uraian = st.text_input("Uraian Rekening", key="r_uraian")
                    if st.form_submit_button("Simpan Rekening", type="primary"):
                        if helpers.add_master_rekening(
                            r_kode, r_uraian, user=current_user.get("Nama", "Sistem")
                        ):
                            st.success("Rekening berhasil ditambahkan.")
                            st.rerun()
                        else:
                            st.error("Gagal menambahkan rekening.")
            with col_edit:
                with st.form("form_edit_rekening", border=True):
                    st.markdown("**Edit / Hapus Rekening**")
                    r_idx = st.number_input(
                        "Indeks Baris", min_value=0, step=1, key="r_idx"
                    )
                    e_kode = st.text_input("Kode Rekening Baru", key="e_kode")
                    e_uraian = st.text_input("Uraian Rekening Baru", key="e_uraian")
                    col_simpan, col_hapus = st.columns(2)
                    with col_simpan:
                        if st.form_submit_button("Simpan Perubahan", type="primary"):
                            if helpers.edit_master_rekening(
                                int(r_idx),
                                e_kode,
                                e_uraian,
                                user=current_user.get("Nama", "Sistem"),
                            ):
                                st.success("Rekening berhasil diupdate.")
                                st.rerun()
                            else:
                                st.error("Gagal mengupdate rekening.")
                    with col_hapus:
                        if st.form_submit_button("Hapus", type="secondary"):
                            if helpers.delete_master_rekening(
                                int(r_idx),
                                user=current_user.get("Nama", "Sistem"),
                            ):
                                st.success("Rekening berhasil dihapus.")
                                st.rerun()
                            else:
                                st.error("Gagal menghapus rekening.")
        else:
            st.info("Belum ada data rekening.")

# ---------- Tab Pengguna ----------
if tab4.open:
    with tab4:
        st.subheader("Data pengguna")
        if not df_pengguna.empty:
            st.dataframe(df_pengguna, hide_index=True, width="stretch")
            st.divider()
            with st.form("form_add_user", border=True):
                st.markdown("**Tambah Pengguna**")
                u_user = st.text_input("User Name", key="u_user")
                u_pass = st.text_input("Password", type="password", key="u_pass")
                u_nama = st.text_input("Nama Lengkap", key="u_nama")
                u_peran = st.selectbox(
                    "Peran", ["ADMIN", "KASUBAG_PEK", "PPTK"], key="u_peran"
                )
                if st.form_submit_button("Simpan Pengguna", type="primary"):
                    if helpers.add_master_user(
                        u_user, u_pass, u_nama, u_peran, user=current_user.get("Nama", "Sistem")
                    ):
                        st.success("Pengguna berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("Gagal menambahkan pengguna.")
        else:
            st.info("Belum ada data pengguna.")

# ---------- Tab Audit Log ----------
if tab5.open:
    with tab5:
        st.subheader("Audit log — riwayat perubahan data")
        df_audit = helpers.load_sheet("AUDIT_LOG")
        if not df_audit.empty:
            df_audit = df_audit.sort_values("WAKTU", ascending=False)
            st.dataframe(df_audit, hide_index=True, width="stretch")
            st.divider()
            if st.button("Refresh Audit Log", key="btn_refresh_audit"):
                helpers.load_sheet.clear()
                st.rerun()
        else:
            st.info("Belum ada riwayat audit log.")
