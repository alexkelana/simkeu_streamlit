"""
Halaman Manajerial — hanya untuk KASUBAG_PEK.
Berisi antrian yang membutuhkan tindakan: approval transaksi dan
approval pengajuan perubahan pagu. Informasi tanpa aksi ada di Dashboard.
"""

import streamlit as st
import pandas as pd

from app_pages import helpers  # noqa: E402

current_user = st.session_state.get("current_user") or {}
user_peran = str(current_user.get("Peran", "")).upper()

if user_peran != "KASUBAG_PEK":
    st.warning("Halaman ini hanya untuk KASUBAG_PEK.")
    st.stop()

# Muat data yang diperlukan (cached)
df_transaksi = helpers.load_sheet("TRANSAKSI")

st.header("Manajerial")
st.caption("Antrian yang membutuhkan tindakan.")

# --- 1. Antrian Menunggu Approval ---
st.subheader("Antrian Transaksi Menunggu Approval")
# Status "Menunggu Approval" tidak lagi dihasilkan oleh alur apa pun
# (fitur pengajuan perubahan pagu oleh PPTK telah dihapus), jadi antrian
# di sini hanya menampilkan status Draft (lihat 10.2 Temuan).
if not df_transaksi.empty and "STATUS" in df_transaksi.columns:
    df_pending = df_transaksi[
        df_transaksi["STATUS"].astype(str).str.strip() == "Draft"
    ]
    if not df_pending.empty:
        df_pending_display = df_pending[
            ["NO", "SUB KEGIATAN", "PPTK", "NOMINAL", "TANGGAL PENGAJUAN", "STATUS", "URAIAN"]
        ].copy()
        if "ALASAN_PENOLAKAN" in df_pending.columns:
            df_pending_display["ALASAN_PENOLAKAN"] = df_pending["ALASAN_PENOLAKAN"].fillna("")
        df_pending_display["NOMINAL"] = df_pending_display["NOMINAL"].apply(helpers.format_rupiah)
        st.dataframe(df_pending_display, hide_index=True, width="stretch")

        st.subheader("Aksi approval")
        col_app1, col_app2 = st.columns(2)
        with col_app1:
            app_aksi = st.selectbox(
                "Aksi", ["Setujui", "Tolak", "Cetak SPJ"], key="app_aksi"
            )
        with col_app2:
            alasan = ""
            # Pilihan transaksi disesuaikan aksi: Setujui/Tolak hanya Draft,
            # Cetak SPJ bisa semua transaksi.
            if app_aksi == "Cetak SPJ":
                no_options = df_transaksi
            else:
                no_options = df_pending
            app_no = None
            if not no_options.empty and "NO" in no_options.columns:
                no_map = {}
                for _, r in no_options.iterrows():
                    no_val = r.get("NO")
                    label = (
                        f"No {no_val} · {r.get('PPTK','-')} · "
                        f"{helpers.format_rupiah(r.get('NOMINAL',0))} · "
                        f"{str(r.get('SUB KEGIATAN','-'))}"
                    )
                    no_map[label] = no_val
                app_no_label = st.selectbox(
                    "Transaksi", options=list(no_map.keys()), key="app_no_label"
                )
                app_no = int(no_map[app_no_label])
            else:
                st.info("Tidak ada transaksi yang tersedia untuk aksi ini.")

            if app_aksi == "Tolak":
                alasan = st.text_area("Alasan penolakan", key="app_alasan")

        if app_aksi in ("Setujui", "Tolak") and app_no is not None:
            if st.button(f"{app_aksi} Transaksi", type="primary", key="btn_approval"):
                if app_aksi == "Tolak" and not alasan.strip():
                    st.error("Alasan penolakan wajib diisi.")
                else:
                    pptk_nama = current_user.get("Nama", "Sistem")
                    status_baru = "Disetujui" if app_aksi == "Setujui" else "Ditolak"
                    with st.spinner(f"Memproses {status_baru.lower()}…"):
                        ok = helpers.update_transaksi_status(
                            app_no, status_baru, pptk_nama, alasan=alasan
                        )
                    if ok:
                        if app_aksi == "Tolak":
                            row = df_transaksi[
                                pd.to_numeric(df_transaksi["NO"], errors="coerce") == app_no
                            ]
                            if not row.empty:
                                with st.spinner("Mengirim notifikasi penolakan…"):
                                    helpers.kirim_notifikasi_penolakan(row.iloc[0], alasan)
                        st.toast(
                            f"✅ Transaksi No {app_no} berhasil {status_baru.lower()}.",
                            icon="✅",
                        )
                        st.success(
                            f"Transaksi No {app_no} berhasil {status_baru.lower()}."
                        )
                        # Reset form aksi ke state awal
                        helpers.reset_form_keys(
                            "app_aksi", "app_no_label", "app_alasan",
                        )
                        st.rerun()
                    else:
                        st.toast("❌ Gagal memproses approval.", icon="❌")
                        st.error("Gagal memproses approval.")

        elif app_aksi == "Cetak SPJ" and app_no is not None:
            row = df_transaksi[
                pd.to_numeric(df_transaksi["NO"], errors="coerce") == app_no
            ]
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

