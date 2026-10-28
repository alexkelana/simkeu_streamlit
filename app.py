"""
SIMKEU Kecamatan Candisari 2027 — Streamlit (terhubung Google Sheets)

Persiapan:
1. Buat service account di Google Cloud, unduh JSON key.
2. Share spreadsheet "DATABASE SIMKEU KECAMATAN CANDISARI 2027"
   ke email service account (minimal Editor untuk bisa tulis).
3. Buat file .streamlit/secrets.toml (lihat secrets.toml.example).
4. Jalankan: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import requests
import io
import secrets
import html
from datetime import date, datetime
from streamlit_gsheets import GSheetsConnection

try:
    from openpyxl import Workbook
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

# ===================== KONFIG =====================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1MMi0ABevTztyCfuzje6JLqNFeYt9octD_GKA0R2Xic8/edit"

st.set_page_config(
    page_title="SIMKEU Kecamatan Candisari 2027",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===================== STYLING UI MODERN (LIGHT THEME) =====================
# Deteksi tema dengan fallback aman
_theme_type = None
try:
    _theme_type = getattr(getattr(st, "context", None), "theme", None)
    _theme_type = getattr(_theme_type, "type", None) or None
except Exception:
    _theme_type = None

_is_dark = _theme_type == "dark"

# Warna untuk light theme (dominan)
_page_bg = "#0F172A" if _is_dark else "#F8FAFC"
_card_bg = "#0F172A" if _is_dark else "#FFFFFF"
_card_border = "#334155" if _is_dark else "#E2E8F0"
_card_shadow = "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)" if _is_dark else "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.04)"
_input_bg = "#1E293B" if _is_dark else "#FFFFFF"
_input_border = "#475569" if _is_dark else "#CBD5E1"
_input_focus = "#60A5FA" if _is_dark else "#3B82F6"
_input_shadow = "0 0 0 3px rgba(96, 165, 250, 0.3)" if _is_dark else "0 0 0 3px rgba(59, 130, 246, 0.3)"
_primary_btn = "#60A5FA" if _is_dark else "#2563EB"
_primary_btn_hover = "#3B82F6" if _is_dark else "#1D4ED8"
_table_header_bg = "#1E293B" if _is_dark else "#F1F5F9"
_table_header_text = "#F8FAFC" if _is_dark else "#0F172A"
_table_border = "#334155" if _is_dark else "#E2E8F0"
_table_row_even = "#1E293B" if _is_dark else "#FFFFFF"
_table_row_odd = "#0F172A" if _is_dark else "#F8FAFC"
_table_row_hover = "#1E3A8A" if _is_dark else "#E0F2FE"
_table_row_hover_text = "#FFFFFF" if _is_dark else "#0F172A"
_table_cell_text = "#F1F5F9" if _is_dark else "#334155"
_table_cell_border = "#334155" if _is_dark else "#E2E8F0"
_sidebar_bg = "#0B1120" if _is_dark else "#F1F5F9"
_sidebar_text = "#F1F5F9" if _is_dark else "#0F172A"

st.markdown(
    f"""
    <style>
    /* ============================================================
       HIDE STREAMLIT UI CHROME
       ============================================================ */
    .stDeployButton {{ display: none !important; }}
    footer {{ visibility: hidden !important; }}
    div[data-testid="stStatusWidget"] {{ display: none !important; }}

    /* ============================================================
       BACKGROUND UTAMA — Light Gray untuk kedalaman visual
       ============================================================ */
    .stApp {{
        background-color: {_page_bg} !important;
    }}

    /* ============================================================
       SIDEBAR — Soft contrast dengan body
       ============================================================ */
    [data-testid="stSidebar"] {{
        background-color: {_sidebar_bg} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: {_sidebar_text} !important;
    }}

    /* ============================================================
       KARTU KONTEN — Form, Container, dan Section berdimensi
       ============================================================ */
    div[data-testid="stForm"],
    div[data-testid="stContainer"],
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stElementContainer"]),
    .stMarkdownContainer > div {{
        background-color: {_card_bg} !important;
        border: 1px solid {_card_border} !important;
        border-radius: 10px !important;
        box-shadow: {_card_shadow} !important;
        padding: 1.5rem !important;
        margin-bottom: 1.5rem !important;
    }}

    /* ============================================================
       TOMBOL UNDUH — Modern, shadow, hover
       ============================================================ */
    div[data-testid="stDownloadButton"] > button {{
        background-color: {_primary_btn} !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 600 !important;
        box-shadow: {_card_shadow} !important;
        transition: all 0.25s ease-in-out !important;
    }}
    div[data-testid="stDownloadButton"] > button:hover {{
        background-color: {_primary_btn_hover} !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 7px 14px rgba(0, 0, 0, 0.15) !important;
    }}
    div[data-testid="stDownloadButton"] > button:active {{
        transform: translateY(1px) !important;
    }}

    /* ============================================================
       TOMBOL PRIMARI — Simpan, Setujui, dll.
       ============================================================ */
    .stButton > button[kind="primary"],
    .stButton > button {{
        background-color: {_primary_btn} !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.25rem !important;
        font-weight: 600 !important;
        box-shadow: {_card_shadow} !important;
        transition: all 0.2s ease !important;
    }}
    .stButton > button[kind="primary"]:hover,
    .stButton > button:hover {{
        background-color: {_primary_btn_hover} !important;
        transform: translateY(-1px) !important;
    }}

    /* ============================================================
       INPUT FORM — Putih, border halus, focus ring
       ============================================================ */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[data-baseweb="select"],
    .stNumberInput input,
    .stDateInput input {{
        background-color: {_input_bg} !important;
        border: 1px solid {_input_border} !important;
        border-radius: 6px !important;
        color: {_sidebar_text} !important;
        transition: all 0.2s ease !important;
    }}
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox div[data-baseweb="select"]:focus-within,
    .stNumberInput input:focus,
    .stDateInput input:focus {{
        border-color: {_input_focus} !important;
        box-shadow: {_input_shadow} !important;
        outline: none !important;
    }}

    /* ============================================================
       TABEL — Header, zebra striping, hover, kontras
       ============================================================ */
    div[data-testid="stDataFrame"] table,
    div[data-testid="stTable"] table {{
        border-collapse: separate !important;
        border-spacing: 0 !important;
        width: 100% !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }}
    div[data-testid="stDataFrame"] thead th,
    div[data-testid="stTable"] thead th,
    div[data-testid="stDataFrame"] [role="columnheader"],
    div[data-testid="stTable"] [role="columnheader"] {{
        background-color: {_table_header_bg} !important;
        color: {_table_header_text} !important;
        font-weight: 600 !important;
        padding: 12px 16px !important;
        text-align: left !important;
        border-bottom: 2px solid {_table_border} !important;
    }}
    div[data-testid="stDataFrame"] thead th *,
    div[data-testid="stTable"] thead th *,
    div[data-testid="stDataFrame"] [role="columnheader"] *,
    div[data-testid="stTable"] [role="columnheader"] * {{
        color: {_table_header_text} !important;
    }}
    div[data-testid="stDataFrame"] tbody tr:nth-child(even),
    div[data-testid="stTable"] tbody tr:nth-child(even) {{
        background-color: {_table_row_even} !important;
    }}
    div[data-testid="stDataFrame"] tbody tr:nth-child(odd),
    div[data-testid="stTable"] tbody tr:nth-child(odd) {{
        background-color: {_table_row_odd} !important;
    }}
    div[data-testid="stDataFrame"] tbody tr:hover,
    div[data-testid="stTable"] tbody tr:hover {{
        background-color: {_table_row_hover} !important;
        color: {_table_row_hover_text} !important;
        transition: background-color 0.2s ease !important;
    }}
    div[data-testid="stDataFrame"] td,
    div[data-testid="stTable"] td {{
        padding: 10px 16px !important;
        border-bottom: 1px solid {_table_cell_border} !important;
        color: {_table_cell_text} !important;
    }}
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"] {{
        margin-bottom: 2rem !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ===================== KONEKSI =====================
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

# Tandai apakah Google Sheets tersedia
_gsheets_available = None

