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
import sqlite3
from datetime import date, datetime
from streamlit_gsheets import GSheetsConnection

try:
    from openpyxl import Workbook
    from openpyxl.utils.dataframe import dataframe_to_rows
    OPENPYXL_AVAILABLE = True
except Exception:
    OPENPYXL_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ===================== KONFIG =====================
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1YzcixnxXR7B5hHh4ffVkbyKlmPscH_v-tB8Gq9cai_s/edit"

st.set_page_config(
    page_title="SIMKEU Kecamatan Candisari 2027",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===================== HIDE STREAMLIT UI CHROME =====================
st.markdown(
    """
    <style>
    /* Sembunyikan teks "running ..." dan toolbar kanan atas */
    .stDeployButton { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    .stAppToolbar { visibility: hidden !important; }
    /* Sembunyikan indikator running di pojok kanan atas */
    div[data-testid="stStatusWidget"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Inisialisasi dark mode toggle (session_state)
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ===================== KONEKSI =====================
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

# ===================== SQLITE FALLBACK (P3) =====================

SQLITE_PATH = "simkeu_local.db"

def _sqlite_connect():
    return sqlite3.connect(SQLITE_PATH)

def sqlite_init():
    """Buat tabel-tabel SQLite lokal jika belum ada."""
    try:
        conn = _sqlite_connect()
        c = conn.cursor()
        for table, cols in {
            "TRANSAKSI": "NO INTEGER PRIMARY KEY, SUB KEGIATAN TEXT, KODE_REKENING TEXT, PENGELOMPOKAN TEXT, URAIAN TEXT, JENIS TEXT, NOMINAL REAL, TANGGAL TEXT, BUKTI TEXT, PPTK TEXT, STATUS TEXT",
            "MASTER_REKENING": "id INTEGER PRIMARY KEY AUTOINCREMENT, kode_rekening TEXT, uraian_rekening TEXT",
            "MASTER_WILAYAH": "id INTEGER PRIMARY KEY AUTOINCREMENT, nama_wilayah TEXT, kode_wilayah TEXT",
            "MASTER_KEGIATAN": "id INTEGER PRIMARY KEY AUTOINCREMENT, subkegiatan TEXT, nama_kegiatan TEXT, pagu_awal REAL",
            "PENGGUNA": "id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT, password TEXT, nama TEXT, peran TEXT",
            "AUDIT_LOG": "id INTEGER PRIMARY KEY AUTOINCREMENT, WAKTU TEXT, USER TEXT, AKSI TEXT, TABEL TEXT, RECORD_ID TEXT, OLD_VALUES TEXT, NEW_VALUES TEXT",
            "PERUBAHAN_PAGU": "id INTEGER PRIMARY KEY AUTOINCREMENT, SUB_KEGIATAN TEXT, PAGU_BARU REAL, ALASAN TEXT, DIAJUKAN_OLEH TEXT, TANGGAL_AJUAN TEXT, STATUS TEXT",
        }.items():
            c.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols})")
        conn.commit()
        conn.close()
    except Exception:
        pass

def sqlite_read(table: str) -> pd.DataFrame:
    """Baca data dari SQLite lokal."""
    try:
        sqlite_init()
        conn = _sqlite_connect()
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def sqlite_write(table: str, df: pd.DataFrame) -> bool:
    """Tulis ulang data ke SQLite lokal."""
    try:
        sqlite_init()
        conn = _sqlite_connect()
        df.to_sql(table, conn, if_exists="replace", index=False)
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

# Tandai apakah Google Sheets tersedia
_gsheets_available = None

def check_gsheets_available() -> bool:
    """Cek apakah Google Sheets dapat diakses."""
    global _gsheets_available
    if _gsheets_available is not None:
        return _gsheets_available
    try:
        conn = get_conn()
        conn.read(spreadsheet=SPREADSHEET_URL, worksheet="TRANSAKSI", ttl=5)
        _gsheets_available = True
    except Exception:
        _gsheets_available = False
    return _gsheets_available

# ===================== THEME / DARK MODE =====================
if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
        .stApp { background-color: #0e1117; color: #fafafa; }
        .stDataFrame, .stTable { background-color: #0e1117; }
        .stMetric { background-color: #1a1c23; }
        .stTextInput input, .stTextArea textarea, .stSelectbox div, .stNumberInput input {
            background-color: #1a1c23; color: #fafafa;
        }
        .stButton button { background-color: #4a4a4a; color: #fafafa; }
        .stButton button:hover { background-color: #6a6a6a; }
        </style>
        """,
        unsafe_allow_html=True,
    )

@st.cache_data(ttl=300)
def load_sheet(worksheet_name: str) -> pd.DataFrame:
    """Baca worksheet dengan cache 5 menit. Fallback ke SQLite jika Google Sheets tidak tersedia."""
    try:
        if check_gsheets_available():
            conn = get_conn()
            df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, ttl=30)
            if df is not None and not df.empty:
                return df
    except Exception:
        pass
    # Fallback ke SQLite
    return sqlite_read(worksheet_name)

