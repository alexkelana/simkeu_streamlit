"""
Halaman Dashboard — gambaran besar kondisi keuangan (KPI, grafik, transaksi hari ini).
Untuk semua user yang login. Data difilter sesuai pptk_filter (PPTK hanya lihat data sendiri).

Khusus KASUBAG_PEK, Dashboard juga memuat informasi tanpa aksi yang dipindah dari
halaman Manajerial: Ringkasan Realisasi per PPTK, Peringatan Pagu ≥90%, dan
Peringkat PPTK Berdasarkan Realisasi.
"""

import streamlit as st
import pandas as pd

from app_pages import helpers  # noqa: E402


@st.fragment
def kpi_row(*, jumlah_kegiatan: int, total_pagu: float, total_realisasi: float,
            sisa: float, persen: float):
    """KPI cards yang rerun terpisah dari halaman utama."""
    with st.container(horizontal=True):
        st.metric("Jumlah Sub Kegiatan", jumlah_kegiatan, border=True)
        st.metric("Total Pagu", helpers.format_rupiah(total_pagu), border=True)
        st.metric("Realisasi", helpers.format_rupiah(total_realisasi), border=True)
        st.metric(
            "Sisa Pagu",
            helpers.format_rupiah(sisa),
            delta=f"{persen:.1f}% terpakai",
            border=True,
        )
        if st.button("Refresh KPI", key="refresh_kpi"):
            st.rerun(scope="fragment")


st.header("Dashboard")

current_user = st.session_state.get("current_user") or {}
user_peran = str(current_user.get("Peran", "")).upper()

# --- Kesehatan Sistem (khusus ADMIN) — tidak ada informasi keuangan ---
if user_peran == "ADMIN":
    st.divider()
    st.subheader("🏥 Kesehatan Sistem")
    st.caption("Ringkasan kondisi sistem SIMKEU untuk administrator.")

    # 1. Status koneksi Google Sheets
    st.caption("Koneksi Google Sheets")
    try:
        helpers.load_sheet("PENGGUNA")
        st.success("Terhubung ke Google Sheets.")
    except Exception as exc:
        st.error(f"Gagal terhubung ke Google Sheets: {exc}")

    # 2. Jumlah baris per worksheet
    st.caption("Jumlah baris per worksheet")
    worksheet_rows = []
    for ws in [
        "TRANSAKSI", "MASTER_SUB_KEGIATAN", "PERUBAHAN_PAGU",
        "PENGGUNA", "AUDIT_LOG", "MASTER_WILAYAH", "MASTER_REKENING",
    ]:
        try:
            df_ws = helpers.load_sheet(ws)
            worksheet_rows.append({"Worksheet": ws, "Baris": len(df_ws)})
        except Exception:
            worksheet_rows.append({"Worksheet": ws, "Baris": "-"})
    if worksheet_rows:
        st.dataframe(pd.DataFrame(worksheet_rows), hide_index=True, width="stretch")

    # 3. Pengaturan Notifikasi Telegram (hanya ADMIN)
    st.caption("Notifikasi Telegram")
    try:
        if "telegram_enabled" not in st.session_state:
            st.session_state.telegram_enabled = helpers.load_telegram_setting()
        telegram_enabled = st.session_state.telegram_enabled
        new_value = st.toggle(
            "Aktifkan notifikasi Telegram",
            value=telegram_enabled,
            key="health_toggle_telegram",
            help="Matikan untuk menghentikan notifikasi Telegram saat transaksi baru atau penolakan.",
        )
        if new_value != telegram_enabled:
            st.session_state.telegram_enabled = new_value
            helpers.save_telegram_setting(new_value)
            st.rerun()
        if not new_value:
            st.info("Notifikasi Telegram saat ini dimatikan.")
    except Exception:
        st.info("Pengaturan Telegram tidak tersedia.")

    # 4. Audit Log Terkini
    st.caption("Audit Log Terkini")
    try:
        df_audit = helpers.load_sheet("AUDIT_LOG")
        if not df_audit.empty and "WAKTU" in df_audit.columns:
            df_audit = df_audit.sort_values("WAKTU", ascending=False).head(5)
            st.dataframe(df_audit, hide_index=True, width="stretch")
        else:
            st.info("Belum ada audit log.")
    except Exception:
        st.info("Audit log tidak tersedia.")

    # 5. Informasi aplikasi
    st.caption("Informasi Aplikasi")
    st.text(f"Streamlit: {getattr(st, '__version__', '-')}")
    st.text("Halaman: Dashboard (Kesehatan Sistem — ADMIN)")

    st.stop()