def check_gsheets_available(force_refresh: bool = False) -> bool:
    """Cek apakah Google Sheets dapat diakses."""
    global _gsheets_available
    if force_refresh:
        _gsheets_available = None
    if _gsheets_available is not None:
        return _gsheets_available
    try:
        conn = get_conn()
        conn.read(spreadsheet=SPREADSHEET_URL, worksheet="TRANSAKSI", ttl=5)
        _gsheets_available = True
    except Exception:
        _gsheets_available = False
    return _gsheets_available

@st.cache_data(ttl=300)
def load_sheet(worksheet_name: str) -> pd.DataFrame:
    """Baca worksheet dari Google Sheets. Tampilkan error jika tidak dapat terkoneksi."""
    try:
        if check_gsheets_available():
            conn = get_conn()
            df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, ttl=30)
            if df is not None and not df.empty:
                return df
            return pd.DataFrame()
        else:
            st.error("❌ Tidak dapat terkoneksi ke Google Sheets. Pastikan service account sudah di-share ke spreadsheet dan .streamlit/secrets.toml sudah benar.")
            return pd.DataFrame()
    except Exception:
        st.error(f"❌ Gagal membaca sheet '{worksheet_name}'.")
        return pd.DataFrame()

def update_sheet_data(worksheet_name: str, df: pd.DataFrame) -> bool:
    """Tulis ulang seluruh data worksheet ke Google Sheets."""
    try:
        # Reset status koneksi agar pengecekan dilakukan ulang
        check_gsheets_available(force_refresh=True)
        if check_gsheets_available():
            conn = get_conn()
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, data=df)
            st.cache_resource.clear()
            st.cache_data.clear()  # Bersihkan cache data agar perubahan langsung terlihat
            return True
        else:
            st.error("❌ Tidak dapat terkoneksi ke Google Sheets. Data tidak dapat disimpan.")
            return False
    except Exception:
        st.error(f"❌ Gagal menyimpan ke sheet '{worksheet_name}'.")
        return False

def append_transaksi(new_data: dict, user: str = "Sistem"):
    """Tambahkan baris baru ke sheet TRANSAKSI."""
    try:
        conn = get_conn()
        df = load_sheet("TRANSAKSI")
        if df.empty:
            df = pd.DataFrame(columns=[
                "NO", "SUB KEGIATAN", "KODE REKENING BELANJA",
                "PENGELOMPOKAN BELANJA (#)", "URAIAN",
                "JENIS TRANSAKSI (UP/GU/LS)", "NOMINAL",
                "TANGGAL PENGAJUAN", "BUKTI DUKUNG SPJ", "PPTK", "STATUS"
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

        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="TRANSAKSI", data=updated)
        write_audit_log("CREATE", "TRANSAKSI", str(next_no), None, new_data, user)
        return True, next_no
    except Exception:
        st.error("❌ Gagal menyimpan transaksi ke Google Sheets.")
        return False, "Gagal menyimpan transaksi."

def send_telegram(message: str) -> bool:
    """Kirim notifikasi ke Telegram. Return True jika berhasil."""
    try:
        if "telegram" not in st.secrets:
            return False
        token = st.secrets["telegram"].get("bot_token")
        chat_id = st.secrets["telegram"].get("chat_id")
        if not token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
        }
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def check_login(username: str, password: str, df_pengguna: pd.DataFrame = None) -> bool:
    """Cek username + password dari Google Sheets (sheet PENGGUNA)."""
    try:
        if df_pengguna is None or df_pengguna.empty:
            return False

        # Cari kolom username dan password
        uname_col = None
        pass_col = None
        for col in df_pengguna.columns:
            col_lower = str(col).strip().lower()
            if col_lower in ("user_name", "username"):
                uname_col = col
            elif col_lower == "password":
                pass_col = col

        if not uname_col or not pass_col:
            return False

        user_row = df_pengguna[
            df_pengguna[uname_col].astype(str).str.strip().str.lower() == username.strip().lower()
        ]
        if user_row.empty:
            return False

        return secrets.compare_digest(
            str(user_row.iloc[0].get(pass_col, "")).strip(),
            password.strip(),
        )
    except Exception:
        return False

def find_username_column(df: pd.DataFrame) -> str | None:
    """Cari nama kolom user_name (case-insensitive)."""
    if df is None or df.empty:
        return None
    for col in df.columns:
        if str(col).strip().lower() in ("user_name", "username"):
            return col
    return None

# ===================== HELPER =====================
def format_rupiah(n):
    try:
        n = float(n)
        # Format dengan koma sebagai pemisah ribuan, lalu ganti menjadi titik (format Indonesia)
        if n < 0:
            return f"(Rp {abs(n):,.0f})".replace(",", ".")
        return f"Rp {n:,.0f}".replace(",", ".")
    except Exception:
        return "-"

def format_df_rupiah(df: pd.DataFrame) -> pd.DataFrame:
    """Format kolom nominal/angka dalam DataFrame ke format accounting rupiah."""
    if df is None or df.empty:
        return df
    df = df.copy()
    # Kolom yang berisi nominal/angka uang
    nominal_cols = [
        "NOMINAL", "nilai", "Nominal",
        "pagu_awal", "PAGU_AWAL", "Pagu Awal",
        "PAGU_BARU", "Pagu Baru",
        "SISA", "Sisa",
        "REALISASI", "Realisasi",
    ]
    for col in nominal_cols:
        if col in df.columns:
            df[col] = df[col].apply(format_rupiah)
    return df

# ===================== EXPORT EXCEL / PDF (Reporting & Notifikasi P2) =====================

def export_to_excel(df: pd.DataFrame, nama_file: str = "laporan_simkeu.xlsx") -> bytes:
    """Export DataFrame ke Excel (bytes)."""
    if not OPENPYXL_AVAILABLE:
        return b""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Laporan")
    return output.getvalue()