def update_sheet_data(worksheet_name: str, df: pd.DataFrame) -> bool:
    """Tulis ulang seluruh data worksheet. Google Sheets utama, SQLite fallback."""
    try:
        if check_gsheets_available():
            conn = get_conn()
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, data=df)
            st.cache_resource.clear()
            return True
    except Exception:
        pass
    # Fallback ke SQLite
    return sqlite_write(worksheet_name, df)

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
        # Fallback ke SQLite
        try:
            df_local = sqlite_read("TRANSAKSI")
            if df_local.empty:
                df_local = pd.DataFrame(columns=list(new_data.keys()) + ["STATUS"])
            next_no_local = 1
            if not df_local.empty and "NO" in df_local.columns:
                nums = pd.to_numeric(df_local["NO"], errors="coerce").dropna()
                if not nums.empty:
                    next_no_local = int(nums.max()) + 1
            new_data["NO"] = next_no_local
            new_data["STATUS"] = "Draft"
            new_row = pd.DataFrame([new_data])
            updated_local = pd.concat([df_local, new_row], ignore_index=True)
            sqlite_write("TRANSAKSI", updated_local)
            write_audit_log("CREATE", "TRANSAKSI", str(next_no_local), None, new_data, user)
            return True, next_no_local
        except Exception as e2:
            return False, str(e2)

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
            "parse_mode": "HTML"
        }
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def check_login(username: str, password: str) -> bool:
    """Cek username + password dari secrets."""
    try:
        if "users" not in st.secrets:
            return False
        return st.secrets["users"].get(username) == password
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
        return f"Rp {n:,.0f}".replace(",", ".")
    except Exception:
        return "-"

# ===================== EXPORT EXCEL / PDF (Reporting & Notifikasi P2) =====================

def export_to_excel(df: pd.DataFrame, nama_file: str = "laporan_simkeu.xlsx") -> bytes:
    """Export DataFrame ke Excel (bytes)."""
    if not OPENPYXL_AVAILABLE:
        return b""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Laporan")
    return output.getvalue()

def export_to_pdf(df: pd.DataFrame, nama_file: str = "laporan_simkeu.pdf") -> bytes:
    """Export DataFrame ke PDF (bytes)."""
    if not REPORTLAB_AVAILABLE:
        return b""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Laporan SIMKEU Kecamatan Candisari 2027", styles["Title"])]
    data = [df.columns.tolist()] + df.values.tolist()
    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]))
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()

# ===================== CETAK SPJ / SURAT (P3) =====================

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

def is_manager(peran: str) -> bool:
    return str(peran).upper() in ("ADMIN", "KASUBAG_PEK")

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

# ===================== BACKEND: CRUD MASTER DATA =====================