# Muat data yang diperlukan (cached)
df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")
df_transaksi = helpers.load_sheet("TRANSAKSI")

# Terapkan filter PPTK ke data transaksi
pptk_filter = st.session_state.get("pptk_filter")
if pptk_filter and pptk_filter != "Semua PPTK" and "PPTK" in df_transaksi.columns:
    df_transaksi = df_transaksi[df_transaksi["PPTK"].astype(str) == pptk_filter]

    # Untuk PPTK (bukan manajer): filter kegiatan hanya yang memiliki transaksi
    if user_peran not in ("ADMIN", "KASUBAG_PEK") and not df_transaksi.empty:
        if "SUB KEGIATAN" in df_transaksi.columns and "Kode Sub Kegiatan" in df_kegiatan.columns:
            subkode_terpakai = (
                df_transaksi["SUB KEGIATAN"].astype(str).str.split(" - ").str[0].str.strip().unique().tolist()
            )
            df_kegiatan = df_kegiatan[
                df_kegiatan["Kode Sub Kegiatan"].astype(str).isin(subkode_terpakai)
            ]

# --- Hitung KPI (hanya transaksi Disetujui, konsisten dengan formula
# Sisa Pagu di MASTER_SUB_KEGIATAN — lihat 10.1 Temuan) ---
total_pagu = 0
if not df_kegiatan.empty and "Pagu Awal" in df_kegiatan.columns:
    total_pagu = helpers.to_number_series(df_kegiatan["Pagu Awal"]).sum()

nominal_col = "NOMINAL" if "NOMINAL" in df_transaksi.columns else None

df_realisasi = df_transaksi
if nominal_col and not df_transaksi.empty and "STATUS" in df_transaksi.columns:
    df_realisasi = df_transaksi[
        df_transaksi["STATUS"].astype(str).str.strip() == "Disetujui"
    ]

total_realisasi = 0
if nominal_col and not df_realisasi.empty:
    total_realisasi = helpers.to_number_series(df_realisasi[nominal_col]).sum()

sisa = total_pagu - total_realisasi
persen = (total_realisasi / total_pagu * 100) if total_pagu else 0

# --- KPI Row ---
kpi_row(
    jumlah_kegiatan=len(df_kegiatan),
    total_pagu=total_pagu,
    total_realisasi=total_realisasi,
    sisa=sisa,
    persen=persen,
)

# --- 2. Peringatan Pagu Melebihi (≥90%) (khusus Kasubag, tidak collapsible) ---
if user_peran == "KASUBAG_PEK":
    st.divider()
    st.subheader("Peringatan Pagu Melebihi (≥90%)")
    if (
        not df_kegiatan.empty
        and not df_realisasi.empty
        and "Pagu Awal" in df_kegiatan.columns
        and nominal_col
        and "SUB KEGIATAN" in df_realisasi.columns
    ):
        df_kegiatan_copy = df_kegiatan.copy()
        df_kegiatan_copy["Pagu Awal"] = helpers.to_number_series(
            df_kegiatan_copy["Pagu Awal"]
        )
        df_realisasi_copy = df_realisasi.copy()
        df_realisasi_copy["_nominal"] = helpers.to_number_series(
            df_realisasi_copy[nominal_col]
        )
        df_realisasi_copy["_kode"] = (
            df_realisasi_copy["SUB KEGIATAN"]
            .astype(str)
            .str.split(" - ")
            .str[0]
            .str.strip()
        )
        realisasi_per_sub = (
            df_realisasi_copy.groupby("_kode")["_nominal"].sum().reset_index()
        )
        realisasi_per_sub.columns = ["Kode Sub Kegiatan", "Realisasi"]
        df_alert = df_kegiatan_copy.merge(
            realisasi_per_sub, on="Kode Sub Kegiatan", how="left"
        )
        df_alert["Realisasi"] = df_alert["Realisasi"].fillna(0)
        df_alert["% Pakai"] = (
            df_alert["Realisasi"] / df_alert["Pagu Awal"] * 100
        ).fillna(0)
        df_over = df_alert[df_alert["% Pakai"] >= 90].copy()
        if not df_over.empty:
            df_over_display = df_over[
                ["Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal", "Realisasi", "% Pakai"]
            ].copy()
            df_over_display.columns = ["Kode", "Nama Kegiatan", "Pagu", "Realisasi", "% Pakai"]
            df_over_display["Pagu"] = df_over_display["Pagu"].apply(helpers.format_rupiah)
            df_over_display["Realisasi"] = df_over_display["Realisasi"].apply(
                helpers.format_rupiah
            )
            df_over_display["% Pakai"] = df_over_display["% Pakai"].apply(
                lambda x: f"{x:.1f}%"
            )
            st.warning(
                f"⚠️ Ditemukan {len(df_over_display)} sub kegiatan yang pagunya "
                "telah mencapai ≥90%!"
            )
            st.dataframe(df_over_display, hide_index=True, width="stretch")
        else:
            st.info("✅ Tidak ada sub kegiatan yang melebihi 90% pagu.")
    else:
        st.info("Data pagu atau transaksi tidak cukup untuk peringatan over budget.")

