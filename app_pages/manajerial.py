"""
Halaman Dashboard Manajerial — hanya untuk ADMIN / KASUBAG_PEK.
Berisi analisis keuangan mendalam: realisasi per PPTK, peringatan over budget,
antrian approval, dan peringkat PPTK.
"""

import streamlit as st
import pandas as pd

from app_pages import helpers  # noqa: E402

current_user = st.session_state.get("current_user") or {}

if not helpers.is_manager(current_user.get("Peran", "")):
    st.warning("Halaman ini hanya untuk manajer (ADMIN / KASUBAG_PEK).")
    st.stop()

# Muat data yang diperlukan (cached)
df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")
df_transaksi = helpers.load_sheet("TRANSAKSI")

# Tentukan kolom nominal
nominal_col = "NOMINAL" if "NOMINAL" in df_transaksi.columns else None

st.header("Dashboard Manajerial")
st.caption("Analisis keuangan untuk pengelola (ADMIN / KASUBAG_PEK)")

# --- 1. Ringkasan Realisasi per PPTK ---
st.subheader("Ringkasan Realisasi per PPTK")
if not df_transaksi.empty and nominal_col and "PPTK" in df_transaksi.columns:
    df_transaksi_copy = df_transaksi.copy()
    df_transaksi_copy[nominal_col] = helpers.to_number_series(df_transaksi_copy[nominal_col])
    df_pptk_summary = (
        df_transaksi_copy.groupby("PPTK")[nominal_col]
        .sum().reset_index()
    )
    df_pptk_summary.columns = ["PPTK", "Realisasi"]
    df_pptk_summary = df_pptk_summary.sort_values("Realisasi", ascending=False)
    df_pptk_summary["Realisasi"] = df_pptk_summary["Realisasi"].apply(helpers.format_rupiah)
    st.dataframe(df_pptk_summary, hide_index=True, width="stretch")
else:
    st.info("Belum ada data transaksi untuk ditampilkan per PPTK.")

# --- 2. Peringatan Pagu Melebihi (≥90%) ---
st.divider()
st.subheader("Peringatan Pagu Melebihi (≥90%)")
if not df_kegiatan.empty and not df_transaksi.empty and "Pagu Awal" in df_kegiatan.columns and nominal_col:
    df_kegiatan_copy = df_kegiatan.copy()
    df_kegiatan_copy["Pagu Awal"] = helpers.to_number_series(df_kegiatan_copy["Pagu Awal"])
    df_transaksi_copy = df_transaksi.copy()
    df_transaksi_copy[nominal_col] = helpers.to_number_series(df_transaksi_copy[nominal_col])
    df_transaksi_copy["_kode"] = (
        df_transaksi_copy["SUB KEGIATAN"].astype(str).str.split(" - ").str[0].str.strip()
    )
    realisasi_per_sub = (
        df_transaksi_copy.groupby("_kode")[nominal_col]
        .sum().reset_index()
    )
    realisasi_per_sub.columns = ["Kode Sub Kegiatan", "Realisasi"]
    df_alert = df_kegiatan_copy.merge(realisasi_per_sub, on="Kode Sub Kegiatan", how="left")
    df_alert["Realisasi"] = df_alert["Realisasi"].fillna(0)
    df_alert["% Pakai"] = (df_alert["Realisasi"] / df_alert["Pagu Awal"] * 100).fillna(0)
    df_over = df_alert[df_alert["% Pakai"] >= 90].copy()
    if not df_over.empty:
        df_over_display = df_over[
            ["Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal", "Realisasi", "% Pakai"]
        ].copy()
        df_over_display.columns = ["Kode", "Nama Kegiatan", "Pagu", "Realisasi", "% Pakai"]
        df_over_display["Pagu"] = df_over_display["Pagu"].apply(helpers.format_rupiah)
        df_over_display["Realisasi"] = df_over_display["Realisasi"].apply(helpers.format_rupiah)
        df_over_display["% Pakai"] = df_over_display["% Pakai"].apply(lambda x: f"{x:.1f}%")
        st.warning(f"⚠️ Ditemukan {len(df_over_display)} sub kegiatan yang pagunya telah mencapai ≥90%!")
        st.dataframe(df_over_display, hide_index=True, width="stretch")
    else:
        st.info("✅ Tidak ada sub kegiatan yang melebihi 90% pagu.")
else:
    st.info("Data pagu atau transaksi tidak cukup untuk peringatan over budget.")