def update_sheet_data(worksheet_name: str, df: pd.DataFrame) -> bool:
    """Tulis ulang seluruh data worksheet ke Google Sheets."""
    try:
        conn = get_conn()
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, data=df)
        st.cache_resource.clear()
        return True
    except Exception as e:
        st.error(f"Gagal menulis ke sheet '{worksheet_name}': {e}")
        return False

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
    st.title("Login SIMKEU 2027")
    st.caption("Kecamatan Candisari")

    with st.form("login_form"):
        username = st.text_input("User Name")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk", type="primary"):
            if check_login(username.strip().lower(), password):
                uname_col = find_username_column(df_pengguna)
                if not df_pengguna.empty and uname_col:
                    user_row = df_pengguna[
                        df_pengguna[uname_col].astype(str).str.strip().str.lower() == username.strip().lower()
                    ]
                    if not user_row.empty:
                        st.session_state.current_user = user_row.iloc[0].to_dict()
                        st.session_state.logged_in = True
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
    st.markdown(f"**{current_user.get('nama', '-')}**")
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
    dark_label = "🌙 Mode Gelap" if not st.session_state.dark_mode else "☀️ Mode Terang"
    if st.button(dark_label):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

    # ---- Multi-Kecamatan filter (P3) ----
    st.divider()
    st.markdown("### 🏘️ Kecamatan")
    kec_opts = ["Candisari", "Jebres", "Laweyan", "Pasar Kliwon", "Serengan", "Banjarsari"]
    kec_default = st.session_state.get("kecamatan_filter", "Candisari")
    kec_selected = st.selectbox("Pilih Kecamatan", kec_opts, index=kec_opts.index(kec_default) if kec_default in kec_opts else 0)
    st.session_state.kecamatan_filter = kec_selected
    st.caption(f"Data ditampilkan untuk: **{kec_selected}**")

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
                        f"📌 <b>Transaksi Baru SIMKEU</b>\n"
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

        st.caption(f"Menampilkan {len(df_show)} dari {len(df_transaksi)} transaksi")
        st.dataframe(df_show, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Aksi Transaksi (Hanya Manager: ADMIN / KASUBAG_PEK)")

        col_no, col_action = st.columns([2, 3])
        with col_no:
            target_no = st.number_input("Nomor Transaksi (NO)", min_value=1, step=1)
        with col_action:
            aksi = st.selectbox("Pilih Aksi", ["Setujui", "Tolak", "Edit", "Hapus", "Cetak SPJ"])

        if aksi in ("Setujui", "Tolak"):
            status_baru = "Disetujui" if aksi == "Setujui" else "Ditolak"
            if st.button(f"{aksi} Transaksi", type="primary"):
                pptk_nama = current_user.get("nama", "Admin")
                ok = update_transaksi_status(int(target_no), status_baru, pptk_nama)
                if ok:
                    st.success(f"Transaksi No {target_no} berhasil {status_baru.lower()}.")
                    try:
                        row = df_transaksi[pd.to_numeric(df_transaksi["NO"], errors="coerce") == int(target_no)]
                        if not row.empty:
                            r = row.iloc[0]
                            pesan = (
                                f"📋 <b>Transaksi {status_baru}</b>\n"
                                f"No: {target_no}\n"
                                f"Sub Kegiatan: {r.get('SUB KEGIATAN', '-')}\n"
                                f"Nominal: {format_rupiah(r.get('NOMINAL', 0))}\n"
                                f"Oleh: {pptk_nama}"
                            )
                            send_telegram(pesan)
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.error("Gagal mengubah status transaksi.")

        elif aksi == "Edit":
            with st.form("form_edit_transaksi"):
                new_uraian = st.text_input("Uraian baru")
                new_nominal = st.number_input("Nominal baru", min_value=0, step=1000)
                if st.form_submit_button("Simpan Perubahan"):
                    new_data = {"URAIAN": new_uraian, "NOMINAL": new_nominal}
                    ok = edit_transaksi(int(target_no), new_data)
                    if ok:
                        st.success(f"Transaksi No {target_no} berhasil diupdate.")
                        st.rerun()
                    else:
                        st.error("Gagal mengedit transaksi.")

        elif aksi == "Hapus":
            st.warning("⚠️ Aksi ini tidak dapat dibatalkan.")
            konfirmasi = st.checkbox("Saya yakin ingin menghapus transaksi ini.")
            if st.button("Hapus Transaksi", type="secondary"):
                if not konfirmasi:
                    st.error("Centang konfirmasi terlebih dahulu.")
                else:
                    ok = delete_transaksi(int(target_no))
                    if ok:
                        st.success(f"Transaksi No {target_no} berhasil dihapus.")
                        st.rerun()
                    else:
                        st.error("Gagal menghapus transaksi.")

        elif aksi == "Cetak SPJ":
            st.markdown("### Cetak Surat Pertanggungjawaban (SPJ)")
            row = df_transaksi[pd.to_numeric(df_transaksi["NO"], errors="coerce") == int(target_no)]
            if not row.empty:
                r = row.iloc[0]
                st.info(f"SPJ untuk Transaksi No {target_no}")
                if REPORTLAB_AVAILABLE:
                    spj_bytes = generate_spj_document(r)
                    st.download_button(
                        label="⬇️ Unduh SPJ (PDF)",
                        data=spj_bytes,
                        file_name=f"SPJ_No{target_no}.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.warning("Library reportlab tidak terinstal. Tidak dapat generate PDF.")
            else:
                st.error("Transaksi tidak ditemukan.")
    else:
        st.info("Belum ada transaksi.")

# ===================== DASHBOARD =====================
elif menu == "Dashboard":
    # Lazy load data yang dibutuhkan menu Dashboard
    df_kegiatan = get_df("MASTER_KEGIATAN")
    df_transaksi = get_df("TRANSAKSI")
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jumlah Sub Kegiatan", len(df_kegiatan))
    c2.metric("Total Pagu", format_rupiah(total_pagu))
    c3.metric("Realisasi", format_rupiah(total_realisasi))
    c4.metric("Sisa Pagu", format_rupiah(sisa), delta=f"{persen:.1f}% terpakai")

    # ---- Tombol Export (Reporting & Notifikasi P2) ----
    st.divider()
    st.markdown("### Export Laporan")
    e_col1, e_col2, e_col3 = st.columns(3)
    df_export = df_transaksi if not df_transaksi.empty else pd.DataFrame()
    with e_col1:
        if OPENPYXL_AVAILABLE and st.button("⬇️ Unduh Excel"):
            xlsx_bytes = export_to_excel(df_export)
            st.download_button(
                label="Klik untuk unduh file Excel",
                data=xlsx_bytes,
                file_name="laporan_simkeu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    with e_col2:
        if REPORTLAB_AVAILABLE and st.button("⬇️ Unduh PDF"):
            pdf_bytes = export_to_pdf(df_export)
            st.download_button(
                label="Klik untuk unduh file PDF",
                data=pdf_bytes,
                file_name="laporan_simkeu.pdf",
                mime="application/pdf",
            )
    with e_col3:
        st.info("Excel: openpyxl | PDF: reportlab")

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
                f"🚨 <b>PERINGATAN PAGU HABIS</b>\n"
                f"Realisasi: {format_rupiah(total_realisasi)} / {format_rupiah(total_pagu)}\n"
                f"Penggunaan: {persen:.1f}%\n"
                f"Sisa: {format_rupiah(sisa)}"
            )
            send_telegram(pesan_pagu)
        except Exception:
            pass

    st.subheader("Sub Kegiatan")
    if not df_kegiatan.empty:
        st.dataframe(df_kegiatan, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data sub kegiatan.")

    st.subheader("Transaksi Terbaru")
    if not df_transaksi.empty:
        st.dataframe(df_transaksi, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada transaksi.")

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
        st.dataframe(df_perubahan, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data perubahan pagu.")

# ===================== MASTER DATA =====================
elif menu == "Master Data":
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
            st.dataframe(df_wilayah, use_container_width=True, hide_index=True)
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
            st.dataframe(df_kegiatan, use_container_width=True, hide_index=True)
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
            st.dataframe(df_rekening, use_container_width=True, hide_index=True)
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
            st.dataframe(df_pengguna, use_container_width=True, hide_index=True)
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
            st.dataframe(df_audit, use_container_width=True, hide_index=True)
            st.divider()
            if st.button("Refresh Audit Log"):
                st.cache_resource.clear()
                st.rerun()
        else:
            st.info("Belum ada riwayat audit log.")

st.divider()
st.caption("SIMKEU Kecamatan Candisari 2027 · Data dari Google Sheets · Validasi dan hak akses tetap harus di backend")
