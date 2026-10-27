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

# Inisialisasi dark mode toggle (session_state)
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ===================== KONEKSI =====================
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

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

def load_sheet(worksheet_name: str) -> pd.DataFrame:
    """Baca worksheet. Kembalikan DataFrame kosong jika gagal."""
    try:
        conn = get_conn()
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, ttl=30)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Gagal membaca sheet '{worksheet_name}': {e}")
        st.info("Pastikan service account sudah di-share ke spreadsheet dan secrets.toml sudah benar.")
        return pd.DataFrame()

def append_transaksi(new_data: dict):
    """Tambahkan baris baru ke sheet TRANSAKSI."""
    try:
        conn = get_conn()
        df = load_sheet("TRANSAKSI")
        if df.empty:
            df = pd.DataFrame(columns=[
                "NO", "SUB KEGIATAN", "KODE REKENING BELANJA",
                "PENGELOMPOKAN BELANJA (#)", "URAIAN",
                "JENIS TRANSAKSI (UP/GU/LS)", "NOMINAL",
                "TANGGAL PENGAJUAN", "BUKTI DUKUNG SPJ", "PPTK"
            ])
        next_no = 1
        if not df.empty and "NO" in df.columns:
            nums = pd.to_numeric(df["NO"], errors="coerce").dropna()
            if not nums.empty:
                next_no = int(nums.max()) + 1

        new_data["NO"] = next_no
        new_row = pd.DataFrame([new_data])
        updated = pd.concat([df, new_row], ignore_index=True)

        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="TRANSAKSI", data=updated)
        return True, next_no
    except Exception as e:
        return False, str(e)

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
def add_master_rekening(kode: str, uraian: str) -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty:
        df = pd.DataFrame(columns=["kode_rekening", "uraian_rekening"])
    new_row = pd.DataFrame([{"kode_rekening": kode, "uraian_rekaning": uraian}])
    updated = pd.concat([df, new_row], ignore_index=True)
    return update_sheet_data("MASTER_REKENING", updated)

def edit_master_rekening(idx: int, kode: str, uraian: str) -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df.at[idx, "kode_rekening"] = kode
    df.at[idx, "uraian_rekening"] = uraian
    return update_sheet_data("MASTER_REKENING", df)

def delete_master_rekening(idx: int) -> bool:
    df = load_sheet("MASTER_REKENING")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df = df.drop(index=idx).reset_index(drop=True)
    return update_sheet_data("MASTER_REKENING", df)

# --- Master Wilayah ---
def add_master_wilayah(nama: str, kode: str) -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty:
        df = pd.DataFrame(columns=["nama_wilayah", "kode_wilayah"])
    new_row = pd.DataFrame([{"nama_wilayah": nama, "kode_wilayah": kode}])
    updated = pd.concat([df, new_row], ignore_index=True)
    return update_sheet_data("MASTER_WILAYAH", updated)

def edit_master_wilayah(idx: int, nama: str, kode: str) -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df.at[idx, "nama_wilayah"] = nama
    df.at[idx, "kode_wilayah"] = kode
    return update_sheet_data("MASTER_WILAYAH", df)

def delete_master_wilayah(idx: int) -> bool:
    df = load_sheet("MASTER_WILAYAH")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df = df.drop(index=idx).reset_index(drop=True)
    return update_sheet_data("MASTER_WILAYAH", df)

# --- Master Kegiatan ---
def add_master_kegiatan(subkode: str, nama: str, pagu: float) -> bool:
    df = load_sheet("MASTER_KEGIATAN")
    if df.empty:
        df = pd.DataFrame(columns=["subkegiatan", "nama_kegiatan", "pagu_awal"])
    new_row = pd.DataFrame([{"subkegiatan": subkode, "nama_kegiatan": nama, "pagu_awal": pagu}])
    updated = pd.concat([df, new_row], ignore_index=True)
    return update_sheet_data("MASTER_KEGIATAN", updated)

def edit_master_kegiatan(idx: int, subkode: str, nama: str, pagu: float) -> bool:
    df = load_sheet("MASTER_KEGIATAN")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df.at[idx, "subkegiatan"] = subkode
    df.at[idx, "nama_kegiatan"] = nama
    df.at[idx, "pagu_awal"] = pagu
    return update_sheet_data("MASTER_KEGIATAN", df)

def delete_master_kegiatan(idx: int) -> bool:
    df = load_sheet("MASTER_KEGIATAN")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df = df.drop(index=idx).reset_index(drop=True)
    return update_sheet_data("MASTER_KEGIATAN", df)

