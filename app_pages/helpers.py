"""
Backend bersama untuk semua halaman SIMKEU.
Berisi fungsi baca/tulis Google Sheets, format, export, dan audit log.
Semua fungsi diakses melalui get_conn() dari streamlit_app (cache_resource).
"""

import io
import re
import secrets as pysecrets
from datetime import date, datetime

import pandas as pd
import streamlit as st

from db import get_conn, SPREADSHEET_URL  # noqa: E402

try:
    from openpyxl import Workbook  # noqa: F401
    OPENPYXL_AVAILABLE = True
except Exception:
    OPENPYXL_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Koneksi & baca data (cache)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner="Memuat data…")
def load_sheet(worksheet_name: str) -> pd.DataFrame:
    """Baca worksheet dari Google Sheets. Mengembalikan DataFrame kosong jika gagal."""
    try:
        conn = get_conn()
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, ttl=30)
        if df is not None and not df.empty:
            return df
        return pd.DataFrame()
    except Exception:
        st.error(f"❌ Gagal membaca sheet '{worksheet_name}'.")
        return pd.DataFrame()


def update_sheet_data(worksheet_name: str, df: pd.DataFrame) -> bool:
    """Tulis ulang seluruh data worksheet ke Google Sheets dan bersihkan cache worksheet tersebut saja."""
    try:
        conn = get_conn()
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, data=df)
        load_sheet.clear()  # Bersihkan hanya cache load_sheet, bukan semua cache global
        return True
    except Exception:
        st.error(f"❌ Gagal menyimpan ke sheet '{worksheet_name}'.")
        return False