def export_to_pdf(
    df_transaksi: pd.DataFrame = None,
    df_kegiatan: pd.DataFrame = None,
    total_pagu: float = 0,
    total_realisasi: float = 0,
    sisa: float = 0,
    persen: float = 0,
    nominal_col: str = None,
    NOMINAL_COL_FOR_DASH: str = None,
    nama_file: str = "laporan_simkeu.pdf",
) -> bytes:
    """Export seluruh informasi dashboard ke PDF (landscape A4) dengan text wrapping."""
    if not REPORTLAB_AVAILABLE:
        return b""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25,
        title="Laporan SIMKEU Kecamatan Candisari 2027",
        author="SIMKEU",
    )
    styles = getSampleStyleSheet()

    # Style untuk sel tabel dengan text wrapping
    cell_style = ParagraphStyle(
        "CellStyle",
        parent=styles["Normal"],
        fontSize=7,
        leading=8,
        alignment=0,  # LEFT
    )
    cell_style_bold = ParagraphStyle(
        "CellStyleBold",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    header_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        alignment=0,
        textColor=colors.whitesmoke,
    )

    elements = []

    # ---------- Header ----------
    elements.append(Paragraph("LAPORAN TRANSAKSI SIMKEU", styles["Title"]))
    elements.append(Paragraph("Kecamatan Candisari 2027", styles["Heading2"]))
    elements.append(Paragraph(f"Tanggal Cetak: {date.today().strftime('%d/%m/%Y')}", styles["Normal"]))
    elements.append(Paragraph("Dibuat oleh: SIMKEU Sistem Manajemen Keuangan", styles["Normal"]))
    elements.append(Paragraph("<br/><br/>", styles["Normal"]))

    # ---------- Ringkasan Eksekutif ----------
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

    # ---------- 2. Perbandingan Target vs Realisasi per Sub Kegiatan ----------
    elements.append(Paragraph("2. Perbandingan Target vs Realisasi per Sub Kegiatan", styles["Heading3"]))
    if df_kegiatan is not None and not df_kegiatan.empty and nominal_col and NOMINAL_COL_FOR_DASH:
        df_compare = df_kegiatan.copy()
        df_compare["pagu_awal"] = pd.to_numeric(df_compare["pagu_awal"], errors="coerce").fillna(0)
        df_transaksi_calc = df_transaksi.copy() if df_transaksi is not None else pd.DataFrame()
        if not df_transaksi_calc.empty:
            df_transaksi_calc[NOMINAL_COL_FOR_DASH] = pd.to_numeric(
                df_transaksi_calc[NOMINAL_COL_FOR_DASH], errors="coerce"
            ).fillna(0)
            df_transaksi_calc["subkode"] = df_transaksi_calc["SUB KEGIATAN"].astype(str).str.split(" - ").str[0]
            realisasi_per_sub = (
                df_transaksi_calc.groupby("subkode")[NOMINAL_COL_FOR_DASH]
                .sum()
                .reset_index()
            )
            realisasi_per_sub.columns = ["subkegiatan", "realisasi"]
            df_compare = df_compare.merge(realisasi_per_sub, on="subkegiatan", how="left")
            df_compare["realisasi"] = df_compare["realisasi"].fillna(0)
        else:
            df_compare["realisasi"] = 0

        df_compare["sisa_pagu"] = df_compare["pagu_awal"] - df_compare["realisasi"]

        # Header tabel
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
                Paragraph(str(row.get("subkegiatan", "-")), cell_style),
                Paragraph(str(row.get("nama_kegiatan", "-")), cell_style),
                Paragraph(format_rupiah(row.get("pagu_awal", 0)), cell_style),
                Paragraph(format_rupiah(row.get("realisasi", 0)), cell_style),
                Paragraph(format_rupiah(row.get("sisa_pagu", 0)), cell_style),
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

    # ---------- 3. Daftar Transaksi ----------
    elements.append(Paragraph("3. Daftar Transaksi", styles["Heading3"]))
    if df_transaksi is not None and not df_transaksi.empty:
        df_show = df_transaksi.copy()
        # Format kolom nominal
        for col in ["NOMINAL", "nilai", "Nominal"]:
            if col in df_show.columns:
                df_show[col] = df_show[col].apply(format_rupiah)

        # Pilih kolom yang akan diekspor
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
            row_data = []
            for c in df_show.columns:
                row_data.append(Paragraph(str(row.get(c, "-")), cell_style))
            pdf_data.append(row_data)

        # Hitung lebar kolom dinamis
        n_cols = len(df_show.columns)
        available_width = 792  # landscape A4 minus margins
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

# ===================== CETAK SPJ / SURAT (P3) =====================

def is_manager(peran: str) -> bool:
    return str(peran).upper() in ("ADMIN", "KASUBAG_PEK")

def generate_spj_document(transaksi_row: pd.Series) -> bytes:
    """Generate dokumen SPJ (Surat Pertanggungjawaban) dalam format PDF."""
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

def get_subkegiatan_full(subkode: str, df: pd.DataFrame) -> str:
    """Label lengkap: kode - nama."""
    if df.empty or subkode == "-":
        return subkode
    row = df[df["subkegiatan"] == subkode]
    if row.empty:
        return subkode
    nama = row.iloc[0].get("nama_kegiatan", "")
    if nama:
        return f"{subkode} - {nama}"
    return str(subkode)

def get_rekening_full(kode: str, df: pd.DataFrame) -> str:
    """Label lengkap: kode — uraian."""
    if df.empty or kode == "-":
        return kode
    row = df[df["kode_rekening"] == kode]
    if row.empty:
        return kode
    uraian = row.iloc[0].get("uraian_rekening", "")
    if uraian:
        return f"{kode} — {uraian}"
    return str(kode)

