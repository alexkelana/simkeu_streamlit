"""
Halaman Transaksi — input transaksi baru + daftar transaksi dengan filter.
"""

import streamlit as st
import pandas as pd
from datetime import date

from app_pages import helpers  # noqa: E402

st.header("Input transaksi")

# Tampilkan status simpan yang disimpan di session_state (setelah rerun)
if "simpan_status" in st.session_state:
    status = st.session_state.pop("simpan_status")
    if status["success"]:
        st.success(status["message"])
        if status.get("telegram_ok"):
            st.info("Notifikasi Telegram terkirim.")
        else:
            st.warning("Transaksi tersimpan, tapi notifikasi Telegram gagal.")
    else:
        st.error(status["message"])

# Muat master data (cached)
df_rekening = helpers.load_sheet("MASTER_REKENING")
df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")

rekening_opts = []
if not df_rekening.empty and "Kode Rekening" in df_rekening.columns:
    rekening_opts = df_rekening["Kode Rekening"].dropna().tolist()

sub_opts = []
if not df_kegiatan.empty and "Kode Sub Kegiatan" in df_kegiatan.columns:
    sub_opts = df_kegiatan["Kode Sub Kegiatan"].dropna().tolist()

with st.form("form_transaksi", border=True):
    tgl = st.date_input("Tanggal Pengajuan", value=date.today(), key="tx_tanggal")

    subkegiatan = st.selectbox(
        "Sub Kegiatan",
        options=sub_opts if sub_opts else ["-"],
        format_func=lambda x: helpers.get_subkegiatan_full(x, df_kegiatan),
        key="tx_subkegiatan",
    )

    rekening = st.selectbox(
        "Kode Rekening Belanja",
        options=rekening_opts if rekening_opts else ["-"],
        format_func=lambda x: helpers.get_rekening_full(x, df_rekening),
        key="tx_rekening",
    )

    pengelompokan = st.text_input("Pengelompokan Belanja (#)", key="tx_pengelompokan")
    jenis = st.selectbox("Jenis Transaksi", ["UP/GU", "LS"], key="tx_jenis")
    nominal = st.number_input("Nominal (Rp)", min_value=0, step=1000, key="tx_nominal")
    uraian = st.text_area("Uraian", height=100, key="tx_uraian")
    bukti = st.text_input("Bukti Dukung SPJ (tautan / nomor)", key="tx_bukti")

    if st.form_submit_button("Simpan Transaksi", type="primary"):
        if nominal <= 0 or subkegiatan == "-" or rekening == "-":
            st.error("Sub Kegiatan, Kode Rekening, dan Nominal wajib diisi dengan benar.")
        else:
            user = st.session_state.get("current_user") or {}
            uname = user.get("User Name") or user.get("username") or ""
            pptk = f"{user.get('Nama', '')} ({uname})"
            new_data = {
                "SUB KEGIATAN": helpers.get_subkegiatan_full(subkegiatan, df_kegiatan),
                "KODE REKENING BELANJA": rekening,
                "PENGELOMPOKAN BELANJA (#)": pengelompokan or "",
                "URAIAN": uraian or "",
                "JENIS TRANSAKSI (UP/GU/LS)": jenis,
                "NOMINAL": nominal,
                "TANGGAL PENGAJUAN": tgl.strftime("%d/%m/%Y"),
                "BUKTI DUKUNG SPJ": bukti or "",
                "PPTK": pptk,
            }
            success, result = helpers.append_transaksi(
                new_data, user=user.get("Nama", "Sistem")
            )
            if success:
                pesan = (
                    f"📌 Transaksi Baru SIMKEU\n"
                    f"No: {result}\n"
                    f"PPTK: {pptk}\n"
                    f"Sub Kegiatan: {new_data['SUB KEGIATAN']}\n"
                    f"Rekening: {rekening}\n"
                    f"Jenis: {jenis}\n"
                    f"Nominal: {helpers.format_rupiah(nominal)}\n"
                    f"Tanggal: {new_data['TANGGAL PENGAJUAN']}\n"
                    f"Uraian: {uraian or '-'}"
                )
                telegram_ok = helpers.send_telegram(pesan)
                st.session_state.simpan_status = {
                    "success": True,
                    "message": f"✅ Transaksi berhasil disimpan. Nomor: {result}",
                    "telegram_ok": telegram_ok,
                }
                st.rerun()
            else:
                st.session_state.simpan_status = {
                    "success": False,
                    "message": f"❌ Gagal menyimpan: {result}",
                }
                st.rerun()

st.divider()
st.subheader("Daftar transaksi")

df_transaksi = helpers.load_sheet("TRANSAKSI")

if not df_transaksi.empty:
    # Inisialisasi default filter agar tersedia saat expander collapsed
    filter_tanggal = ""
    filter_sub = ""
    filter_rek = ""
    filter_status = "Semua"

    exp = st.expander("🔍 Filter & pencarian transaksi", on_change="rerun")
    if exp.open:
        with exp:
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                filter_tanggal = st.text_input(
                    "Tanggal (DD/MM/YYYY)", placeholder="contoh: 01/01/2027", key="f_tgl"
                )
            with f_col2:
                filter_sub = st.text_input(
                    "Sub Kegiatan", placeholder="kata kunci...", key="f_sub"
                )
            with f_col3:
                filter_rek = st.text_input(
                    "Kode Rekening", placeholder="kata kunci...", key="f_rek"
                )
            with f_col4:
                filter_status = st.selectbox(
                    "Status",
                    ["Semua", "Draft", "Diajuan", "Disetujui", "Ditolak"],
                    key="f_status",
                )

    df_show = df_transaksi.copy()
    if "STATUS" not in df_show.columns:
        df_show["STATUS"] = "Draft"

    if filter_tanggal:
        df_show = df_show[
            df_show["TANGGAL PENGAJUAN"].astype(str).str.contains(
                filter_tanggal, case=False, na=False
            )
        ]
    if filter_sub:
        df_show = df_show[
            df_show["SUB KEGIATAN"].astype(str).str.contains(
                filter_sub, case=False, na=False
            )
        ]
    if filter_rek:
        df_show = df_show[
            df_show["KODE REKENING BELANJA"].astype(str).str.contains(
                filter_rek, case=False, na=False
            )
        ]
    if filter_status != "Semua":
        df_show = df_show[df_show["STATUS"] == filter_status]

    # Filter PPTK (untuk user PPTK)
    pptk_filter = st.session_state.get("pptk_filter")
    if pptk_filter and pptk_filter != "Semua PPTK":
        df_show = df_show[df_show["PPTK"].astype(str) == pptk_filter]

    st.caption(f"Menampilkan {len(df_show)} dari {len(df_transaksi)} transaksi")
    st.dataframe(
        helpers.format_df_rupiah(df_show),
        hide_index=True,
        width="stretch",
    )
else:
    st.info("Belum ada transaksi.")