# --- 3. Grafik Realisasi per Sub Kegiatan & Tren Bulanan (collapsible) ---
st.divider()
with st.expander("📊 Grafik Realisasi", expanded=True):
    col_chart1, col_chart2 = st.columns(2)

    # Kolom 1: Bar chart realisasi per sub kegiatan
    with col_chart1:
        st.caption("Realisasi per Sub Kegiatan")
        kolom_kegiatan = ["Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal"]
        if (
            not df_kegiatan.empty
            and not df_transaksi.empty
            and nominal_col
            and all(col in df_kegiatan.columns for col in kolom_kegiatan)
            and "SUB KEGIATAN" in df_transaksi.columns
        ):
            df_transaksi_copy = df_transaksi.copy()
            if "STATUS" in df_transaksi_copy.columns:
                df_transaksi_copy = df_transaksi_copy[
                    df_transaksi_copy["STATUS"].astype(str).str.strip() == "Disetujui"
                ]
            df_transaksi_copy["_nominal"] = helpers.to_number_series(df_transaksi_copy[nominal_col])
            df_transaksi_copy["_kode"] = (
                df_transaksi_copy["SUB KEGIATAN"].astype(str).str.split(" - ").str[0].str.strip()
            )
            realisasi_per_sub = (
                df_transaksi_copy.groupby("_kode")["_nominal"]
                .sum().reset_index()
            )
            realisasi_per_sub.columns = ["Kode Sub Kegiatan", "Realisasi"]

            df_kegiatan_display = df_kegiatan[kolom_kegiatan].copy()
            df_kegiatan_display = df_kegiatan_display.merge(
                realisasi_per_sub, on="Kode Sub Kegiatan", how="left"
            )
            df_kegiatan_display["Realisasi"] = df_kegiatan_display["Realisasi"].fillna(0)
            df_kegiatan_display["Pagu Awal"] = helpers.to_number_series(
                df_kegiatan_display["Pagu Awal"]
            )
            df_kegiatan_display["Sisa Pagu"] = (
                df_kegiatan_display["Pagu Awal"] - df_kegiatan_display["Realisasi"]
            )

            chart_df = df_kegiatan_display.copy()
            chart_df["label"] = (
                chart_df["Kode Sub Kegiatan"].astype(str)
                + " — "
                + chart_df["Sub Kegiatan"].fillna("").astype(str)
            )
            st.bar_chart(chart_df.set_index("label")["Realisasi"])
        else:
            st.info("Belum ada data sub kegiatan atau transaksi.")

    # Kolom 2: Line chart tren realisasi bulanan
    with col_chart2:
        st.caption("Tren Realisasi Bulanan")
        if not df_transaksi.empty and nominal_col and "TANGGAL PENGAJUAN" in df_transaksi.columns:
            df_trend = df_transaksi.copy()
            if "STATUS" in df_trend.columns:
                df_trend = df_trend[
                    df_trend["STATUS"].astype(str).str.strip() == "Disetujui"
                ]
            df_trend["_nominal"] = helpers.to_number_series(df_trend[nominal_col])
            df_trend["_tanggal"] = pd.to_datetime(
                df_trend["TANGGAL PENGAJUAN"], format="%d/%m/%Y", errors="coerce"
            )
            df_trend = df_trend.dropna(subset=["_tanggal"])
            if not df_trend.empty:
                trend_monthly = (
                    df_trend.groupby(df_trend["_tanggal"].dt.to_period("M"))["_nominal"]
                    .sum().reset_index()
                )
                trend_monthly["_tanggal"] = trend_monthly["_tanggal"].dt.strftime("%m/%Y")
                trend_monthly = trend_monthly.sort_values("_tanggal")
                st.line_chart(trend_monthly.set_index("_tanggal")["_nominal"])
            else:
                st.info("Belum ada data tren bulanan.")
        else:
            st.info("Data transaksi atau tanggal tidak cukup untuk tren bulanan.")