# --- Master Pengguna (User Management via UI) ---
def add_master_user(user_name: str, password: str, nama: str, peran: str) -> bool:
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
    return update_sheet_data("PENGGUNA", updated)

def edit_master_user(idx: int, user_name: str, password: str, nama: str, peran: str) -> bool:
    df = load_sheet("PENGGUNA")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df.at[idx, "user_name"] = user_name
    df.at[idx, "password"] = password
    df.at[idx, "nama"] = nama
    df.at[idx, "peran"] = peran
    return update_sheet_data("PENGGUNA", df)

def delete_master_user(idx: int) -> bool:
    df = load_sheet("PENGGUNA")
    if df.empty or idx < 0 or idx >= len(df):
        return False
    df = df.drop(index=idx).reset_index(drop=True)
    return update_sheet_data("PENGGUNA", df)

# ===================== BACKEND: TRANSAKSI APPROVAL & EDIT/HAPUS =====================

def update_transaksi_status(no: int, status: str, approved_by: str) -> bool:
    """Ubah status transaksi (Draft / Diajuan / Disetujui / Ditolak)."""
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    df.loc[mask, "STATUS"] = status
    df.loc[mask, "DISETUJUI_OLEH"] = approved_by
    df.loc[mask, "TANGGAL_APPROVAL"] = date.today().strftime("%d/%m/%Y")
    return update_sheet_data("TRANSAKSI", df)

def delete_transaksi(no: int) -> bool:
    """Hapus transaksi berdasarkan nomor."""
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    df = df[~mask].reset_index(drop=True)
    return update_sheet_data("TRANSAKSI", df)

def edit_transaksi(no: int, new_data: dict) -> bool:
    """Edit transaksi yang sudah ada berdasarkan nomor."""
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    for col, val in new_data.items():
        if col in df.columns:
            df.loc[mask, col] = val
    return update_sheet_data("TRANSAKSI", df)

# ===================== LOAD DATA =====================
with st.spinner("Memuat data dari Google Sheets..."):
    df_pengguna = load_sheet("PENGGUNA")
    df_wilayah = load_sheet("MASTER_WILAYAH")
    df_rekening = load_sheet("MASTER_REKENING")
    df_kegiatan = load_sheet("MASTER_KEGIATAN")
    df_transaksi = load_sheet("TRANSAKSI")
    df_perubahan = load_sheet("PERUBAHAN_PAGU")

    # Pastikan kolom STATUS ada (untuk approval transaksi)
    if not df_transaksi.empty and "STATUS" not in df_transaksi.columns:
        df_transaksi["STATUS"] = "Draft"
        df_transaksi["DISETUJUI_OLEH"] = ""
        df_transaksi["TANGGAL_APPROVAL"] = ""

# ===================== LOGIN =====================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None

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
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.rerun()
    if st.button("Refresh data"):
        st.cache_resource.clear()
        st.rerun()

# ===================== TRANSAKSI =====================
if menu == "Transaksi":
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
                success, result = append_transaksi(new_data)
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
            aksi = st.selectbox("Pilih Aksi", ["Setujui", "Tolak", "Edit", "Hapus"])

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
    else:
        st.info("Belum ada transaksi.")

# ===================== DASHBOARD =====================
elif menu == "Dashboard":
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
            st.bar_chart(chart_df.set_index("label")[NOMINAL_COL_FOR_DASH])
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
    st.header("Master Data")
    tab1, tab2, tab3, tab4 = st.tabs(["Wilayah", "Sub Kegiatan", "Rekening", "Pengguna"])

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
                    if add_master_wilayah(w_nama, w_kode):
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
                    if add_master_kegiatan(k_sub, k_nama, k_pagu):
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
                        if add_master_rekening(r_kode, r_uraian):
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
                            if edit_master_rekening(int(r_idx), e_kode, e_uraian):
                                st.success("Rekening berhasil diupdate.")
                                st.rerun()
                            else:
                                st.error("Gagal mengupdate rekening.")
                    with col_hapus:
                        if st.form_submit_button("Hapus", type="secondary"):
                            if delete_master_rekening(int(r_idx)):
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
                    if add_master_user(u_user, u_pass, u_nama, u_peran):
                        st.success("Pengguna berhasil ditambahkan.")
                        st.rerun()
                    else:
                        st.error("Gagal menambahkan pengguna.")
        else:
            st.info("Belum ada data pengguna.")

st.divider()
st.caption("SIMKEU Kecamatan Candisari 2027 · Data dari Google Sheets · Validasi dan hak akses tetap harus di backend")
