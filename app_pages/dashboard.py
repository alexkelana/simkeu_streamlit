"""
Halaman Dashboard — gambaran besar kondisi keuangan (KPI, grafik, transaksi terbaru).
Untuk semua user yang login. Data difilter sesuai pptk_filter (PPTK hanya lihat data sendiri).
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

# Muat data yang diperlukan (cached)
df_kegiatan = helpers.load_sheet("MASTER_SUB_KEGIATAN")
df_transaksi = helpers.load_sheet("TRANSAKSI")

current_user = st.session_state.get("current_user") or {}
user_peran = str(current_user.get("Peran", "")).upper()

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

# --- Hitung KPI ---
total_pagu = 0
if not df_kegiatan.empty and "Pagu Awal" in df_kegiatan.columns:
    total_pagu = helpers.to_number_series(df_kegiatan["Pagu Awal"]).sum()

nominal_col = "NOMINAL" if "NOMINAL" in df_transaksi.columns else None

total_realisasi = 0
if nominal_col and not df_transaksi.empty:
    total_realisasi = helpers.to_number_series(df_transaksi[nominal_col]).sum()

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

# --- Grafik Realisasi per Sub Kegiatan & Tren Bulanan ---
st.divider()
st.subheader("Grafik Realisasi")

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

# --- Perbandingan Target vs Realisasi per Sub Kegiatan (khusus manajer) ---
if helpers.is_manager(current_user.get("Peran", "")):
    st.divider()
    st.subheader("Perbandingan Target vs Realisasi per Sub Kegiatan")
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

# --- Transaksi Terbaru ---
st.divider()
st.subheader("Transaksi Terbaru")
if not df_transaksi.empty:
    st.dataframe(helpers.format_df_rupiah(df_transaksi), hide_index=True, width="stretch")
else:
    st.info("Belum ada transaksi.")

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