# --- 4. Perbandingan Target vs Realisasi per Sub Kegiatan (collapsible, manajer) ---
if helpers.is_manager(current_user.get("Peran", "")):
    with st.expander("🎯 Perbandingan Target vs Realisasi per Sub Kegiatan", expanded=False):
        st.divider()
        if (
            not df_kegiatan.empty
            and not df_transaksi.empty
            and "Pagu Awal" in df_kegiatan.columns
            and "SUB KEGIATAN" in df_transaksi.columns
            and nominal_col
        ):
            df_compare = df_kegiatan.copy()
            df_compare["Pagu Awal"] = helpers.to_number_series(df_compare["Pagu Awal"])
            df_transaksi_copy = df_transaksi.copy()
            if "STATUS" in df_transaksi_copy.columns:
                df_transaksi_copy = df_transaksi_copy[
                    df_transaksi_copy["STATUS"].astype(str).str.strip() == "Disetujui"
                ]
            df_transaksi_copy["_nominal"] = helpers.to_number_series(df_transaksi_copy[nominal_col])
            df_transaksi_copy["_kode"] = (
                df_transaksi_copy["SUB KEGIATAN"].astype(str).str.split(" - ").str[0].str.strip()
            )
            realisasi_per_sub = (
                df_transaksi_copy.groupby("_kode")["_nominal"]
                .sum().reset_index()
            )
            realisasi_per_sub.columns = ["Kode Sub Kegiatan", "Realisasi"]
            df_compare = df_compare.merge(realisasi_per_sub, on="Kode Sub Kegiatan", how="left")
            df_compare["Realisasi"] = df_compare["Realisasi"].fillna(0)

            df_compare_display = df_compare[
                ["Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal", "Realisasi"]
            ].copy()
            df_compare_display["Sisa Pagu"] = (
                df_compare_display["Pagu Awal"] - df_compare_display["Realisasi"]
            )
            df_compare_display = df_compare_display.rename(
                columns={"Pagu Awal": "Target (Pagu)"}
            )
            for col in ["Target (Pagu)", "Realisasi", "Sisa Pagu"]:
                df_compare_display[col] = df_compare_display[col].apply(helpers.format_rupiah)
            st.dataframe(df_compare_display, hide_index=True, width="stretch")
        else:
            st.info("Data pagu atau transaksi tidak cukup untuk perbandingan target vs realisasi.")

# --- 5. Transaksi hari ini (collapsible, pembeda dari daftar lengkap di menu Transaksi) ---
st.divider()
with st.expander("📅 Transaksi hari ini", expanded=False):
    st.caption(
        "Hanya transaksi dengan tanggal pengajuan "
        f"{pd.Timestamp.today().strftime('%d/%m/%Y')}."
    )
    df_hari_ini = pd.DataFrame()
    if not df_transaksi.empty and "TANGGAL PENGAJUAN" in df_transaksi.columns:
        _tgl_pengajuan = pd.to_datetime(
            df_transaksi["TANGGAL PENGAJUAN"], format="%d/%m/%Y", errors="coerce"
        )
        df_hari_ini = df_transaksi[
            _tgl_pengajuan == pd.Timestamp.today().normalize()
        ]
    if not df_hari_ini.empty:
        st.dataframe(helpers.format_df_rupiah(df_hari_ini), hide_index=True, width="stretch")
    else:
        st.info("Belum ada transaksi hari ini.")