# --- 2. Perubahan Pagu (ganti pengajuan pagu PPTK) ---
st.divider()
st.subheader("Perubahan Pagu")
st.caption(
    "Ubah pagu sub kegiatan secara langsung. Nominal positif = penambahan, "
    "negatif = pengurangan. Sisa Pagu dihitung otomatis dari Pagu Akhir "
    "+ Perubahan Pagu − Realisasi."
)

df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")

if not df_kegiatan.empty and "Kode Sub Kegiatan" in df_kegiatan.columns:
    sub_opts = df_kegiatan["Kode Sub Kegiatan"].dropna().tolist()

    # Dropdown di luar form agar perubahan langsung trigger rerun,
    # caption pagu ikut berubah tanpa perlu submit form.
    selected_subkode = st.selectbox(
        "Pilih Sub Kegiatan",
        options=sub_opts,
        format_func=lambda x: helpers.get_subkegiatan_full(x, df_kegiatan),
        key="mp_subkode",
    )

    # Tampilkan info pagu sebagai referensi (di luar form agar berubah segera
    # saat dropdown diganti). Selalu tampil walaupun data belum tersedia (nilai Rp 0).
    pagu_awal = 0
    pagu_akhir = 0
    perubahan_lama = 0
    sisa_lama = 0
    if selected_subkode and selected_subkode != "-":
        row_ref = df_kegiatan[
            df_kegiatan["Kode Sub Kegiatan"].astype(str).str.strip() == str(selected_subkode).strip()
        ]
        if not row_ref.empty:
            r = row_ref.iloc[0]
            pagu_awal = helpers.parse_number(r.get("Pagu Awal", 0)) or 0
            pagu_akhir = helpers.parse_number(r.get("Pagu Akhir", 0)) or 0
            perubahan_lama = helpers.parse_number(r.get("Perubahan Pagu", 0)) or 0
            sisa_lama = helpers.parse_number(r.get("Sisa Pagu", 0)) or 0
    st.caption(
        f"Pagu Awal: {helpers.format_rupiah(pagu_awal)} · "
        f"Pagu Akhir: {helpers.format_rupiah(pagu_akhir)} · "
        f"Perubahan Pagu: {helpers.format_rupiah(perubahan_lama)} · "
        f"Sisa Pagu: {helpers.format_rupiah(sisa_lama)}"
    )

    with st.container(border=True):
        perubahan = st.number_input(
            "Perubahan Pagu (Rp)",
            step=100000.0,
            format="%.2f",
            key="mp_perubahan",
            help="Isi angka positif untuk penambahan, negatif untuk pengurangan.",
        )
        st.caption(f"Nilai terbaca: {helpers.format_rupiah(perubahan)}")

        konf_mp = st.checkbox("Saya yakin ingin mencatat perubahan pagu ini.", key="mp_conf")
        if st.button("Catat Perubahan Pagu", type="primary", key="btn_catat_mp"):
            if not konf_mp:
                st.error("Centang konfirmasi terlebih dahulu.")
            elif not selected_subkode or selected_subkode == "-":
                st.error("Pilih Sub Kegiatan terlebih dahulu.")
            else:
                user = current_user.get("Nama", "Sistem")
                with st.spinner("Mencatat perubahan pagu…"):
                    ok = helpers.update_master_subkegiatan_perubahan_pagu(
                        selected_subkode, float(perubahan), user=user
                    )
                if ok:
                    st.toast("✅ Perubahan pagu berhasil dicatat.", icon="✅")
                    st.success(
                        f"Perubahan pagu sub kegiatan {selected_subkode} sebesar "
                        f"{helpers.format_rupiah(perubahan)} berhasil dicatat."
                    )
                    helpers.reset_form_keys(
                        "mp_perubahan", "mp_conf",
                    )
                    st.rerun()
                else:
                    st.toast("❌ Gagal mencatat perubahan pagu.", icon="❌")
                    st.error("Gagal mencatat perubahan pagu.")
else:
    st.info("Data master sub kegiatan tidak tersedia.")
