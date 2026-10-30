"""
Halaman Transaksi — input transaksi baru + daftar transaksi dengan filter.
"""

import streamlit as st
import pandas as pd
from datetime import date

from app_pages import helpers  # noqa: E402

current_user = st.session_state.get("current_user") or {}
user_peran = str(current_user.get("Peran", "")).upper()
is_pptk = user_peran not in ("ADMIN", "KASUBAG_PEK")

# Muat master data (cached) — selalu dimuat (dipakai di section export untuk manajer)
df_rekening = helpers.load_sheet("MASTER_REKENING")
df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")
df_transaksi = helpers.load_sheet("TRANSAKSI")

# Form input transaksi hanya untuk PPTK. ADMIN / KASUBAG_PEK hanya lihat daftar.
if is_pptk:
    st.header("Input transaksi")

    # Tampilkan status simpan yang disimpan di session_state (setelah rerun)
    if "simpan_status" in st.session_state:
        status = st.session_state.pop("simpan_status")
        if status["success"]:
            st.success(status["message"])
            # Tampilkan status Telegram hanya saat fitur benar-benar diaktifkan.
            # Saat toggle OFF, kiriman dilewati dan tidak perlu menunjukkan pesan gagal.
            if st.session_state.get("telegram_enabled", True):
                if status.get("telegram_ok"):
                    st.info("Notifikasi Telegram terkirim.")
                else:
                    st.warning("Transaksi tersimpan, tapi notifikasi Telegram gagal.")
        else:
            st.error(status["message"])

    rekening_opts = []
    if not df_rekening.empty and "Kode Rekening" in df_rekening.columns:
        rekening_opts = df_rekening["Kode Rekening"].dropna().tolist()

    sub_opts = []
    if not df_kegiatan.empty and "Kode Sub Kegiatan" in df_kegiatan.columns:
        sub_opts = df_kegiatan["Kode Sub Kegiatan"].dropna().tolist()

    # Sub Kegiatan di luar form agar pemilihan langsung trigger rerun,
    # dan info Pagu Awal / Sisa Pagu ikut terupdate tanpa perlu submit form.
    subkegiatan = st.selectbox(
        "Sub Kegiatan",
        options=sub_opts if sub_opts else ["-"],
        format_func=lambda x: helpers.get_subkegiatan_full(x, df_kegiatan),
        key="tx_subkegiatan",
    )

    # Info Sisa Pagu & Pagu Awal di bawah dropdown Sub Kegiatan
    sg_kode = ""
    if not df_kegiatan.empty and "Kode Sub Kegiatan" in df_kegiatan.columns:
        sg_kode = str(subkegiatan).split(" - ")[0] if " - " in str(subkegiatan) else str(subkegiatan)
    pagu_awal_val = helpers.get_pagu_awal(sg_kode, df_kegiatan)
    sisa_pagu_val = helpers.get_sisa_pagu(sg_kode, df_kegiatan, df_transaksi)
    st.caption(f"Pagu Awal: {helpers.format_rupiah(pagu_awal_val)} · Sisa Pagu: {helpers.format_rupiah(sisa_pagu_val)}")

    with st.form("form_transaksi", border=True):
        tgl = st.date_input("Tanggal Pengajuan", value=date.today(), key="tx_tanggal")

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

        if st.form_submit_button("Ajukan Transaksi", type="primary"):
            if (
                nominal <= 0
                or subkegiatan == "-"
                or rekening == "-"
                or not uraian.strip()
            ):
                st.error(
                    "Sub Kegiatan, Kode Rekening, Nominal, dan Uraian wajib diisi dengan benar."
                )
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
                    "TANGGAL PENGAJUAN": tgl.strftime("%d/%m/%Y %H:%M:%S"),
                    "BUKTI DUKUNG SPJ": bukti or "",
                    "PPTK": pptk,
                }
                with st.spinner("Menyimpan transaksi ke Google Sheets…"):
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
                    with st.spinner("Mengirim notifikasi Telegram…"):
                        telegram_ok = helpers.send_telegram(pesan)
                    st.toast(f"✅ Transaksi No {result} berhasil diajukan.", icon="✅")
                    st.session_state.simpan_status = {
                        "success": True,
                        "message": f"✅ Transaksi berhasil diajukan. Nomor: {result}",
                        "telegram_ok": telegram_ok,
                    }
                    # Reset form input ke state awal
                    helpers.reset_form_keys(
                        "tx_tanggal", "tx_subkegiatan", "tx_rekening",
                        "tx_pengelompokan", "tx_jenis", "tx_nominal",
                        "tx_uraian", "tx_bukti",
                    )
                    st.rerun()
                else:
                    st.toast("❌ Gagal menyimpan transaksi.", icon="❌")
                    st.session_state.simpan_status = {
                        "success": False,
                        "message": f"❌ Gagal menyimpan: {result}",
                    }
                    st.rerun()