# --- Informasi tanpa aksi khusus Kasubag (collapsible, dipindah dari halaman Manajerial) ---
if user_peran == "KASUBAG_PEK":
    # 6. Peringkat PPTK Berdasarkan Realisasi (collapsible)
    st.divider()
    with st.expander("🏆 Peringkat PPTK Berdasarkan Realisasi", expanded=False):
        if not df_realisasi.empty and nominal_col and "PPTK" in df_realisasi.columns:
            df_rank = (
                df_realisasi.assign(
                    _nominal=helpers.to_number_series(df_realisasi[nominal_col])
                )
                .groupby("PPTK")["_nominal"]
                .sum()
                .reset_index()
            )
            df_rank.columns = ["PPTK", "Total Realisasi"]
            df_rank = df_rank.sort_values("Total Realisasi", ascending=False)
            df_rank["Peringkat"] = range(1, len(df_rank) + 1)
            df_rank["Total Realisasi"] = df_rank["Total Realisasi"].apply(
                helpers.format_rupiah
            )
            df_rank = df_rank[["Peringkat", "PPTK", "Total Realisasi"]]
            st.dataframe(df_rank, hide_index=True, width="stretch")
        else:
            st.info("Belum ada data PPTK untuk ditampilkan dalam peringkat.")

    # 7. Ringkasan Realisasi per PPTK (collapsible)
    st.divider()
    with st.expander("📋 Ringkasan Realisasi per PPTK", expanded=False):
        if not df_realisasi.empty and nominal_col and "PPTK" in df_realisasi.columns:
            df_pptk_summary = (
                df_realisasi.assign(
                    _nominal=helpers.to_number_series(df_realisasi[nominal_col])
                )
                .groupby("PPTK")["_nominal"]
                .sum()
                .reset_index()
            )
            df_pptk_summary.columns = ["PPTK", "Realisasi"]
            df_pptk_summary = df_pptk_summary.sort_values("Realisasi", ascending=False)
            df_pptk_summary["Realisasi"] = df_pptk_summary["Realisasi"].apply(
                helpers.format_rupiah
            )
            st.dataframe(df_pptk_summary, hide_index=True, width="stretch")
        else:
            st.info("Belum ada data transaksi untuk ditampilkan per PPTK.")

# --- Sidebar: Export Laporan (role-based) ---
with st.sidebar:
    st.divider()
    st.subheader("📤 Export Laporan")
    df_export = df_transaksi if not df_transaksi.empty else pd.DataFrame()

    # Excel — untuk semua user yang login
    if helpers.OPENPYXL_AVAILABLE:
        xlsx_bytes = helpers.export_to_excel(df_export)
        st.download_button(
            label="Unduh Excel",
            data=xlsx_bytes,
            file_name="laporan_simkeu.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="sidebar_dl_excel",
        )
    else:
        st.caption("Library openpyxl tidak tersedia.")

    # PDF — hanya untuk manajer (ADMIN / KASUBAG_PEK)
    if helpers.is_manager(current_user.get("Peran", "")):
        if helpers.REPORTLAB_AVAILABLE:
            pdf_bytes = helpers.export_to_pdf(
                df_transaksi=df_export,
                df_kegiatan=df_kegiatan,
                total_pagu=total_pagu,
                total_realisasi=total_realisasi,
                sisa=sisa,
                persen=persen,
                nominal_col=nominal_col,
                NOMINAL_COL_FOR_DASH=nominal_col,
            )
            st.download_button(
                label="Unduh PDF",
                data=pdf_bytes,
                file_name="laporan_simkeu.pdf",
                mime="application/pdf",
                key="sidebar_dl_pdf",
            )
        else:
            st.caption("Library reportlab tidak tersedia.")
    else:
        st.caption("Unduh PDF hanya untuk manajer (ADMIN / KASUBAG_PEK).")