def send_telegram(message: str) -> bool:
    """Kirim notifikasi ke Telegram. Return True jika berhasil."""
    try:
        if "telegram" not in st.secrets:
            return False
        token = st.secrets["telegram"].get("bot_token")
        chat_id = st.secrets["telegram"].get("chat_id")
        if not token or not chat_id:
            return False
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Format & export
# ---------------------------------------------------------------------------
def parse_number(value):
    """Ubah nilai dari Google Sheets menjadi float.

    Sheet menyimpan angka sebagai teks, misalnya ``"50,000,000.00"``.
    Format Indonesia (``"1.234.567,89"``) dan format Inggris
    (``"1,234,567.89"``) sama-sama didukung.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    text = text.replace("Rp", "").replace("rp", "").replace(" ", "")
    if not re.search(r"\d", text):
        return None

    has_comma = "," in text
    has_dot = "." in text

    if has_comma and has_dot:
        # Pemisah yang muncul terakhir adalah pemisah desimal.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif has_comma:
        after_comma = text.rsplit(",", 1)[1]
        digits = text.replace(",", "").replace(".", "")
        if len(after_comma) == 3 and len(digits) > 3:
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")
    elif has_dot and text.count(".") > 1:
        # Beberapa titik berarti pemisah ribuan.
        text = text.replace(".", "")

    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def to_number_series(series: pd.Series) -> pd.Series:
    """Konversi kolom angka dari Google Sheets menjadi Series float."""
    return series.apply(parse_number).fillna(0.0).astype(float)


def format_rupiah(n):
    number = parse_number(n)
    if number is None:
        return "-"
    if number < 0:
        return f"(Rp {abs(number):,.0f})".replace(",", ".")
    return f"Rp {number:,.0f}".replace(",", ".")


def format_df_rupiah(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    nominal_cols = [
        "NOMINAL",
        "Pagu Awal",
        "PAGU BARU",
        "Sisa Pagu",
        "Realisasi",
    ]
    for col in nominal_cols:
        if col in df.columns:
            df[col] = df[col].apply(format_rupiah)

    # Samakan tipe kolom teks agar aman diserialisasi ke Arrow oleh st.dataframe.
    for col in df.columns:
        if col in nominal_cols:
            continue
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda value: "" if pd.isna(value) else str(value))
    return df


def export_to_excel(df: pd.DataFrame, nama_file: str = "laporan_simkeu.xlsx") -> bytes:
    if not OPENPYXL_AVAILABLE:
        return b""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Laporan")
    return output.getvalue()


def export_to_pdf(
    df_transaksi=None,
    df_kegiatan=None,
    total_pagu=0,
    total_realisasi=0,
    sisa=0,
    persen=0,
    nominal_col=None,
    NOMINAL_COL_FOR_DASH=None,
    nama_file="laporan_simkeu.pdf",
) -> bytes:
    if not REPORTLAB_AVAILABLE:
        return b""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=25, rightMargin=25, topMargin=25, bottomMargin=25,
        title="Laporan SIMKEU Kecamatan Candisari 2027",
        author="SIMKEU",
    )
    styles = getSampleStyleSheet()

    cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=7, leading=8, alignment=0)
    cell_style_bold = ParagraphStyle("CellStyleBold", parent=cell_style, fontName="Helvetica-Bold")
    header_style = ParagraphStyle(
        "HeaderStyle", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7.5, leading=9, alignment=0, textColor=colors.whitesmoke,
    )

    elements = []
    elements.append(Paragraph("LAPORAN TRANSAKSI SIMKEU", styles["Title"]))
    elements.append(Paragraph("Kecamatan Candisari 2027", styles["Heading2"]))
    elements.append(Paragraph(f"Tanggal Cetak: {date.today().strftime('%d/%m/%Y')}", styles["Normal"]))
    elements.append(Paragraph("Dibuat oleh: SIMKEU Sistem Manajemen Keuangan", styles["Normal"]))
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    elements.append(Paragraph("1. Ringkasan Eksekutif", styles["Heading3"]))
    summary_data = [
        [Paragraph("Total Pagu", header_style), Paragraph(format_rupiah(total_pagu), cell_style_bold)],
        [Paragraph("Total Realisasi", header_style), Paragraph(format_rupiah(total_realisasi), cell_style_bold)],
        [Paragraph("Sisa Pagu", header_style), Paragraph(format_rupiah(sisa), cell_style_bold)],
        [Paragraph("Persentase Realisasi", header_style), Paragraph(f"{persen:.1f}%", cell_style_bold)],
    ]
    summary_table = Table(summary_data, colWidths=[160, 300])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(summary_table)
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    elements.append(Paragraph("2. Perbandingan Target vs Realisasi per Sub Kegiatan", styles["Heading3"]))
    if df_kegiatan is not None and not df_kegiatan.empty and nominal_col and NOMINAL_COL_FOR_DASH:
        df_compare = df_kegiatan.copy()
        df_compare["Pagu Awal"] = to_number_series(df_compare["Pagu Awal"])
        df_transaksi_calc = df_transaksi.copy() if df_transaksi is not None else pd.DataFrame()
        if not df_transaksi_calc.empty:
            df_transaksi_calc[NOMINAL_COL_FOR_DASH] = to_number_series(
                df_transaksi_calc[NOMINAL_COL_FOR_DASH]
            )
            df_transaksi_calc["subkode"] = df_transaksi_calc["SUB KEGIATAN"].astype(str).str.split(" - ").str[0]
            realisasi_per_sub = (
                df_transaksi_calc.groupby("subkode")[NOMINAL_COL_FOR_DASH]
                .sum().reset_index()
            )
            realisasi_per_sub.columns = ["Kode Sub Kegiatan", "realisasi"]
            df_compare = df_compare.merge(realisasi_per_sub, on="Kode Sub Kegiatan", how="left")
            df_compare["realisasi"] = df_compare["realisasi"].fillna(0)
        else:
            df_compare["realisasi"] = 0

        df_compare["Sisa Pagu"] = df_compare["Pagu Awal"] - df_compare["realisasi"]

        pdf_header = [
            Paragraph("Kode", header_style),
            Paragraph("Nama Kegiatan", header_style),
            Paragraph("Pagu Awal", header_style),
            Paragraph("Realisasi", header_style),
            Paragraph("Sisa Pagu", header_style),
        ]
        pdf_data = [pdf_header]
        for _, row in df_compare.iterrows():
            pdf_data.append([
                Paragraph(str(row.get("Kode Sub Kegiatan", "-")), cell_style),
                Paragraph(str(row.get("Sub Kegiatan", "-")), cell_style),
                Paragraph(format_rupiah(row.get("Pagu Awal", 0)), cell_style),
                Paragraph(format_rupiah(row.get("realisasi", 0)), cell_style),
                Paragraph(format_rupiah(row.get("Sisa Pagu", 0)), cell_style),
            ])
        col_widths = [70, 220, 130, 130, 130]
        compare_table = Table(pdf_data, colWidths=col_widths, repeatRows=1)
        compare_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(compare_table)
    else:
        elements.append(Paragraph("Data sub kegiatan tidak tersedia.", cell_style))
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    elements.append(Paragraph("3. Daftar Transaksi", styles["Heading3"]))
    if df_transaksi is not None and not df_transaksi.empty:
        df_show = df_transaksi.copy()
        for col in ["NOMINAL"]:
            if col in df_show.columns:
                df_show[col] = df_show[col].apply(format_rupiah)
        export_cols = [c for c in [
            "NO", "SUB KEGIATAN", "KODE REKENING BELANJA",
            "PENGELOMPOKAN BELANJA (#)", "URAIAN",
            "JENIS TRANSAKSI (UP/GU/LS)", "NOMINAL",
            "TANGGAL PENGAJUAN", "PPTK", "STATUS"
        ] if c in df_show.columns]
        df_show = df_show[export_cols]

        pdf_header = [Paragraph(str(c), header_style) for c in df_show.columns]
        pdf_data = [pdf_header]
        for _, row in df_show.iterrows():
            pdf_data.append([Paragraph(str(row.get(c, "-")), cell_style) for c in df_show.columns])

        n_cols = len(df_show.columns)
        available_width = 792
        base_width = available_width / n_cols
        col_widths = [max(50, min(160, base_width)) for _ in range(n_cols)]
        trans_table = Table(pdf_data, colWidths=col_widths, repeatRows=1)
        trans_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(trans_table)
    else:
        elements.append(Paragraph("Tidak ada data transaksi.", cell_style))

    doc.build(elements)
    return buffer.getvalue()


def generate_spj_document(transaksi_row: pd.Series) -> bytes:
    if not REPORTLAB_AVAILABLE:
        return b""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph("SURAT PERTANGGUNGJAWABAN (SPJ)", styles["Title"]))
    elements.append(Paragraph("Kecamatan Candisari 2027", styles["Heading2"]))
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))
    data = [
        ["No Transaksi", str(transaksi_row.get("NO", "-"))],
        ["Tanggal Pengajuan", str(transaksi_row.get("TANGGAL PENGAJUAN", "-"))],
        ["PPTK", str(transaksi_row.get("PPTK", "-"))],
        ["Sub Kegiatan", str(transaksi_row.get("SUB KEGIATAN", "-"))],
        ["Kode Rekening", str(transaksi_row.get("KODE REKENING BELANJA", "-"))],
        ["Pengelompokan", str(transaksi_row.get("PENGELOMPOKAN BELANJA (#)", "-"))],
        ["Jenis Transaksi", str(transaksi_row.get("JENIS TRANSAKSI (UP/GU/LS)", "-"))],
        ["Nominal", format_rupiah(transaksi_row.get("NOMINAL", 0))],
        ["Uraian", str(transaksi_row.get("URAIAN", "-"))],
        ["Bukti Dukung", str(transaksi_row.get("BUKTI DUKUNG SPJ", "-"))],
        ["Status", str(transaksi_row.get("STATUS", "-"))],
    ]
    table = Table(data, colWidths=[120, 400])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(table)
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))
    elements.append(Paragraph("Dibuat oleh: ______________________", styles["Normal"]))
    elements.append(Paragraph("Disetujui oleh: ______________________", styles["Normal"]))
    doc.build(elements)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Label master
# ---------------------------------------------------------------------------
def get_subkegiatan_full(subkode: str, df: pd.DataFrame) -> str:
    if df.empty or subkode == "-":
        return subkode
    if "Kode Sub Kegiatan" not in df.columns:
        return str(subkode)
    row = df[df["Kode Sub Kegiatan"].astype(str) == str(subkode)]
    if row.empty:
        return str(subkode)
    nama = row.iloc[0].get("Sub Kegiatan", "")
    return f"{subkode} - {nama}" if nama else str(subkode)


def get_rekening_full(kode: str, df: pd.DataFrame) -> str:
    if df.empty or kode == "-":
        return kode
    if "Kode Rekening" not in df.columns:
        return str(kode)
    row = df[df["Kode Rekening"].astype(str) == str(kode)]
    if row.empty:
        return str(kode)
    uraian = row.iloc[0].get("Uraian Rekening", "")
    return f"{kode} — {uraian}" if uraian else str(kode)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def write_audit_log(action: str, table: str, record_id: str,
                    old_values: dict = None, new_values: dict = None, user: str = "Sistem") -> bool:
    try:
        df = load_sheet("AUDIT_LOG")
        if df.empty:
            df = pd.DataFrame(columns=[
                "WAKTU", "USER", "AKSI", "TABEL", "RECORD_ID", "OLD VALUES", "NEW VALUES"
            ])
        new_row = {
            "WAKTU": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "USER": user,
            "AKSI": action,
            "TABEL": table,
            "RECORD_ID": str(record_id),
            "OLD VALUES": str(old_values) if old_values else "",
            "NEW VALUES": str(new_values) if new_values else "",
        }
        updated = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        return update_sheet_data("AUDIT_LOG", updated)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Hak akses
# ---------------------------------------------------------------------------
def is_manager(peran: str) -> bool:
    return str(peran).upper() in ("ADMIN", "KASUBAG_PEK")


# ---------------------------------------------------------------------------
# Transaksi
# ---------------------------------------------------------------------------
def append_transaksi(new_data: dict, user: str = "Sistem"):
    df = load_sheet("TRANSAKSI")
    if df.empty:
        df = pd.DataFrame(columns=[
            "NO", "SUB KEGIATAN", "KODE REKENING BELANJA",
            "PENGELOMPOKAN BELANJA (#)", "URAIAN",
            "JENIS TRANSAKSI (UP/GU/LS)", "NOMINAL",
            "TANGGAL PENGAJUAN", "BUKTI DUKUNG SPJ", "PPTK", "STATUS",
            "DISETUJUI_OLEH", "TANGGAL_APPROVAL",
        ])
    next_no = 1
    if not df.empty and "NO" in df.columns:
        nums = pd.to_numeric(df["NO"], errors="coerce").dropna()
        if not nums.empty:
            next_no = int(nums.max()) + 1

    new_data["NO"] = next_no
    new_data["STATUS"] = "Draft"
    new_row = pd.DataFrame([new_data])
    updated = pd.concat([df, new_row], ignore_index=True)

    ok = update_sheet_data("TRANSAKSI", updated)
    if ok:
        write_audit_log("CREATE", "TRANSAKSI", str(next_no), None, new_data, user)
        return True, next_no
    return False, "Gagal menyimpan transaksi."


def update_transaksi_status(no: int, status: str, approved_by: str) -> bool:
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    old = df.loc[mask].iloc[0].to_dict()
    df.loc[mask, "STATUS"] = status
    df.loc[mask, "DISETUJUI_OLEH"] = approved_by
    df.loc[mask, "TANGGAL_APPROVAL"] = date.today().strftime("%d/%m/%Y")
    ok = update_sheet_data("TRANSAKSI", df)
    if ok:
        write_audit_log("UPDATE_STATUS", "TRANSAKSI", str(no), old,
                        {"STATUS": status, "DISETUJUI_OLEH": approved_by}, approved_by)
    return ok


def delete_transaksi(no: int) -> bool:
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    old = df.loc[mask].iloc[0].to_dict()
    df = df[~mask].reset_index(drop=True)
    ok = update_sheet_data("TRANSAKSI", df)
    if ok:
        write_audit_log("DELETE", "TRANSAKSI", str(no), old, None, "Sistem")
    return ok


def edit_transaksi(no: int, new_data: dict) -> bool:
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    old = df.loc[mask].iloc[0].to_dict()
    for col, val in new_data.items():
        if col in df.columns:
            df.loc[mask, col] = val
    ok = update_sheet_data("TRANSAKSI", df)
    if ok:
        write_audit_log("UPDATE", "TRANSAKSI", str(no), old, new_data, "Sistem")
    return ok


# ---------------------------------------------------------------------------
# Master CRUD
# ---------------------------------------------------------------------------
def _master_kegiatan_with_formula(df: pd.DataFrame) -> pd.DataFrame:
    """Susun ulang MASTER_SUB_KEGIATAN dengan formula kolom Sisa Pagu.

    Kolom Sisa Pagu di spreadsheet berisi formula, bukan angka statis. Saat
    aplikasi menulis ulang sheet, formula harus ditulis kembali agar tidak
    berubah menjadi nilai biasa.
    """
    columns = ["Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal", "Sisa Pagu"]
    df = df.copy().reset_index(drop=True)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns]
    df["Sisa Pagu"] = [
        f'=C{i + 2} - SUMIFS(TRANSAKSI!G:G, TRANSAKSI!B:B, A{i + 2} & "*", TRANSAKSI!K:K, "Disetujui")'
        for i in range(len(df))
    ]
    return df


def add_master_rekening(kode: str, uraian: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty:
        df = pd.DataFrame(columns=["Kode Rekening", "Uraian Rekening"])
    new_row = pd.DataFrame([{"Kode Rekening": kode, "Uraian Rekening": uraian}])
    updated = pd.concat([df, new_row], ignore_index=True)
    ok = update_sheet_data("MASTER_REKENING", updated)
    if ok:
        write_audit_log("CREATE", "MASTER_REKENING", kode, None,
                        {"Kode Rekening": kode, "Uraian Rekening": uraian}, user)
    return ok


def edit_master_rekening(idx: int, kode: str, uraian: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "Kode Rekening"] = kode
    df.at[idx, "Uraian Rekening"] = uraian
    ok = update_sheet_data("MASTER_REKENING", df)
    if ok:
        write_audit_log("UPDATE", "MASTER_REKENING", str(idx), old,
                        {"Kode Rekening": kode, "Uraian Rekening": uraian}, user)
    return ok


def delete_master_rekening(idx: int, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df = df.drop(index=idx).reset_index(drop=True)
    ok = update_sheet_data("MASTER_REKENING", df)
    if ok:
        write_audit_log("DELETE", "MASTER_REKENING", str(idx), old, None, user)
    return ok


def add_master_wilayah(nama: str, kode: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty:
        df = pd.DataFrame(columns=["Nama Wilayah", "Kode Wilayah"])
    new_row = pd.DataFrame([{"Nama Wilayah": nama, "Kode Wilayah": kode}])
    updated = pd.concat([df, new_row], ignore_index=True)
    ok = update_sheet_data("MASTER_WILAYAH", updated)
    if ok:
        write_audit_log("CREATE", "MASTER_WILAYAH", kode, None,
                        {"Nama Wilayah": nama, "Kode Wilayah": kode}, user)
    return ok


def edit_master_wilayah(idx: int, nama: str, kode: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "Nama Wilayah"] = nama
    df.at[idx, "Kode Wilayah"] = kode
    ok = update_sheet_data("MASTER_WILAYAH", df)
    if ok:
        write_audit_log("UPDATE", "MASTER_WILAYAH", str(idx), old,
                        {"Nama Wilayah": nama, "Kode Wilayah": kode}, user)
    return ok


def delete_master_wilayah(idx: int, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df = df.drop(index=idx).reset_index(drop=True)
    ok = update_sheet_data("MASTER_WILAYAH", df)
    if ok:
        write_audit_log("DELETE", "MASTER_WILAYAH", str(idx), old, None, user)
    return ok


def add_master_kegiatan(subkode: str, nama: str, pagu: float, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_SUB_KEGIATAN")
    if df.empty:
        df = pd.DataFrame(columns=["Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal", "Sisa Pagu"])
    new_row = pd.DataFrame([{
        "Kode Sub Kegiatan": subkode,
        "Sub Kegiatan": nama,
        "Pagu Awal": pagu,
        "Sisa Pagu": "",
    }])
    updated = pd.concat([df, new_row], ignore_index=True)
    updated = _master_kegiatan_with_formula(updated)
    ok = update_sheet_data("MASTER_SUB_KEGIATAN", updated)
    if ok:
        write_audit_log("CREATE", "MASTER_SUB_KEGIATAN", subkode, None,
                        {"Kode Sub Kegiatan": subkode, "Sub Kegiatan": nama, "Pagu Awal": pagu}, user)
    return ok


def edit_master_kegiatan(idx: int, subkode: str, nama: str, pagu: float, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_SUB_KEGIATAN")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "Kode Sub Kegiatan"] = subkode
    df.at[idx, "Sub Kegiatan"] = nama
    df.at[idx, "Pagu Awal"] = pagu
    df = _master_kegiatan_with_formula(df)
    ok = update_sheet_data("MASTER_SUB_KEGIATAN", df)
    if ok:
        write_audit_log("UPDATE", "MASTER_SUB_KEGIATAN", str(idx), old,
                        {"Kode Sub Kegiatan": subkode, "Sub Kegiatan": nama, "Pagu Awal": pagu}, user)
    return ok


def delete_master_kegiatan(idx: int, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_SUB_KEGIATAN")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df = df.drop(index=idx).reset_index(drop=True)
    df = _master_kegiatan_with_formula(df)
    ok = update_sheet_data("MASTER_SUB_KEGIATAN", df)
    if ok:
        write_audit_log("DELETE", "MASTER_SUB_KEGIATAN", str(idx), old, None, user)
    return ok


def add_master_user(user_name: str, password: str, nama: str, peran: str,
                    user: str = "Sistem") -> bool:
    df = load_sheet("PENGGUNA")
    if df.empty:
        df = pd.DataFrame(columns=["User Name", "Password", "Nama", "Peran"])
    new_row = pd.DataFrame([{
        "User Name": user_name,
        "Password": password,
        "Nama": nama,
        "Peran": peran,
    }])
    updated = pd.concat([df, new_row], ignore_index=True)
    ok = update_sheet_data("PENGGUNA", updated)
    if ok:
        write_audit_log("CREATE", "PENGGUNA", user_name, None,
                        {"User Name": user_name, "Nama": nama, "Peran": peran}, user)
    return ok


def edit_master_user(idx: int, user_name: str, password: str, nama: str,
                     peran: str, user: str = "Sistem") -> bool:
    df = load_sheet("PENGGUNA")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "User Name"] = user_name
    df.at[idx, "Password"] = password
    df.at[idx, "Nama"] = nama
    df.at[idx, "Peran"] = peran
    ok = update_sheet_data("PENGGUNA", df)
    if ok:
        write_audit_log("UPDATE", "PENGGUNA", str(idx), old,
                        {"User Name": user_name, "Nama": nama, "Peran": peran}, user)
    return ok


def delete_master_user(idx: int, user: str = "Sistem") -> bool:
    df = load_sheet("PENGGUNA")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df = df.drop(index=idx).reset_index(drop=True)
    ok = update_sheet_data("PENGGUNA", df)
    if ok:
        write_audit_log("DELETE", "PENGGUNA", str(idx), old, None, user)
    return ok