# --- Master Rekening (pilot CRUD) ---
def add_master_rekening(kode: str, uraian: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty:
        df = pd.DataFrame(columns=["kode_rekening", "uraian_rekening"])
    new_row = pd.DataFrame([{"kode_rekening": kode, "uraian_rekaning": uraian}])
    updated = pd.concat([df, new_row], ignore_index=True)
    ok = update_sheet_data("MASTER_REKENING", updated)
    if ok:
        write_audit_log("CREATE", "MASTER_REKENING", kode, None, {"kode_rekening": kode, "uraian_rekening": uraian}, user)
    return ok

def edit_master_rekening(idx: int, kode: str, uraian: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "kode_rekening"] = kode
    df.at[idx, "uraian_rekening"] = uraian
    ok = update_sheet_data("MASTER_REKENING", df)
    if ok:
        write_audit_log("UPDATE", "MASTER_REKENING", str(idx), old, {"kode_rekening": kode, "uraian_rekening": uraian}, user)
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

# --- Master Wilayah ---
def add_master_wilayah(nama: str, kode: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty:
        df = pd.DataFrame(columns=["nama_wilayah", "kode_wilayah"])
    new_row = pd.DataFrame([{"nama_wilayah": nama, "kode_wilayah": kode}])
    updated = pd.concat([df, new_row], ignore_index=True)
    ok = update_sheet_data("MASTER_WILAYAH", updated)
    if ok:
        write_audit_log("CREATE", "MASTER_WILAYAH", kode, None, {"nama_wilayah": nama, "kode_wilayah": kode}, user)
    return ok

def edit_master_wilayah(idx: int, nama: str, kode: str, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "nama_wilayah"] = nama
    df.at[idx, "kode_wilayah"] = kode
    ok = update_sheet_data("MASTER_WILAYAH", df)
    if ok:
        write_audit_log("UPDATE", "MASTER_WILAYAH", str(idx), old, {"nama_wilayah": nama, "kode_wilayah": kode}, user)
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

# --- Master Kegiatan ---
def add_master_kegiatan(subkode: str, nama: str, pagu: float, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_KEGIATAN")
    if df.empty:
        df = pd.DataFrame(columns=["subkegiatan", "nama_kegiatan", "pagu_awal"])
    new_row = pd.DataFrame([{"subkegiatan": subkode, "nama_kegiatan": nama, "pagu_awal": pagu}])
    updated = pd.concat([df, new_row], ignore_index=True)
    ok = update_sheet_data("MASTER_KEGIATAN", updated)
    if ok:
        write_audit_log("CREATE", "MASTER_KEGIATAN", subkode, None, {"subkegiatan": subkode, "nama_kegiatan": nama, "pagu_awal": pagu}, user)
    return ok

def edit_master_kegiatan(idx: int, subkode: str, nama: str, pagu: float, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_KEGIATAN")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "subkegiatan"] = subkode
    df.at[idx, "nama_kegiatan"] = nama
    df.at[idx, "pagu_awal"] = pagu
    ok = update_sheet_data("MASTER_KEGIATAN", df)
    if ok:
        write_audit_log("UPDATE", "MASTER_KEGIATAN", str(idx), old, {"subkegiatan": subkode, "nama_kegiatan": nama, "pagu_awal": pagu}, user)
    return ok

def delete_master_kegiatan(idx: int, user: str = "Sistem") -> bool:
    df = load_sheet("MASTER_KEGIATAN")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df = df.drop(index=idx).reset_index(drop=True)
    ok = update_sheet_data("MASTER_KEGIATAN", df)
    if ok:
        write_audit_log("DELETE", "MASTER_KEGIATAN", str(idx), old, None, user)
    return ok

# --- Master Pengguna (User Management via UI) ---
def add_master_user(user_name: str, password: str, nama: str, peran: str, user: str = "Sistem") -> bool:
    df = load_sheet("PENGGUNA")
    if df.empty:
        df = pd.DataFrame(columns=["user_name", "password", "nama", "peran"])
    new_row = pd.DataFrame([{
        "user_name": user_name,
        "password": password,
        "nama": nama,
        "peran": peran
    }])
    updated = pd.concat([df, new_row], ignore_index=True)
    ok = update_sheet_data("PENGGUNA", updated)
    if ok:
        write_audit_log("CREATE", "PENGGUNA", user_name, None, {"user_name": user_name, "nama": nama, "peran": peran}, user)
    return ok

def edit_master_user(idx: int, user_name: str, password: str, nama: str, peran: str, user: str = "Sistem") -> bool:
    df = load_sheet("PENGGUNA")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    old = df.iloc[idx].to_dict()
    df.at[idx, "user_name"] = user_name
    df.at[idx, "password"] = password
    df.at[idx, "nama"] = nama
    df.at[idx, "peran"] = peran
    ok = update_sheet_data("PENGGUNA", df)
    if ok:
        write_audit_log("UPDATE", "PENGGUNA", str(idx), old, {"user_name": user_name, "nama": nama, "peran": peran}, user)
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

# ===================== AUDIT LOG (P3) =====================

def write_audit_log(action: str, table: str, record_id: str, old_values: dict = None, new_values: dict = None, user: str = "Sistem") -> bool:
    """Catat aksi create/update/delete ke sheet AUDIT_LOG."""
    try:
        df = load_sheet("AUDIT_LOG")
        if df.empty:
            df = pd.DataFrame(columns=[
                "WAKTU", "USER", "AKSI", "TABEL", "RECORD_ID", "OLD_VALUES", "NEW_VALUES"
            ])
        new_row = {
            "WAKTU": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "USER": user,
            "AKSI": action,
            "TABEL": table,
            "RECORD_ID": str(record_id),
            "OLD_VALUES": str(old_values) if old_values else "",
            "NEW_VALUES": str(new_values) if new_values else "",
        }
        updated = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        return update_sheet_data("AUDIT_LOG", updated)
    except Exception:
        return False

# ===================== BACKEND: TRANSAKSI APPROVAL & EDIT/HAPUS =====================

def update_transaksi_status(no: int, status: str, approved_by: str) -> bool:
    """Ubah status transaksi (Draft / Diajuan / Disetujui / Ditolak)."""
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
        write_audit_log("UPDATE_STATUS", "TRANSAKSI", str(no), old, {"STATUS": status, "DISETUJUI_OLEH": approved_by}, approved_by)
    return ok

def delete_transaksi(no: int) -> bool:
    """Hapus transaksi berdasarkan nomor."""
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
    """Edit transaksi yang sudah ada berdasarkan nomor."""
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

# ===================== LOAD DATA =====================

# Opsi A: Lazy Loading — data hanya dimuat saat menu membutuhkannya.
# load_sheet() sudah dilengkapi @st.cache_data(ttl=300) sehingga
# pemanggilan berulang dalam satu sesi tidak mengakses Google Sheets ulang.

def get_df(worksheet_name: str) -> pd.DataFrame:
    """Helper lazy loading: ambil DataFrame dari sheet dengan cache."""
    return load_sheet(worksheet_name)

# Inisialisasi variabel kosong (akan diisi saat menu membutuhkan)
df_pengguna = pd.DataFrame()
df_wilayah = pd.DataFrame()
df_rekening = pd.DataFrame()
df_kegiatan = pd.DataFrame()
df_transaksi = pd.DataFrame()
df_perubahan = pd.DataFrame()

# ===================== LOGIN =====================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None

# Lazy load data PENGGUNA untuk login
df_pengguna = get_df("PENGGUNA")

if not st.session_state.logged_in:
    # CSS responsif untuk form login — fleksibel di HP & Desktop (tanpa kekecilan/kepotongan)
    st.markdown(
        """
        <style>
        div[data-testid="stForm"] {
            width: 90vw;
            max-width: 450px;
            min-width: 280px;
            margin: 2rem auto;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>SIMKEU 2027</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Kecamatan Candisari</p>", unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("User Name", placeholder="Masukkan username")
            password = st.text_input("Password", type="password", placeholder="Masukkan password")
            
            # PERBAIKAN: Gunakan use_container_width=True agar tombol memenuhi lebarnya form
            submitted = st.form_submit_button("Masuk", type="primary", use_container_width=True)
            
            if submitted:
                username_clean = username.strip().lower()
                password_clean = password.strip()
                
                # Validasi panjang input
                if not username_clean or not password_clean:
                    st.error("User Name dan password tidak boleh kosong.")
                elif len(username_clean) > 100 or len(password_clean) > 100:
                    st.error("Input terlalu panjang.")
                elif check_login(username_clean, password_clean, df_pengguna):
                    uname_col = find_username_column(df_pengguna)
                    if not df_pengguna.empty and uname_col:
                        user_row = df_pengguna[
                            df_pengguna[uname_col].astype(str).str.strip().str.lower() == username_clean
                        ]
                        if not user_row.empty:
                            st.session_state.current_user = user_row.iloc[0].to_dict()
                            st.session_state.logged_in = True
                            
                            # Inisialisasi filter PPTK otomatis setelah login
                            user_peran_login = str(user_row.iloc[0].get("peran", "")).upper()
                            if user_peran_login == "PPTK":
                                nama_login = str(user_row.iloc[0].get("nama", "")).strip()
                                uname_login = str(user_row.iloc[0].get("user_name") or user_row.iloc[0].get("username", "")).strip()
                                st.session_state.pptk_filter = f"{nama_login} ({uname_login})" if uname_login else nama_login
                            else:
                                st.session_state.pptk_filter = "Semua PPTK"
                            
                            st.rerun()
                        else:
                            st.error("User Name tidak ditemukan di sheet PENGGUNA.")
                    else:
                        st.error("Sheet PENGGUNA tidak memiliki kolom user_name atau kosong.")
                else:
                    st.error("User Name atau password salah.")

    st.stop()

current_user = st.session_state.current_user

# ===================== SIDEBAR =====================
with st.sidebar:
    st.title("SIMKEU 2027")
    st.caption("Kecamatan Candisari")
    st.divider()
    st.text(f"{current_user.get('nama', '-')}")
    st.caption(str(current_user.get("peran", "")).replace("_", " "))
    uname = current_user.get("user_name") or current_user.get("username") or "-"
    st.caption(f"User: {uname}")
    st.divider()
    menu = st.radio(
        "Menu",
        ["Transaksi", "Dashboard", "Perubahan Pagu", "Master Data"],
        index=0,
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Terhubung ke Google Sheets")

    # ---- Filter PPTK (di-set otomatis saat login) ----
    user_peran = str(current_user.get("peran", "")).upper()
    pptk_filter = st.session_state.get("pptk_filter", "Semua PPTK")
    if pptk_filter and pptk_filter != "Semua PPTK":
        st.caption(f"🔒 Data ditampilkan untuk: **{pptk_filter}**")
    else:
        st.caption("Data ditampilkan untuk: **Semua PPTK**")

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.rerun()
    if st.button("Refresh data"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

# ===================== TRANSAKSI =====================
if menu == "Transaksi":
    # Lazy load data yang dibutuhkan menu Transaksi
    df_rekening = get_df("MASTER_REKENING")
    df_kegiatan = get_df("MASTER_KEGIATAN")
    df_transaksi = get_df("TRANSAKSI")
    df_pengguna = get_df("PENGGUNA")
    st.header("Input Transaksi")

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

    rekening_opts = []
    if not df_rekening.empty and "kode_rekening" in df_rekening.columns:
        rekening_opts = df_rekening["kode_rekening"].dropna().tolist()

    sub_opts = []
    if not df_kegiatan.empty and "subkegiatan" in df_kegiatan.columns:
        sub_opts = df_kegiatan["subkegiatan"].dropna().tolist()

    with st.form("form_transaksi"):
        tgl = st.date_input("Tanggal Pengajuan", value=date.today())

        subkegiatan = st.selectbox(
            "Sub Kegiatan",
            options=sub_opts if sub_opts else ["-"],
            format_func=lambda x: get_subkegiatan_full(x, df_kegiatan)
        )

        rekening = st.selectbox(
            "Kode Rekening Belanja",
            options=rekening_opts if rekening_opts else ["-"],
            format_func=lambda x: get_rekening_full(x, df_rekening)
        )

        pengelompokan = st.text_input("Pengelompokan Belanja (#)")
        jenis = st.selectbox("Jenis Transaksi", ["UP/GU", "LS"])
        nominal = st.number_input("Nominal (Rp)", min_value=0, step=1000)
        uraian = st.text_area("Uraian", height=100)
        bukti = st.text_input("Bukti Dukung SPJ (tautan / nomor)")

        if st.form_submit_button("Simpan Transaksi", type="primary"):
            if nominal <= 0 or subkegiatan == "-" or rekening == "-":
                st.error("Sub Kegiatan, Kode Rekening, dan Nominal wajib diisi dengan benar.")
            else:
                uname = current_user.get("user_name") or current_user.get("username") or ""
                pptk = f"{current_user.get('nama', '')} ({uname})"
                new_data = {
                    "SUB KEGIATAN": get_subkegiatan_full(subkegiatan, df_kegiatan),
                    "KODE REKENING BELANJA": rekening,
                    "PENGELOMPOKAN BELANJA (#)": pengelompokan or "",
                    "URAIAN": uraian or "",
                    "JENIS TRANSAKSI (UP/GU/LS)": jenis,
                    "NOMINAL": nominal,
                    "TANGGAL PENGAJUAN": tgl.strftime("%d/%m/%Y"),
                    "BUKTI DUKUNG SPJ": bukti or "",
                    "PPTK": pptk,
                }
                success, result = append_transaksi(new_data, user=current_user.get("nama", "Sistem"))
                if success:
                    pesan = (
                        f"📌 Transaksi Baru SIMKEU\n"
                        f"No: {result}\n"
                        f"PPTK: {pptk}\n"
                        f"Sub Kegiatan: {new_data['SUB KEGIATAN']}\n"
                        f"Rekening: {rekening}\n"
                        f"Jenis: {jenis}\n"
                        f"Nominal: {format_rupiah(nominal)}\n"
                        f"Tanggal: {new_data['TANGGAL PENGAJUAN']}\n"
                        f"Uraian: {uraian or '-'}"
                    )
                    telegram_ok = send_telegram(pesan)
                    st.session_state.simpan_status = {
                        "success": True,
                        "message": f"✅ Transaksi berhasil disimpan. Nomor: {result}",
                        "telegram_ok": telegram_ok
                    }
                    st.cache_resource.clear()
                    st.rerun()
                else:
                    st.session_state.simpan_status = {
                        "success": False,
                        "message": f"❌ Gagal menyimpan: {result}"
                    }
                    st.rerun()

    st.divider()
    st.subheader("Daftar Transaksi")
    if not df_transaksi.empty:
        # ---- Filter & Pencarian (Frontend & UI P2) ----
        with st.expander("🔍 Filter & Pencarian Transaksi", expanded=False):
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                filter_tanggal = st.text_input("Tanggal (DD/MM/YYYY)", placeholder="contoh: 01/01/2027")
            with f_col2:
                filter_sub = st.text_input("Sub Kegiatan", placeholder="kata kunci...")
            with f_col3:
                filter_rek = st.text_input("Kode Rekening", placeholder="kata kunci...")
            with f_col4:
                filter_status = st.selectbox("Status", ["Semua", "Draft", "Diajuan", "Disetujui", "Ditolak"])

        df_show = df_transaksi.copy()
        if "STATUS" not in df_show.columns:
            df_show["STATUS"] = "Draft"

        # Terapkan filter
        if filter_tanggal:
            df_show = df_show[df_show["TANGGAL PENGAJUAN"].astype(str).str.contains(filter_tanggal, case=False, na=False)]
        if filter_sub:
            df_show = df_show[df_show["SUB KEGIATAN"].astype(str).str.contains(filter_sub, case=False, na=False)]
        if filter_rek:
            df_show = df_show[df_show["KODE REKENING BELANJA"].astype(str).str.contains(filter_rek, case=False, na=False)]
        if filter_status != "Semua":
            df_show = df_show[df_show["STATUS"] == filter_status]

        # Terapkan filter PPTK
        pptk_filter = st.session_state.get("pptk_filter")
        if pptk_filter and pptk_filter != "Semua PPTK":
            df_show = df_show[df_show["PPTK"].astype(str) == pptk_filter]

        st.caption(f"Menampilkan {len(df_show)} dari {len(df_transaksi)} transaksi")
        st.dataframe(format_df_rupiah(df_show), hide_index=True)
    else:
        st.info("Belum ada transaksi.")

# ===================== DASHBOARD =====================
elif menu == "Dashboard":
    # Lazy load data yang dibutuhkan menu Dashboard
    df_kegiatan = get_df("MASTER_KEGIATAN")
    df_transaksi = get_df("TRANSAKSI")
    
    # Terapkan filter PPTK ke data transaksi
    pptk_filter = st.session_state.get("pptk_filter")
    user_peran = str(current_user.get("peran", "")).upper()
    if pptk_filter and pptk_filter != "Semua PPTK":
        df_transaksi = df_transaksi[df_transaksi["PPTK"].astype(str) == pptk_filter]
        
        # Untuk PPTK: filter df_kegiatan hanya ke sub-kegiatan yang memiliki transaksi dari PPTK tersebut
        if user_peran not in ("ADMIN", "KASUBAG_PEK") and not df_transaksi.empty and "SUB KEGIATAN" in df_transaksi.columns and "subkegiatan" in df_kegiatan.columns:
            subkode_terpakai = df_transaksi["SUB KEGIATAN"].astype(str).str.split(" - ").str[0].unique().tolist()
            df_kegiatan = df_kegiatan[df_kegiatan["subkegiatan"].isin(subkode_terpakai)]
    
    st.header("Dashboard")

    total_pagu = 0
    if not df_kegiatan.empty and "pagu_awal" in df_kegiatan.columns:
        total_pagu = pd.to_numeric(df_kegiatan["pagu_awal"], errors="coerce").fillna(0).sum()

    total_realisasi = 0
    nominal_col = None
    for col in ["NOMINAL", "nilai", "Nominal"]:
        if col in df_transaksi.columns:
            nominal_col = col
            break
    NOMINAL_COL_FOR_DASH = nominal_col  # alias untuk visualisasi
    if nominal_col and not df_transaksi.empty:
        total_realisasi = pd.to_numeric(df_transaksi[nominal_col], errors="coerce").fillna(0).sum()

    sisa = total_pagu - total_realisasi
    persen = (total_realisasi / total_pagu * 100) if total_pagu else 0

    # ---- KPI Row — 4 card metrik ----------
    with st.container(horizontal=True):
        st.metric("Jumlah Sub Kegiatan", len(df_kegiatan), border=True)
        st.metric("Total Pagu", format_rupiah(total_pagu), border=True)
        st.metric("Realisasi", format_rupiah(total_realisasi), border=True)
        st.metric("Sisa Pagu", format_rupiah(sisa), delta=f"{persen:.1f}% terpakai", border=True)

    # ---- Tombol Export (Reporting & Notifikasi P2) ----
    st.divider()
    st.markdown("### Export Laporan")
    e_col1, e_col2 = st.columns(2)
    df_export = df_transaksi if not df_transaksi.empty else pd.DataFrame()
    with e_col1:
        if OPENPYXL_AVAILABLE:
            xlsx_bytes = export_to_excel(df_export)
            st.download_button(
                label="⬇️ Unduh Excel",
                data=xlsx_bytes,
                file_name="laporan_simkeu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("Library openpyxl tidak tersedia.")
    with e_col2:
        if REPORTLAB_AVAILABLE:
            pdf_bytes = export_to_pdf(
                df_transaksi=df_export,
                df_kegiatan=df_kegiatan,
                total_pagu=total_pagu,
                total_realisasi=total_realisasi,
                sisa=sisa,
                persen=persen,
                nominal_col=nominal_col,
                NOMINAL_COL_FOR_DASH=NOMINAL_COL_FOR_DASH,
            )
            st.download_button(
                label="⬇️ Unduh PDF",
                data=pdf_bytes,
                file_name="laporan_simkeu.pdf",
                mime="application/pdf",
            )
        else:
            st.info("Library reportlab tidak tersedia.")

    st.divider()
    st.subheader("Realisasi per Sub Kegiatan")
    if not df_kegiatan.empty and not df_transaksi.empty and nominal_col:
        df_transaksi_copy = df_transaksi.copy()
        df_transaksi_copy[NOMINAL_COL_FOR_DASH] = pd.to_numeric(df_transaksi_copy[nominal_col], errors="coerce").fillna(0)
        # Gabungkan nama sub kegiatan
        df_merge = df_kegiatan[["subkegiatan", "nama_kegiatan"]].copy() if "subkegiatan" in df_kegiatan.columns else pd.DataFrame()
        if not df_merge.empty and "SUB KEGIATAN" in df_transaksi_copy.columns:
            # Ambil kode sub kegiatan dari kolom "SUB KEGIATAN" (format: "KODE - Nama")
            df_transaksi_copy["subkode"] = df_transaksi_copy["SUB KEGIATAN"].astype(str).str.split(" - ").str[0]
            realisasi_per_sub = df_transaksi_copy.groupby("subkode")[NOMINAL_COL_FOR_DASH].sum().reset_index()
            realisasi_per_sub.columns = ["subkegiatan", "realisasi"]
            chart_df = realisasi_per_sub.merge(df_merge, on="subkegiatan", how="left")
            chart_df["label"] = chart_df["subkegiatan"] + " — " + chart_df["nama_kegiatan"].fillna("")
            st.bar_chart(chart_df.set_index("label")["realisasi"])
        else:
            st.info("Data sub kegiatan tidak cukup untuk visualisasi.")
    else:
        st.info("Belum ada data untuk divisualisasikan.")

    # ---- Peringatan Pagu Habis (Reporting & Notifikasi P2) ----
    if total_pagu > 0 and persen >= 80:
        st.warning(f"⚠️ Peringatan: Realisasi telah mencapai {persen:.1f}% dari pagu total!")
        try:
            pesan_pagu = (
                f"🚨 PERINGATAN PAGU HABIS\n"
                f"Realisasi: {format_rupiah(total_realisasi)} / {format_rupiah(total_pagu)}\n"
                f"Penggunaan: {persen:.1f}%\n"
                f"Sisa: {format_rupiah(sisa)}"
            )
            send_telegram(pesan_pagu)
        except Exception:
            pass

    st.divider()
    st.subheader("Sub Kegiatan")
    if not df_kegiatan.empty:
        df_kegiatan_display = df_kegiatan.copy()
        if not df_transaksi.empty and nominal_col:
            df_transaksi_copy = df_transaksi.copy()
            df_transaksi_copy[NOMINAL_COL_FOR_DASH] = pd.to_numeric(
                df_transaksi_copy[nominal_col], errors="coerce"
            ).fillna(0)
            df_transaksi_copy["subkode"] = df_transaksi_copy["SUB KEGIATAN"].astype(str).str.split(" - ").str[0]
            realisasi_per_sub = (
                df_transaksi_copy.groupby("subkode")[NOMINAL_COL_FOR_DASH]
                .sum()
                .reset_index()
            )
            realisasi_per_sub.columns = ["subkegiatan", "realisasi"]
            df_kegiatan_display = df_kegiatan_display.merge(
                realisasi_per_sub, on="subkegiatan", how="left"
            )
            df_kegiatan_display["realisasi"] = df_kegiatan_display["realisasi"].fillna(0)
            df_kegiatan_display["sisa_pagu"] = (
                pd.to_numeric(df_kegiatan_display["pagu_awal"], errors="coerce").fillna(0)
                - df_kegiatan_display["realisasi"]
            )
            df_kegiatan_display = df_kegiatan_display[
                ["subkegiatan", "nama_kegiatan", "pagu_awal", "realisasi", "sisa_pagu"]
            ]
            df_kegiatan_display.columns = [
                "Kode", "Nama Kegiatan", "Pagu Awal", "Realisasi", "Sisa Pagu"
            ]
            for col in ["Pagu Awal", "Realisasi", "Sisa Pagu"]:
                df_kegiatan_display[col] = df_kegiatan_display[col].apply(format_rupiah)
        else:
            df_kegiatan_display = format_df_rupiah(df_kegiatan)
        st.dataframe(df_kegiatan_display, hide_index=True)
    else:
        st.info("Belum ada data sub kegiatan.")

    st.divider()
    st.subheader("Transaksi Terbaru")
    if not df_transaksi.empty:
        st.dataframe(format_df_rupiah(df_transaksi), hide_index=True)
    else:
        st.info("Belum ada transaksi.")

    # ===================== FITUR KASUBAG (Hanya ADMIN / KASUBAG_PEK) =====================
    if is_manager(current_user.get("peran", "")):
        st.divider()
        st.markdown("## Dashboard Manajerial (Kasubag)")

        # ---- 1. Ringkasan Realisasi per PPTK ----
        st.subheader("Ringkasan Realisasi per PPTK")
        if not df_transaksi.empty and nominal_col and "PPTK" in df_transaksi.columns:
            df_transaksi_copy = df_transaksi.copy()
            df_transaksi_copy[NOMINAL_COL_FOR_DASH] = pd.to_numeric(
                df_transaksi_copy[nominal_col], errors="coerce"
            ).fillna(0)
            df_pptk_summary = (
                df_transaksi_copy.groupby("PPTK")[NOMINAL_COL_FOR_DASH]
                .sum()
                .reset_index()
            )
            df_pptk_summary.columns = ["PPTK", "Realisasi"]
            df_pptk_summary = df_pptk_summary.sort_values("Realisasi", ascending=False)
            df_pptk_summary["Realisasi"] = df_pptk_summary["Realisasi"].apply(format_rupiah)
            st.dataframe(df_pptk_summary, hide_index=True)
        else:
            st.info("Belum ada data transaksi untuk ditampilkan per PPTK.")

        # ---- 2. Peringatan Pagu Melebihi (≥90%) ----
        st.subheader("Peringatan Pagu Melebihi (≥90%)")
        if not df_kegiatan.empty and not df_transaksi.empty and "pagu_awal" in df_kegiatan.columns and nominal_col:
            df_kegiatan_copy = df_kegiatan.copy()
            df_kegiatan_copy["pagu_awal"] = pd.to_numeric(df_kegiatan_copy["pagu_awal"], errors="coerce").fillna(0)
            df_transaksi_copy = df_transaksi.copy()
            df_transaksi_copy[NOMINAL_COL_FOR_DASH] = pd.to_numeric(
                df_transaksi_copy[nominal_col], errors="coerce"
            ).fillna(0)
            # Ambil kode sub kegiatan dari kolom "SUB KEGIATAN" (format: "KODE - Nama")
            df_transaksi_copy["subkode"] = df_transaksi_copy["SUB KEGIATAN"].astype(str).str.split(" - ").str[0]
            realisasi_per_sub = (
                df_transaksi_copy.groupby("subkode")[NOMINAL_COL_FOR_DASH]
                .sum()
                .reset_index()
            )
            realisasi_per_sub.columns = ["subkegiatan", "realisasi"]
            df_alert = df_kegiatan_copy.merge(realisasi_per_sub, on="subkegiatan", how="left")
            df_alert["realisasi"] = df_alert["realisasi"].fillna(0)
            df_alert["persen"] = (df_alert["realisasi"] / df_alert["pagu_awal"] * 100).fillna(0)
            df_over = df_alert[df_alert["persen"] >= 90].copy()
            if not df_over.empty:
                df_over_display = df_over[["subkegiatan", "nama_kegiatan", "pagu_awal", "realisasi", "persen"]].copy()
                df_over_display.columns = ["Kode", "Nama Kegiatan", "Pagu", "Realisasi", "% Pakai"]
                df_over_display["Pagu"] = df_over_display["Pagu"].apply(format_rupiah)
                df_over_display["Realisasi"] = df_over_display["Realisasi"].apply(format_rupiah)
                df_over_display["% Pakai"] = df_over_display["% Pakai"].apply(lambda x: f"{x:.1f}%")
                st.warning(f"⚠️ Ditemukan {len(df_over_display)} sub kegiatan yang pagunya telah mencapai ≥90%!")
                st.dataframe(df_over_display, hide_index=True)
            else:
                st.info("✅ Tidak ada sub kegiatan yang melebihi 90% pagu.")
        else:
            st.info("Data pagu atau transaksi tidak cukup untuk peringatan over budget.")

        # ---- 3. Antrian Menunggu Approval ----
        st.subheader("Antrian Transaksi Menunggu Approval")
        if not df_transaksi.empty and "STATUS" in df_transaksi.columns:
            df_pending = df_transaksi[df_transaksi["STATUS"].astype(str).isin(["Draft", "Menunggu Approval"])]
            if not df_pending.empty:
                df_pending_display = df_pending[["NO", "SUB KEGIATAN", "PPTK", "NOMINAL", "TANGGAL PENGAJUAN", "STATUS", "URAIAN"]].copy()
                df_pending_display["NOMINAL"] = df_pending_display["NOMINAL"].apply(format_rupiah)
                st.dataframe(df_pending_display, hide_index=True)
                st.markdown("### Aksi Approval")
                col_app1, col_app2 = st.columns(2)
                with col_app1:
                    app_no = st.number_input("Nomor Transaksi", min_value=1, step=1, key="app_no")
                with col_app2:
                    app_aksi = st.selectbox("Aksi", ["Setujui", "Tolak", "Edit", "Hapus", "Cetak SPJ"], key="app_aksi")

                if app_aksi in ("Setujui", "Tolak"):
                    if st.button(f"{app_aksi} Transaksi", type="primary"):
                        pptk_nama = current_user.get("nama", "Admin")
                        status_baru = "Disetujui" if app_aksi == "Setujui" else "Ditolak"
                        ok = update_transaksi_status(int(app_no), status_baru, pptk_nama)
                        if ok:
                            st.success(f"Transaksi No {app_no} berhasil {status_baru.lower()}.")
                            st.rerun()
                        else:
                            st.error("Gagal memproses approval.")

                elif app_aksi == "Edit":
                    with st.form("form_edit_dashboard"):
                        new_uraian = st.text_input("Uraian baru")
                        new_nominal = st.number_input("Nominal baru", min_value=0, step=1000)
                        if st.form_submit_button("Simpan Perubahan"):
                            new_data = {"URAIAN": new_uraian, "NOMINAL": new_nominal}
                            ok = edit_transaksi(int(app_no), new_data)
                            if ok:
                                st.success(f"Transaksi No {app_no} berhasil diupdate.")
                                st.rerun()
                            else:
                                st.error("Gagal mengedit transaksi.")

                elif app_aksi == "Hapus":
                    st.warning("⚠️ Aksi ini tidak dapat dibatalkan.")
                    konfirmasi = st.checkbox("Saya yakin ingin menghapus transaksi ini.", key="hapus_conf")
                    if st.button("Hapus Transaksi", type="secondary"):
                        if not konfirmasi:
                            st.error("Centang konfirmasi terlebih dahulu.")
                        else:
                            ok = delete_transaksi(int(app_no))
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
                        if REPORTLAB_AVAILABLE:
                            spj_bytes = generate_spj_document(r)
                            st.download_button(
                                label="⬇️ Unduh SPJ (PDF)",
                                data=spj_bytes,
                                file_name=f"SPJ_No{app_no}.pdf",
                                mime="application/pdf",
                            )
                        else:
                            st.warning("Library reportlab tidak terinstal. Tidak dapat generate PDF.")
                    else:
                        st.error("Transaksi tidak ditemukan.")
            else:
                st.info("✅ Tidak ada transaksi yang menunggu approval.")
        else:
            st.info("Data transaksi tidak tersedia.")

        st.divider()
        # ---- 4. Tren Realisasi Bulanan ----
        st.subheader("Tren Realisasi Bulanan")
        if not df_transaksi.empty and nominal_col and "TANGGAL PENGAJUAN" in df_transaksi.columns:
            df_trend = df_transaksi.copy()
            df_trend[NOMINAL_COL_FOR_DASH] = pd.to_numeric(
                df_trend[nominal_col], errors="coerce"
            ).fillna(0)
            df_trend["bulan"] = pd.to_datetime(
                df_trend["TANGGAL PENGAJUAN"], format="%d/%m/%Y", errors="coerce"
            ).dt.strftime("%m/%Y")
            trend_monthly = (
                df_trend.groupby("bulan")[NOMINAL_COL_FOR_DASH]
                .sum()
                .reset_index()
            )
            trend_monthly.columns = ["Bulan", "Realisasi"]
            trend_monthly = trend_monthly.sort_values("Bulan")
            if not trend_monthly.empty:
                st.line_chart(trend_monthly.set_index("Bulan")["Realisasi"])
            else:
                st.info("Belum ada data tren bulanan.")
        else:
            st.info("Data transaksi atau tanggal tidak cukup untuk tren bulanan.")

        # ---- 5. Perbandingan Target vs Realisasi ----
        st.subheader("Perbandingan Target vs Realisasi per Sub Kegiatan")
        if not df_kegiatan.empty and not df_transaksi.empty and "pagu_awal" in df_kegiatan.columns and nominal_col:
            df_compare = df_kegiatan.copy()
            df_compare["pagu_awal"] = pd.to_numeric(df_compare["pagu_awal"], errors="coerce").fillna(0)
            df_transaksi_copy = df_transaksi.copy()
            df_transaksi_copy[NOMINAL_COL_FOR_DASH] = pd.to_numeric(
                df_transaksi_copy[nominal_col], errors="coerce"
            ).fillna(0)
            df_transaksi_copy["subkode"] = df_transaksi_copy["SUB KEGIATAN"].astype(str).str.split(" - ").str[0]
            realisasi_per_sub = (
                df_transaksi_copy.groupby("subkode")[NOMINAL_COL_FOR_DASH]
                .sum()
                .reset_index()
            )
            realisasi_per_sub.columns = ["subkegiatan", "realisasi"]
            df_compare = df_compare.merge(realisasi_per_sub, on="subkegiatan", how="left")
            df_compare["realisasi"] = df_compare["realisasi"].fillna(0)
            df_compare_display = df_compare[["subkegiatan", "nama_kegiatan", "pagu_awal", "realisasi"]].copy()
            df_compare_display["sisa"] = df_compare_display["pagu_awal"] - df_compare_display["realisasi"]
            df_compare_display.columns = ["Kode", "Nama Kegiatan", "Target (Pagu)", "Realisasi", "Sisa Pagu"]
            df_compare_display["Target (Pagu)"] = df_compare_display["Target (Pagu)"].apply(format_rupiah)
            df_compare_display["Realisasi"] = df_compare_display["Realisasi"].apply(format_rupiah)
            df_compare_display["Sisa Pagu"] = df_compare_display["Sisa Pagu"].apply(format_rupiah)
            st.dataframe(df_compare_display, hide_index=True)
        else:
            st.info("Data pagu atau transaksi tidak cukup untuk perbandingan target vs realisasi.")

        # ---- 6. Peringkat PPTK Berdasarkan Realisasi ----
        st.subheader("Peringkat PPTK Berdasarkan Realisasi")
        if not df_transaksi.empty and nominal_col and "PPTK" in df_transaksi.columns:
            df_transaksi_copy = df_transaksi.copy()
            df_transaksi_copy[NOMINAL_COL_FOR_DASH] = pd.to_numeric(
                df_transaksi_copy[nominal_col], errors="coerce"
            ).fillna(0)
            df_rank = (
                df_transaksi_copy.groupby("PPTK")[NOMINAL_COL_FOR_DASH]
                .sum()
                .reset_index()
            )
            df_rank.columns = ["PPTK", "Total Realisasi"]
            df_rank = df_rank.sort_values("Total Realisasi", ascending=False)
            df_rank["Peringkat"] = range(1, len(df_rank) + 1)
            df_rank["Total Realisasi"] = df_rank["Total Realisasi"].apply(format_rupiah)
            df_rank = df_rank[["Peringkat", "PPTK", "Total Realisasi"]]
            st.dataframe(df_rank, hide_index=True)
        else:
            st.info("Belum ada data PPTK untuk ditampilkan dalam peringkat.")

# ===================== PERUBAHAN PAGU =====================
elif menu == "Perubahan Pagu":
    # Lazy load data yang dibutuhkan menu Perubahan Pagu
    df_kegiatan = get_df("MASTER_KEGIATAN")
    df_perubahan = get_df("PERUBAHAN_PAGU")
    df_pengguna = get_df("PENGGUNA")
    if not is_manager(current_user.get("peran", "")):
        st.warning("Menu ini hanya untuk pengelola (ADMIN / KASUBAG_PEK).")
        st.stop()

    st.header("Perubahan Pagu")

    st.subheader("Ajukan Perubahan Pagu Baru")
    with st.form("form_perubahan_pagu"):
        subkode = st.selectbox(
            "Sub Kegiatan",
            options=df_kegiatan["subkegiatan"].dropna().tolist() if not df_kegiatan.empty and "subkegiatan" in df_kegiatan.columns else ["-"],
            format_func=lambda x: get_subkegiatan_full(x, df_kegiatan) if not df_kegiatan.empty else x
        )
        pagu_baru = st.number_input("Pagu Baru (Rp)", min_value=0, step=1000000)
        alasan = st.text_area("Alasan Perubahan", height=100)
        if st.form_submit_button("Ajukan Perubahan", type="primary"):
            if subkode == "-" or pagu_baru <= 0:
                st.error("Sub Kegiatan dan Pagu Baru wajib diisi dengan benar.")
            else:
                new_row = {
                    "SUB KEGIATAN": subkode,
                    "PAGU_BARU": pagu_baru,
                    "ALASAN": alasan,
                    "DIAJUKAN_OLEH": current_user.get("nama", "Admin"),
                    "TANGGAL_AJUAN": date.today().strftime("%d/%m/%Y"),
                    "STATUS": "Menunggu Approval"
                }
                df_p = load_sheet("PERUBAHAN_PAGU")
                if df_p.empty:
                    df_p = pd.DataFrame(columns=list(new_row.keys()))
                updated = pd.concat([df_p, pd.DataFrame([new_row])], ignore_index=True)
                ok = update_sheet_data("PERUBAHAN_PAGU", updated)
                if ok:
                    st.success("Perubahan pagu berhasil diajukan. Menunggu approval.")
                    st.rerun()
                else:
                    st.error("Gagal mengajukan perubahan pagu.")

    st.divider()
    st.subheader("Daftar Perubahan Pagu")
    if not df_perubahan.empty:
        st.dataframe(format_df_rupiah(df_perubahan), hide_index=True)
    else:
        st.info("Belum ada data perubahan pagu.")

# ===================== MASTER DATA =====================
elif menu == "Master Data":
    if not is_manager(current_user.get("peran", "")):
        st.warning("Menu ini hanya untuk pengelola (ADMIN / KASUBAG_PEK).")
        st.stop()

    # Lazy load data yang dibutuhkan menu Master Data
    df_wilayah = get_df("MASTER_WILAYAH")
    df_kegiatan = get_df("MASTER_KEGIATAN")
    df_rekening = get_df("MASTER_REKENING")
    df_pengguna = get_df("PENGGUNA")
    st.header("Master Data")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Wilayah", "Sub Kegiatan", "Rekening", "Pengguna", "Audit Log"])

    # ---------- Tab Wilayah ----------
    with tab1:
        st.subheader("Data Wilayah")
        if not df_wilayah.empty:
            st.dataframe(df_wilayah, hide_index=True)
            st.divider()
            with st.form("form_add_wilayah"):
                st.markdown("**Tambah Wilayah**")
                w_nama = st.text_input("Nama Wilayah")
                w_kode = st.text_input("Kode Wilayah")
                if st.form_submit_button("Simpan Wilayah"):
                    if add_master_wilayah(w_nama, w_kode, user=current_user.get("nama", "Sistem")):
                        st.success("Wilayah berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("Gagal menambahkan wilayah.")
        else:
            st.info("Belum ada data wilayah.")

    # ---------- Tab Sub Kegiatan ----------
    with tab2:
        st.subheader("Data Sub Kegiatan")
        if not df_kegiatan.empty:
            st.dataframe(format_df_rupiah(df_kegiatan), hide_index=True)
            st.divider()
            with st.form("form_add_kegiatan"):
                st.markdown("**Tambah Sub Kegiatan**")
                k_sub = st.text_input("Kode Sub Kegiatan")
                k_nama = st.text_input("Nama Kegiatan")
                k_pagu = st.number_input("Pagu Awal (Rp)", min_value=0, step=1000000)
                if st.form_submit_button("Simpan Kegiatan"):
                    if add_master_kegiatan(k_sub, k_nama, k_pagu, user=current_user.get("nama", "Sistem")):
                        st.success("Sub kegiatan berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("Gagal menambahkan sub kegiatan.")
        else:
            st.info("Belum ada data sub kegiatan.")

    # ---------- Tab Rekening ----------
    with tab3:
        st.subheader("Data Rekening Belanja")
        if not df_rekening.empty:
            st.dataframe(df_rekening, hide_index=True)
            st.divider()
            col_add, col_edit = st.columns(2)
            with col_add:
                with st.form("form_add_rekening"):
                    st.markdown("**Tambah Rekening**")
                    r_kode = st.text_input("Kode Rekening")
                    r_uraian = st.text_input("Uraian Rekening")
                    if st.form_submit_button("Simpan Rekening"):
                        if add_master_rekening(r_kode, r_uraian, user=current_user.get("nama", "Sistem")):
                            st.success("Rekening berhasil ditambahkan.")
                            st.rerun()
                        else:
                            st.error("Gagal menambahkan rekening.")
            with col_edit:
                with st.form("form_edit_rekening"):
                    st.markdown("**Edit / Hapus Rekening**")
                    r_idx = st.number_input("Indeks Baris", min_value=0, step=1)
                    e_kode = st.text_input("Kode Rekening Baru")
                    e_uraian = st.text_input("Uraian Rekening Baru")
                    col_simpan, col_hapus = st.columns(2)
                    with col_simpan:
                        if st.form_submit_button("Simpan Perubahan"):
                            if edit_master_rekening(int(r_idx), e_kode, e_uraian, user=current_user.get("nama", "Sistem")):
                                st.success("Rekening berhasil diupdate.")
                                st.rerun()
                            else:
                                st.error("Gagal mengupdate rekening.")
                    with col_hapus:
                        if st.form_submit_button("Hapus", type="secondary"):
                            if delete_master_rekening(int(r_idx), user=current_user.get("nama", "Sistem")):
                                st.success("Rekening berhasil dihapus.")
                                st.rerun()
                            else:
                                st.error("Gagal menghapus rekening.")
        else:
            st.info("Belum ada data rekening.")

    # ---------- Tab Pengguna ----------
    with tab4:
        st.subheader("Data Pengguna")
        if not df_pengguna.empty:
            st.dataframe(df_pengguna, hide_index=True)
            st.divider()
            with st.form("form_add_user"):
                st.markdown("**Tambah Pengguna**")
                u_user = st.text_input("User Name")
                u_pass = st.text_input("Password", type="password")
                u_nama = st.text_input("Nama Lengkap")
                u_peran = st.selectbox("Peran", ["ADMIN", "KASUBAG_PEK", "PPTK"])
                if st.form_submit_button("Simpan Pengguna"):
                    if add_master_user(u_user, u_pass, u_nama, u_peran, user=current_user.get("nama", "Sistem")):
                        st.success("Pengguna berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("Gagal menambahkan pengguna.")
        else:
            st.info("Belum ada data pengguna.")

    # ---------- Tab Audit Log ----------
    with tab5:
        st.subheader("Audit Log — Riwayat Perubahan Data")
        df_audit = load_sheet("AUDIT_LOG")
        if not df_audit.empty:
            # Urutkan terbaru dulu
            df_audit = df_audit.sort_values("WAKTU", ascending=False)
            st.dataframe(df_audit, hide_index=True)
            st.divider()
            if st.button("Refresh Audit Log"):
                st.cache_resource.clear()
                st.rerun()
        else:
            st.info("Belum ada riwayat audit log.")

st.divider()
st.caption("SIMKEU Kecamatan Candisari 2027 · Data dari Google Sheets · Validasi dan hak akses tetap harus di backend")