# --- 3. Antrian Menunggu Approval ---
st.divider()
st.subheader("Antrian Transaksi Menunggu Approval")
if not df_transaksi.empty and "STATUS" in df_transaksi.columns:
    df_pending = df_transaksi[
        df_transaksi["STATUS"].astype(str).isin(["Draft", "Menunggu Approval"])
    ]
    if not df_pending.empty:
        df_pending_display = df_pending[
            ["NO", "SUB KEGIATAN", "PPTK", "NOMINAL", "TANGGAL PENGAJUAN", "STATUS", "URAIAN"]
        ].copy()
        df_pending_display["NOMINAL"] = df_pending_display["NOMINAL"].apply(helpers.format_rupiah)
        st.dataframe(df_pending_display, hide_index=True, width="stretch")
        st.subheader("Aksi approval")
        col_app1, col_app2 = st.columns(2)
        with col_app1:
            app_no = st.number_input("Nomor Transaksi", min_value=1, step=1, key="app_no")
        with col_app2:
            app_aksi = st.selectbox(
                "Aksi", ["Setujui", "Tolak", "Edit", "Hapus", "Cetak SPJ"], key="app_aksi"
            )

        if app_aksi in ("Setujui", "Tolak"):
            if st.button(f"{app_aksi} Transaksi", type="primary", key="btn_approval"):
                pptk_nama = current_user.get("Nama", "Admin")
                status_baru = "Disetujui" if app_aksi == "Setujui" else "Ditolak"
                ok = helpers.update_transaksi_status(int(app_no), status_baru, pptk_nama)
                if ok:
                    st.success(f"Transaksi No {app_no} berhasil {status_baru.lower()}.")
                    st.rerun()
                else:
                    st.error("Gagal memproses approval.")

        elif app_aksi == "Edit":
            with st.form("form_edit_dashboard", border=True):
                new_uraian = st.text_input("Uraian baru", key="edit_uraian")
                new_nominal = st.number_input("Nominal baru", min_value=0, step=1000, key="edit_nominal")
                if st.form_submit_button("Simpan Perubahan", type="primary", ):
                    new_data = {"URAIAN": new_uraian, "NOMINAL": new_nominal}
                    ok = helpers.edit_transaksi(int(app_no), new_data)
                    if ok:
                        st.success(f"Transaksi No {app_no} berhasil diupdate.")
                        st.rerun()
                    else:
                        st.error("Gagal mengedit transaksi.")

        elif app_aksi == "Hapus":
            st.warning("⚠️ Aksi ini tidak dapat dibatalkan.")
            konfirmasi = st.checkbox("Saya yakin ingin menghapus transaksi ini.", key="hapus_conf")
            if st.button("Hapus Transaksi", type="secondary", key="btn_hapus"):
                if not konfirmasi:
                    st.error("Centang konfirmasi terlebih dahulu.")
                else:
                    ok = helpers.delete_transaksi(int(app_no))
                    if ok:
                        st.success(f"Transaksi No {app_no} berhasil dihapus.")
                        st.rerun()
                    else:
                        st.error("Gagal menghapus transaksi.")

        elif app_aksi == "Cetak SPJ":
            row = df_transaksi[pd.to_numeric(df_transaksi["NO"], errors="coerce") == int(app_no)]
            if not row.empty:
                r = row.iloc[0]
                st.info(f"SPJ untuk Transaksi No {app_no}")
                if helpers.REPORTLAB_AVAILABLE:
                    spj_bytes = helpers.generate_spj_document(r)
                    st.download_button(
                        label="⬇️ Unduh SPJ (PDF)",
                        data=spj_bytes,
                        file_name=f"SPJ_No{app_no}.pdf",
                        mime="application/pdf",
                        key="dl_spj",
                    )
                else:
                    st.warning("Library reportlab tidak terinstal. Tidak dapat generate PDF.")
            else:
                st.error("Transaksi tidak ditemukan.")
    else:
        st.info("✅ Tidak ada transaksi yang menunggu approval.")
else:
    st.info("Data transaksi tidak tersedia.")

# --- 4. Peringkat PPTK Berdasarkan Realisasi ---
st.divider()
st.subheader("Peringkat PPTK Berdasarkan Realisasi")
if not df_transaksi.empty and nominal_col and "PPTK" in df_transaksi.columns:
    df_transaksi_copy = df_transaksi.copy()
    df_transaksi_copy[nominal_col] = helpers.to_number_series(df_transaksi_copy[nominal_col])
    df_rank = (
        df_transaksi_copy.groupby("PPTK")[nominal_col]
        .sum().reset_index()
    )
    df_rank.columns = ["PPTK", "Total Realisasi"]
    df_rank = df_rank.sort_values("Total Realisasi", ascending=False)
    df_rank["Peringkat"] = range(1, len(df_rank) + 1)
    df_rank["Total Realisasi"] = df_rank["Total Realisasi"].apply(helpers.format_rupiah)
    df_rank = df_rank[["Peringkat", "PPTK", "Total Realisasi"]]
    st.dataframe(df_rank, hide_index=True, width="stretch")
else:
    st.info("Belum ada data PPTK untuk ditampilkan dalam peringkat.")