st.divider()
st.subheader("Daftar transaksi")

# Banner penolakan untuk PPTK (lihat alasan dan ajukan ulang di bawah)
pptk_filter = st.session_state.get("pptk_filter")
ajukan_ulang_map = {}
if (
    pptk_filter
    and pptk_filter != "Semua PPTK"
    and not df_transaksi.empty
    and "STATUS" in df_transaksi.columns
    and "PPTK" in df_transaksi.columns
):
    # Peta {NO baru: NO lama} untuk transaksi yang sudah diajukan ulang (retroaktif)
    ajukan_ulang_map = helpers.get_ajukan_ulang_map()
    df_ditolak = df_transaksi[
        (df_transaksi["STATUS"].astype(str).str.strip() == "Ditolak")
        & (df_transaksi["PPTK"].astype(str) == pptk_filter)
    ]
    # Kecualikan transaksi lama yang sudah diajukan ulang (tidak lagi butuh aksi)
    if not df_ditolak.empty and ajukan_ulang_map:
        superseded_old = set(ajukan_ulang_map.values())
        df_ditolak = df_ditolak[
            ~pd.to_numeric(df_ditolak["NO"], errors="coerce").isin(superseded_old)
        ]
    if not df_ditolak.empty:
        st.warning(
            f"{len(df_ditolak)} transaksi Anda ditolak. "
            "Periksa alasan di daftar dan ajukan ulang melalui panel di bawah."
        )

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
                    ["Semua", "Draft", "Disetujui", "Ditolak"],
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

    if "ALASAN_PENOLAKAN" not in df_show.columns:
        df_show["ALASAN_PENOLAKAN"] = ""

    st.caption(f"Menampilkan {len(df_show)} dari {len(df_transaksi)} transaksi")
    st.dataframe(
        helpers.format_df_rupiah(df_show),
        hide_index=True,
        width="stretch",
    )

    # --- Panel kelola transaksi PPTK (edit Draft, hapus Draft, ajukan ulang Ditolak) ---
    if (
        pptk_filter
        and pptk_filter != "Semua PPTK"
        and not df_transaksi.empty
        and "STATUS" in df_transaksi.columns
        and "PPTK" in df_transaksi.columns
    ):
        current_user = st.session_state.get("current_user") or {}
        current_user_nama = current_user.get("Nama", "Sistem")
        df_miliku = df_transaksi[df_transaksi["PPTK"].astype(str) == pptk_filter]
        if not df_miliku.empty:
            st.divider()
            with st.expander("Kelola transaksi saya", expanded=True):

                opsi_map = {}
                for _, r in df_miliku.iterrows():
                    no_val = r.get("NO")
                    label = (
                        f"No {no_val} · {r.get('STATUS','-')} · "
                        f"{helpers.format_rupiah(r.get('NOMINAL',0))} · "
                        f"{str(r.get('SUB KEGIATAN','-'))}"
                    )
                    opsi_map[label] = no_val

                # Pilihan yang tersimpan di session_state mungkin sudah tidak valid
                # (transaksi dihapus atau berubah nomor/label setelah edit/hapus).
                if (
                    "kelola_pilih" in st.session_state
                    and st.session_state.kelola_pilih not in opsi_map
                ):
                    st.session_state.pop("kelola_pilih", None)
                    st.rerun()

                pilih_label = st.selectbox(
                    "Pilih transaksi", options=list(opsi_map.keys()), key="kelola_pilih"
                )
                no_pilih = int(opsi_map[pilih_label])
                baris = (
                    df_miliku[pd.to_numeric(df_miliku["NO"], errors="coerce") == no_pilih]
                    .iloc[0]
                )
                status_baris = str(baris.get("STATUS", "")).strip()
                st.caption(f"Status: {status_baris}")

                # Nilai default untuk selectbox agar sesuai data transaksi yang dipilih.
                current_subkode = str(baris.get("SUB KEGIATAN", ""))
                subkode_only = current_subkode.split(" - ")[0] if " - " in current_subkode else current_subkode
                sub_idx = sub_opts.index(subkode_only) if subkode_only in sub_opts else 0

                current_rekening = str(baris.get("KODE REKENING BELANJA", ""))
                rek_idx = rekening_opts.index(current_rekening) if current_rekening in rekening_opts else 0

                # Tombol-tombol aksi dengan label yang jelas (buka form terpisah)
                # State mode untuk masing-masing transaksi.
                edit_mode_key = f"edit_mode_{no_pilih}"
                hapus_mode_key = f"hapus_mode_{no_pilih}"
                ajukan_ulang_mode_key = f"ajukan_ulang_mode_{no_pilih}"

                # --- Aksi Edit (hanya Draft dan Ditolak yang bisa diedit) ---
                if status_baris in ("Draft", "Ditolak"):
                    col_edit, col_hapus, col_ulang = st.columns(3)
                    with col_edit:
                        if st.button("Edit Transaksi", key=f"btn_edit_{no_pilih}", type="secondary"):
                            st.session_state[edit_mode_key] = True
                            st.session_state[hapus_mode_key] = False
                            st.session_state[ajukan_ulang_mode_key] = False
                            st.rerun()

                    # --- Aksi Hapus (hanya Draft dan Ditolak) ---
                    with col_hapus:
                        if st.button("Hapus Transaksi", key=f"btn_hapus_{no_pilih}", type="secondary"):
                            st.session_state[hapus_mode_key] = True
                            st.session_state[edit_mode_key] = False
                            st.session_state[ajukan_ulang_mode_key] = False
                            st.rerun()

                    # --- Aksi Ajukan Ulang (hanya Ditolak yang belum punya pengganti) ---
                    if status_baris == "Ditolak":
                        sudah_diajukan_ulang = any(v == no_pilih for v in ajukan_ulang_map.values())
                        with col_ulang:
                            if not sudah_diajukan_ulang:
                                if st.button(
                                    "Ajukan Ulang", key=f"btn_ulang_{no_pilih}", type="secondary"
                                ):
                                    st.session_state[ajukan_ulang_mode_key] = True
                                    st.session_state[edit_mode_key] = False
                                    st.session_state[hapus_mode_key] = False
                                    st.rerun()
                            else:
                                st.caption("Sudah diajukan ulang.")
                else:
                    st.info("Transaksi sudah disetujui dan tidak dapat diubah.")
                    # Reset mode agar form tidak muncul
                    st.session_state[edit_mode_key] = False
                    st.session_state[hapus_mode_key] = False
                    st.session_state[ajukan_ulang_mode_key] = False

                st.divider()

                # ============ FORM EDIT (muncul saat tombol Edit ditekan) ============
                if status_baris == "Draft" and st.session_state.get(edit_mode_key, False):
                    st.markdown("**Edit transaksi (semua field dapat diubah)**")

                    # Sub Kegiatan di luar form agar pemilihan langsung trigger rerun,
                    # dan info Pagu Awal / Sisa Pagu ikut terupdate tanpa perlu submit form.
                    edit_subkode_key = f"e_subkegiatan_{no_pilih}"
                    if edit_subkode_key not in st.session_state:
                        st.session_state[edit_subkode_key] = (
                            sub_opts[sub_idx] if sub_opts else "-"
                        )
                    e_subkegiatan = st.selectbox(
                        "Sub Kegiatan",
                        options=sub_opts if sub_opts else ["-"],
                        format_func=lambda x: helpers.get_subkegiatan_full(x, df_kegiatan),
                        key=edit_subkode_key,
                    )
                    # Info Sisa Pagu & Pagu Awal di bawah dropdown Sub Kegiatan (edit)
                    e_sg_kode = ""
                    if not df_kegiatan.empty and "Kode Sub Kegiatan" in df_kegiatan.columns:
                        e_sg_kode = str(e_subkegiatan).split(" - ")[0] if " - " in str(e_subkegiatan) else str(e_subkegiatan)
                    e_pagu_awal = helpers.get_pagu_awal(e_sg_kode, df_kegiatan)
                    e_sisa_pagu = helpers.get_sisa_pagu(e_sg_kode, df_kegiatan, df_transaksi)
                    st.caption(f"Pagu Awal: {helpers.format_rupiah(e_pagu_awal)} · Sisa Pagu: {helpers.format_rupiah(e_sisa_pagu)}")

                    with st.form(f"form_edit_miliku_{no_pilih}", border=True):
                        e_rekening = st.selectbox(
                            "Kode Rekening Belanja",
                            options=rekening_opts if rekening_opts else ["-"],
                            format_func=lambda x: helpers.get_rekening_full(x, df_rekening),
                            index=rek_idx,
                            key=f"e_rekening_{no_pilih}",
                        )
                        e_pengelompokan = st.text_input(
                            "Pengelompokan Belanja (#)",
                            value=str(baris.get("PENGELOMPOKAN BELANJA (#)", "")),
                            key=f"e_pengelompokan_{no_pilih}",
                        )
                        e_jenis = st.selectbox(
                            "Jenis Transaksi",
                            ["UP/GU", "LS"],
                            index=0 if str(baris.get("JENIS TRANSAKSI (UP/GU/LS)", "")) in ("", "UP/GU") else 1,
                            key=f"e_jenis_{no_pilih}",
                        )
                        e_uraian = st.text_area(
                            "Uraian baru",
                            value=str(baris.get("URAIAN", "")),
                            key=f"e_uraian_{no_pilih}",
                        )
                        e_nominal = st.number_input(
                            "Nominal baru (Rp)",
                            min_value=0.0,
                            step=1000.0,
                            value=float(helpers.parse_number(baris.get("NOMINAL", 0)) or 0),
                            key=f"e_nominal_{no_pilih}",
                        )
                        e_bukti = st.text_input(
                            "Bukti Dukung SPJ (tautan / nomor)",
                            value=str(baris.get("BUKTI DUKUNG SPJ", "")),
                            key=f"e_bukti_{no_pilih}",
                        )
                        konf_edit = st.checkbox(
                            "Saya yakin ingin mengedit transaksi ini.",
                            key=f"konf_edit_{no_pilih}",
                        )
                        if st.form_submit_button("Simpan Edit", type="primary"):
                            if not konf_edit:
                                st.error("Centang konfirmasi terlebih dahulu.")
                            elif e_subkegiatan == "-" or e_rekening == "-" or not e_uraian.strip() or e_nominal <= 0:
                                st.error("Sub Kegiatan, Kode Rekening, Uraian, dan Nominal wajib diisi dengan benar.")
                            else:
                                with st.spinner("Mengedit transaksi…"):
                                    ok = helpers.edit_transaksi_pptk(
                                        no_pilih,
                                        helpers.get_subkegiatan_full(e_subkegiatan, df_kegiatan),
                                        e_rekening,
                                        e_pengelompokan or "",
                                        e_uraian.strip(),
                                        e_jenis,
                                        e_nominal,
                                        e_bukti or "",
                                        user=current_user_nama,
                                        pptk_label=pptk_filter,
                                    )
                                if ok:
                                    st.toast(f"✅ Transaksi No {no_pilih} berhasil diupdate.", icon="✅")
                                    st.success(f"Transaksi No {no_pilih} berhasil diupdate.")
                                    # Reset form edit ke state awal
                                    helpers.reset_form_keys(
                                        f"e_subkegiatan_{no_pilih}", f"e_rekening_{no_pilih}",
                                        f"e_pengelompokan_{no_pilih}", f"e_jenis_{no_pilih}",
                                        f"e_uraian_{no_pilih}", f"e_nominal_{no_pilih}",
                                        f"e_bukti_{no_pilih}", f"konf_edit_{no_pilih}",
                                    )
                                    st.session_state[edit_mode_key] = False
                                    st.rerun()
                                else:
                                    st.toast("❌ Gagal mengedit transaksi.", icon="❌")
                                    st.error("Gagal mengedit transaksi.")

                    st.divider()

                # ============ KONFIRMASI HAPUS (muncul saat tombol Hapus ditekan) ============
                if status_baris in ("Draft", "Ditolak") and st.session_state.get(hapus_mode_key, False):
                    st.warning("⚠️ Hapus tidak dapat dibatalkan.")
                    konf_hapus = st.checkbox(
                        "Saya yakin ingin menghapus transaksi ini.",
                        key=f"konf_hapus_{no_pilih}",
                    )
                    if st.button("Hapus Transaksi", type="secondary", key=f"btn_hapus_conf_{no_pilih}"):
                        if not konf_hapus:
                            st.error("Centang konfirmasi terlebih dahulu.")
                        else:
                            with st.spinner("Menghapus transaksi…"):
                                ok = helpers.delete_transaksi_pptk(
                                    no_pilih,
                                    user=current_user_nama,
                                    pptk_label=pptk_filter,
                                )
                            if ok:
                                st.toast(f"🗑️ Transaksi No {no_pilih} berhasil dihapus.", icon="🗑️")
                                st.success(f"Transaksi No {no_pilih} berhasil dihapus.")
                                # Reset form hapus ke state awal
                                helpers.reset_form_keys(
                                    f"konf_hapus_{no_pilih}",
                                )
                                st.session_state[hapus_mode_key] = False
                                st.rerun()
                            else:
                                st.toast("❌ Gagal menghapus transaksi.", icon="❌")
                                st.error("Gagal menghapus transaksi.")

                    st.divider()

                # ============ FORM AJUKAN ULANG (muncul saat tombol Ajukan Ulang ditekan) ============
                if status_baris == "Ditolak" and st.session_state.get(ajukan_ulang_mode_key, False):
                    # Cek apakah transaksi ini sudah diajukan ulang sebelumnya
                    successor_no = None
                    for k, v in ajukan_ulang_map.items():
                        if v == no_pilih:
                            successor_no = k
                            break
                    if successor_no is not None:
                        # Cari status pengganti (jika ada)
                        succ_status = "-"
                        if not df_transaksi.empty and "STATUS" in df_transaksi.columns:
                            succ_rows = df_transaksi[
                                pd.to_numeric(df_transaksi["NO"], errors="coerce") == successor_no
                            ]
                            if not succ_rows.empty:
                                succ_status = str(succ_rows.iloc[0].get("STATUS", "-")).strip()
                        st.info(
                            f"Transaksi ini sudah diajukan ulang sebagai No {successor_no} "
                            f"(status: {succ_status}). Tidak perlu diajukan ulang lagi."
                        )
                    else:
                        alasan_lama = str(baris.get("ALASAN_PENOLAKAN", "") or "")
                        st.error(f"Alasan penolakan: {alasan_lama if alasan_lama else '-'}")
                        with st.form(f"form_ajukan_ulang_{no_pilih}", border=True):
                            st.markdown("**Ajukan ulang transaksi (NO baru)**")
                            a_uraian = st.text_area(
                                "Uraian baru",
                                value=str(baris.get("URAIAN", "")),
                                key=f"a_uraian_{no_pilih}",
                            )
                            a_nominal = st.number_input(
                                "Nominal baru (Rp)",
                                min_value=0.0,
                                step=1000.0,
                                value=float(helpers.parse_number(baris.get("NOMINAL", 0)) or 0),
                                key=f"a_nominal_{no_pilih}",
                            )
                            konf_ulang = st.checkbox(
                                "Saya yakin ingin mengajukan ulang transaksi ini.",
                                key=f"konf_ulang_{no_pilih}",
                            )
                            if st.form_submit_button("Ajukan Ulang", type="primary"):
                                if not konf_ulang:
                                    st.error("Centang konfirmasi terlebih dahulu.")
                                elif not a_uraian.strip() or a_nominal <= 0:
                                    st.error("Uraian dan nominal wajib diisi dengan benar.")
                                else:
                                    with st.spinner("Mengajukan ulang transaksi…"):
                                        ok, new_no = helpers.ajukan_ulang_transaksi(
                                            no_pilih,
                                            a_uraian.strip(),
                                            a_nominal,
                                            user=current_user_nama,
                                            pptk_label=pptk_filter,
                                        )
                                    if ok:
                                        st.toast(
                                            f"✅ Transaksi diajukan ulang sebagai No {new_no}.",
                                            icon="✅",
                                        )
                                        st.success(
                                            f"Transaksi diajukan ulang sebagai No {new_no}. Menunggu approval."
                                        )
                                        # Reset form ajukan ulang ke state awal
                                        helpers.reset_form_keys(
                                            f"a_uraian_{no_pilih}", f"a_nominal_{no_pilih}",
                                            f"konf_ulang_{no_pilih}",
                                        )
                                        st.session_state[ajukan_ulang_mode_key] = False
                                        st.rerun()
                                    else:
                                        st.toast("❌ Gagal mengajukan ulang.", icon="❌")
                                        st.error(str(new_no))

                    st.divider()
        else:
            st.info("Belum ada transaksi.")

    # --- Sidebar: Export Transaksi (hanya muncul saat menu Transaksi aktif) ---
    with st.sidebar:
        st.divider()
        st.subheader("📤 Export Transaksi")
        if not df_transaksi.empty:
            # df_show selalu terdefinisi saat df_transaksi tidak kosong (tidak ada block scope di Python)
            export_df = df_show
            nominal_col_exp = (
                "NOMINAL" if "NOMINAL" in export_df.columns else None
            )
            total_pagu_exp = 0.0
            if not df_kegiatan.empty and "Pagu Awal" in df_kegiatan.columns:
                total_pagu_exp = float(
                    helpers.to_number_series(df_kegiatan["Pagu Awal"]).sum()
                )
            total_realisasi_exp = 0.0
            if nominal_col_exp and not export_df.empty:
                total_realisasi_exp = float(
                    helpers.to_number_series(export_df[nominal_col_exp]).sum()
                )
            sisa_exp = total_pagu_exp - total_realisasi_exp
            persen_exp = (
                (total_realisasi_exp / total_pagu_exp * 100) if total_pagu_exp else 0
            )

            current_user = st.session_state.get("current_user") or {}
            if helpers.OPENPYXL_AVAILABLE:
                xlsx_bytes = helpers.export_to_excel(export_df)
                st.download_button(
                    label="Unduh Excel (data terfilter)",
                    data=xlsx_bytes,
                    file_name="laporan_transaksi_filtered.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="sidebar_dl_excel_transaksi",
                )
        else:
            st.caption("Library openpyxl tidak tersedia.")

        if helpers.is_manager(current_user.get("Peran", "")):
            if helpers.REPORTLAB_AVAILABLE:
                pdf_bytes = helpers.export_to_pdf(
                    df_transaksi=export_df,
                    df_kegiatan=df_kegiatan,
                    total_pagu=total_pagu_exp,
                    total_realisasi=total_realisasi_exp,
                    sisa=sisa_exp,
                    persen=persen_exp,
                    nominal_col=nominal_col_exp,
                    NOMINAL_COL_FOR_DASH=nominal_col_exp,
                    nama_file="laporan_transaksi_filtered.pdf",
                )
                st.download_button(
                    label="Unduh PDF (data terfilter)",
                    data=pdf_bytes,
                    file_name="laporan_transaksi_filtered.pdf",
                    mime="application/pdf",
                    key="sidebar_dl_pdf_transaksi",
                )
            else:
                st.caption("Library reportlab tidak tersedia.")
        else:
            st.caption("Unduh PDF hanya untuk manajer (ADMIN / KASUBAG_PEK).")
