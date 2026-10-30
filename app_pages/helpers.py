"""
Backend bersama untuk semua halaman SIMKEU.
Berisi fungsi baca/tulis Google Sheets, format, export, dan audit log.
Semua fungsi diakses melalui get_conn() dari streamlit_app (cache_resource).
"""

import fcntl
import hashlib
import io
import logging
import re
import secrets as pysecrets
import time
from datetime import date, datetime

import pandas as pd
import streamlit as st

from db import get_conn, SPREADSHEET_URL  # noqa: E402
import json
from pathlib import Path

try:
    import gspread
    from gspread import service_account_from_dict
    GSPREAD_AVAILABLE = True
except Exception:
    GSPREAD_AVAILABLE = False

logger = logging.getLogger("simkeu")

# Lock file untuk mencegah race condition read-modify-write pada Google Sheets.
# Semua operasi tulis harus mengambil lock ini sebelum baca+tulis ulang sheet.
LOCK_FILE = Path(__file__).resolve().parents[1] / ".streamlit" / "simkeu_write.lock"


def _acquire_write_lock(timeout_seconds: int = 30) -> bool:
    """Ambil exclusive lock untuk operasi tulis Google Sheets.

    Mencegah dua proses server menimpa data bersamaan (race condition).
    Mengembalikan True jika lock berhasil, False jika timeout.
    """
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = open(LOCK_FILE, "w")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Simpan fd di module-level agar tidak di-gc sebelum dilepaskan.
        _acquire_write_lock._lock_fd = lock_fd
        return True
    except BlockingIOError:
        # Lock sudah dipakai proses lain
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tidak dapat mengambil write lock: %s", exc)
        return True  # Lanjutkan tanpa lock bila gagal (fallback aman)


def _release_write_lock() -> None:
    """Lepas write lock yang sebelumnya diambil."""
    lock_fd = getattr(_acquire_write_lock, "_lock_fd", None)
    if lock_fd is not None:
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:  # noqa: BLE001
            pass
        _acquire_write_lock._lock_fd = None

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
    """Tulis ulang seluruh data worksheet ke Google Sheets dan bersihkan cache.

    Catatan: ``st.cache_data.clear() (load_sheet.clear())`` membuang cache
    SEMUA worksheet sekaligus — tidak ada clear per-worksheet pada st.cache_data.
    Ini adalah batasan arsitektur Google Sheets (lihat 10.7 Temuan).

    Operasi ini dilindungi exclusive file lock untuk mencegah race condition
    read-modify-write saat dua pengguna menyimpan bersamaan.
    """
    _acquire_write_lock()
    try:
        conn = get_conn()
        conn.update(spreadsheet=SPREADSHEET_URL, worksheet=worksheet_name, data=df)
        load_sheet.clear()  # Buang seluruh cache load_sheet (tidak ada clear per-worksheet)
        return True
    except Exception:
        st.error(f"❌ Gagal menyimpan ke sheet '{worksheet_name}'.")
        return False
    finally:
        _release_write_lock()


def _get_gspread_worksheet(worksheet_name: str):
    """Dapatkan objek gspread Worksheet untuk update cell-level tanpa clear seluruh sheet.

    Digunakan agar format manual di spreadsheet (warna, border, column width, dll.)
    tidak terhapus saat hanya satu sel perlu diubah.
    """
    if not GSPREAD_AVAILABLE:
        raise RuntimeError("gspread tidak terinstal")
    secrets = st.secrets["connections"]["gsheets"]
    sa_info = {k: v for k, v in secrets.items() if k not in ("spreadsheet", "worksheet")}
    client = service_account_from_dict(sa_info)
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    return spreadsheet.worksheet(worksheet_name)


# ---------------------------------------------------------------------------
# Pengaturan Telegram persistente (simpan di file JSON agar tidak hilang
# saat server restart; st.session_state hanya berlaku per-sesi).
# ---------------------------------------------------------------------------
SETTINGS_FILE = Path(__file__).resolve().parents[1] / ".streamlit" / "app_settings.json"


def load_telegram_setting() -> bool:
    """Baca setting telegram_enabled dari file JSON (default True)."""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return bool(data.get("telegram_enabled", True))
    except Exception:
        pass
    return True


def save_telegram_setting(value: bool) -> None:
    """Simpan setting telegram_enabled ke file JSON."""
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"telegram_enabled": bool(value)}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def send_telegram(message: str, retries: int = 2) -> bool:
    """Kirim notifikasi ke Telegram dengan retry (lihat 10.9).

    Return True jika berhasil. Gagal total tidak mencegah transaksi tersimpan
    (fire-and-forget tetap, tetapi dengan upaya ulang).

    Notifikasi akan dilewati bila st.session_state["telegram_enabled"] = False
    (toggle di sidebar Dashboard untuk admin).
    """
    try:
        if not st.session_state.get(
            "telegram_enabled", load_telegram_setting()
        ):
            return False
        if "telegram" not in st.secrets:
            return False
        token = st.secrets["telegram"].get("bot_token")
        chat_id = st.secrets["telegram"].get("chat_id")
        if not token or not chat_id:
            return False
        import requests

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        last_error = None
        for attempt in range(retries + 1):
            try:
                r = requests.post(
                    url, json={"chat_id": chat_id, "text": message}, timeout=10
                )
                if r.status_code == 200:
                    return True
                last_error = f"HTTP {r.status_code}"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            if attempt < retries:
                pass  # Jeda antar percobaan dihindari agar tidak blokir main thread Streamlit
        logger.warning("Gagal kirim Telegram setelah %d percobaan: %s", retries + 1, last_error)
        return False
    except Exception:  # noqa: BLE001
        logger.exception("send_telegram error tak terduga")
        return False


# ---------------------------------------------------------------------------
# Keamanan password (mengganti penyimpanan/verifikasi plaintext, lihat 10.5)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hash password dengan PBKDF2-HMAC-SHA256 (stdlib, tanpa dependensi eksternal).

    Format hasil: ``<salt_hex>$<dk_hex>``. Tidak ada dependensi bcrypt agar
    installasi ringan.
    """
    salt = hashlib.sha256(time.time_ns().to_bytes(8, "big")).digest()[:16]
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    """Verifikasi password. Menerima hash PBKDF2 baru atau plaintext lama (legacy)."""
    if not stored:
        return False
    stored = str(stored).strip()
    if "$" in stored:
        try:
            salt_hex, dk_hex = stored.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            dk = bytes.fromhex(dk_hex)
        except ValueError:
            return False
        return pysecrets.compare_digest(
            hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000), dk
        )
    # Fallback legacy: password disimpan plaintext di sheet (data lama).
    return pysecrets.compare_digest(stored, password)


def is_hashed(value: str) -> bool:
    """Cek apakah nilai sudah berbentuk hash PBKDF2 (untuk migrasi data lama)."""
    if not value or "$" not in str(value):
        return False
    try:
        salt_hex, dk_hex = str(value).split("$", 1)
        bytes.fromhex(salt_hex)
        bytes.fromhex(dk_hex)
        return True
    except ValueError:
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
            "TANGGAL PENGAJUAN", "PPTK", "STATUS", "ALASAN_PENOLAKAN"
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


def menu_visibility(peran: str) -> dict:
    """Tentukan menu yang tersedia untuk tiap peran.

    Dashboard tersedia untuk semua role. Transaksi tersedia untuk Kasubag dan
    PPTK (tidak untuk ADMIN). Menu manajemen berbeda:
    KASUBAG_PEK → Manajerial, ADMIN → Master Data.
    Fitur Pengajuan Pagu telah dihapus untuk PPTK (lihat 10.10 Temuan).
    """
    p = str(peran).upper()
    return {
        "dashboard": True,
        "transaksi": p != "ADMIN",
        "manajerial": p == "KASUBAG_PEK",
        "pengajuan_pagu": False,
        "master_data": p == "ADMIN",
    }


def reset_form_keys(*keys: str) -> None:
    """Hapus key widget dari session_state agar form kembali ke default setelah aksi sukses."""
    for k in keys:
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Transaksi
# ---------------------------------------------------------------------------
def append_transaksi(new_data: dict, user: str = "Sistem"):
    _acquire_write_lock()
    try:
        df = load_sheet("TRANSAKSI")
        if df.empty:
            df = pd.DataFrame(columns=[
                "NO", "SUB KEGIATAN", "KODE REKENING BELANJA",
                "PENGELOMPOKAN BELANJA (#)", "URAIAN",
                "JENIS TRANSAKSI (UP/GU/LS)", "NOMINAL",
                "TANGGAL PENGAJUAN", "BUKTI DUKUNG SPJ", "PPTK", "STATUS",
                "DISETUJUI_OLEH", "TANGGAL_APPROVAL", "ALASAN_PENOLAKAN",
            ])
        next_no = 1
        if not df.empty and "NO" in df.columns:
            nums = pd.to_numeric(df["NO"], errors="coerce").dropna()
            if not nums.empty:
                next_no = int(nums.max()) + 1

        new_data["NO"] = next_no
        new_data["STATUS"] = "Draft"

        # Susun nilai baris sesuai urutan kolom di sheet.
        col_order = list(df.columns) if not df.empty else list(new_data.keys())
        row_values = [new_data.get(col, "") for col in col_order]

        try:
            ws = _get_gspread_worksheet("TRANSAKSI")
            ws.append_rows([row_values], value_input_option="USER_ENTERED")
            try:
                load_sheet.clear()
            except AttributeError:
                pass
            ok = True
        except Exception:
            st.error("❌ Gagal menyimpan transaksi.")
            ok = False

        if ok:
            write_audit_log("CREATE", "TRANSAKSI", str(next_no), None, new_data, user)
            return True, next_no
        return False, "Gagal menyimpan transaksi."
    finally:
        _release_write_lock()


def update_transaksi_status(no: int, status: str, approved_by: str,
                            alasan: str = "") -> bool:
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    old = df.loc[mask].iloc[0].to_dict()
    # Pastikan kolom alasan penolakan ada (sheet lama belum mengetahuinya).
    if "ALASAN_PENOLAKAN" not in df.columns:
        df["ALASAN_PENOLAKAN"] = ""
    df.loc[mask, "STATUS"] = status
    df.loc[mask, "DISETUJUI_OLEH"] = approved_by
    df.loc[mask, "TANGGAL_APPROVAL"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    if status == "Ditolak":
        df.loc[mask, "ALASAN_PENOLAKAN"] = alasan
    else:
        df.loc[mask, "ALASAN_PENOLAKAN"] = ""
    ok = update_sheet_data("TRANSAKSI", df)
    if ok:
        write_audit_log("UPDATE_STATUS", "TRANSAKSI", str(no), old,
                        {"STATUS": status, "DISETUJUI_OLEH": approved_by,
                         "ALASAN_PENOLAKAN": alasan if status == "Ditolak" else ""},
                        approved_by)
    return ok


def delete_transaksi(no: int, user: str = "Sistem") -> bool:
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
        write_audit_log("DELETE", "TRANSAKSI", str(no), old, None, user)
    return ok


def edit_transaksi(no: int, new_data: dict, user: str = "Sistem") -> bool:
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
        write_audit_log("UPDATE", "TRANSAKSI", str(no), old, new_data, user)
    return ok


# ---------------------------------------------------------------------------
# Predikat kepemilikan & status (Model A — PPTK pemilik data)
# ---------------------------------------------------------------------------
def boleh_edit_transaksi(row: pd.Series, pptk_label: str) -> bool:
    """Boleh diedit PPTK bila miliknya dan masih Draft."""
    return str(row.get("PPTK", "")) == pptk_label and str(row.get("STATUS", "")) == "Draft"


def boleh_hapus_transaksi(row: pd.Series, pptk_label: str) -> bool:
    """Boleh dihapus PPTK bila miliknya dan masih Draft atau Ditolak."""
    return str(row.get("PPTK", "")) == pptk_label and str(row.get("STATUS", "")) in (
        "Draft", "Ditolak"
    )


def boleh_ajukan_ulang(row: pd.Series, pptk_label: str) -> bool:
    """Boleh diajukan ulang PPTK bila miliknya dan Ditolak."""
    return str(row.get("PPTK", "")) == pptk_label and str(row.get("STATUS", "")) == "Ditolak"


def edit_transaksi_pptk(no: int, sub_kegiatan: str, kode_rekening: str,
                        pengelompokan: str, uraian: str, jenis: str, nominal: float,
                        bukti: str, user: str, pptk_label: str) -> bool:
    """PPTK mengedit semua field transaksi Draft miliknya (kecuali NO, PPTK, STATUS)."""
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    row = df.loc[mask].iloc[0]
    if not boleh_edit_transaksi(row, pptk_label):
        return False
    old = row.to_dict()
    # Semua field yang boleh diedit PPTK pada transaksi Draft.
    if "SUB KEGIATAN" in df.columns:
        df.loc[mask, "SUB KEGIATAN"] = sub_kegiatan
    if "KODE REKENING BELANJA" in df.columns:
        df.loc[mask, "KODE REKENING BELANJA"] = kode_rekening
    if "PENGELOMPOKAN BELANJA (#)" in df.columns:
        df.loc[mask, "PENGELOMPOKAN BELANJA (#)"] = pengelompokan
    if "URAIAN" in df.columns:
        df.loc[mask, "URAIAN"] = uraian
    if "JENIS TRANSAKSI (UP/GU/LS)" in df.columns:
        df.loc[mask, "JENIS TRANSAKSI (UP/GU/LS)"] = jenis
    if "NOMINAL" in df.columns:
        df.loc[mask, "NOMINAL"] = nominal
    if "BUKTI DUKUNG SPJ" in df.columns:
        df.loc[mask, "BUKTI DUKUNG SPJ"] = bukti
    # Draft tidak boleh memiliki tanggal approval / pengesang lama.
    if "TANGGAL_APPROVAL" in df.columns:
        df.loc[mask, "TANGGAL_APPROVAL"] = ""
    if "DISETUJUI_OLEH" in df.columns:
        df.loc[mask, "DISETUJUI_OLEH"] = ""
    if "ALASAN_PENOLAKAN" in df.columns:
        df.loc[mask, "ALASAN_PENOLAKAN"] = ""
    ok = update_sheet_data("TRANSAKSI", df)
    if ok:
        write_audit_log("UPDATE", "TRANSAKSI", str(no), old,
                        {"SUB KEGIATAN": sub_kegiatan, "KODE REKENING BELANJA": kode_rekening,
                         "PENGELOMPOKAN BELANJA (#)": pengelompokan, "URAIAN": uraian,
                         "JENIS TRANSAKSI (UP/GU/LS)": jenis, "NOMINAL": nominal,
                         "BUKTI DUKUNG SPJ": bukti}, user)
    return ok


def delete_transaksi_pptk(no: int, user: str, pptk_label: str) -> bool:
    """PPTK menghapus transaksi Draft atau Ditolak miliknya.

    Baris yang dihapus dipindah ke sheet ``TRANSAKSI DIHAPUS`` sebelum
    dihapus dari ``TRANSAKSI`` (tidak menyisakan baris kosong).
    """
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False
    mask = pd.to_numeric(df["NO"], errors="coerce") == no
    if not mask.any():
        return False
    row = df.loc[mask].iloc[0]
    if not boleh_hapus_transaksi(row, pptk_label):
        return False
    old = row.to_dict()

    # Pindahkan baris ke sheet TRANSAKSI DIHAPUS sebelum dihapus.
    df_arsip = load_sheet("TRANSAKSI DIHAPUS")
    if df_arsip.empty:
        df_arsip = pd.DataFrame(columns=list(df.columns) + ["TANGGAL_HAPUS"])
    row_hapus = row.copy()
    row_hapus["TANGGAL_HAPUS"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    df_arsip = pd.concat([df_arsip, pd.DataFrame([row_hapus])], ignore_index=True)
    if not update_sheet_data("TRANSAKSI DIHAPUS", df_arsip):
        return False

    # Hapus dari TRANSAKSI dan tulis ulang tanpa baris kosong.
    df = df[~mask].reset_index(drop=True)
    ok = update_sheet_data("TRANSAKSI", df)
    if ok:
        write_audit_log("DELETE", "TRANSAKSI", str(no), old, None, user)
    return ok


def ajukan_ulang_transaksi(no_lama: int, uraian: str, nominal: float,
                           user: str, pptk_label: str):
    """PPTK menyalin transaksi Ditolak ke baris baru (Draft, NO baru).

    Transaksi lama tetap ada sebagai riwayat.
    """
    df = load_sheet("TRANSAKSI")
    if df.empty or "NO" not in df.columns:
        return False, "Gagal membaca data transaksi."
    mask = pd.to_numeric(df["NO"], errors="coerce") == no_lama
    if not mask.any():
        return False, "Transaksi tidak ditemukan."
    row = df.loc[mask].iloc[0]
    if not boleh_ajukan_ulang(row, pptk_label):
        return False, "Transaksi tidak dapat diajukan ulang."

    next_no = 1
    nums = pd.to_numeric(df["NO"], errors="coerce").dropna()
    if not nums.empty:
        next_no = int(nums.max()) + 1

    new_data = row.to_dict()
    new_data["NO"] = next_no
    new_data["STATUS"] = "Draft"
    new_data["URAIAN"] = uraian
    new_data["NOMINAL"] = nominal
    new_data["DISETUJUI_OLEH"] = ""
    new_data["TANGGAL_APPROVAL"] = ""
    new_data["ALASAN_PENOLAKAN"] = ""
    new_row = pd.DataFrame([new_data])
    updated = pd.concat([df, new_row], ignore_index=True)

    ok = update_sheet_data("TRANSAKSI", updated)
    if ok:
        write_audit_log("CREATE", "TRANSAKSI", str(next_no),
                        None, {"REF_NO": str(no_lama), **new_data}, user)
        return True, next_no
    return False, "Gagal mengajukan ulang transaksi."


def get_pagu_awal(subkode: str, df_kegiatan: pd.DataFrame) -> float:
    """Mengembalikan nilai Pagu Awal mentah untuk sub kegiatan tertentu."""
    if df_kegiatan.empty or "Kode Sub Kegiatan" not in df_kegiatan.columns:
        return 0.0
    row = df_kegiatan[df_kegiatan["Kode Sub Kegiatan"].astype(str).str.strip() == str(subkode).strip()]
    if row.empty:
        return 0.0
    val = parse_number(row.iloc[0].get("Pagu Awal", 0))
    return float(val) if val is not None else 0.0


def get_sisa_pagu(subkode: str, df_kegiatan: pd.DataFrame, df_transaksi: pd.DataFrame) -> float:
    """Menghitung Sisa Pagu = Pagu Awal + Perubahan Pagu - Realisasi (transaksi Disetujui).

    Realisasi dihitung dari total NOMINAL transaksi status Disetujui yang mapping
    kode sub kegiatannya cocok (dengan memperiksa SUB KEGIATAN apakah mulai dengan kode).
    """
    if df_kegiatan.empty or "Kode Sub Kegiatan" not in df_kegiatan.columns:
        return 0.0

    # Ambil Pagu Awal dan Perubahan Pagu dari master
    row = df_kegiatan[df_kegiatan["Kode Sub Kegiatan"].astype(str).str.strip() == str(subkode).strip()]
    if row.empty:
        return 0.0

    pagu_awal = parse_number(row.iloc[0].get("Pagu Awal", 0)) or 0
    perubahan_lama = parse_number(row.iloc[0].get("Perubahan Pagu", 0)) or 0

    # Hitung Realisasi dari transaksi Disetujui
    if not df_transaksi.empty and "NOMINAL" in df_transaksi.columns and "STATUS" in df_transaksi.columns:
        df_setuju = df_transaksi[df_transaksi["STATUS"].astype(str).str.strip() == "Disetujui"]
        if not df_setuju.empty:
            # Ekstrak kode sub kegiatan dari kolom SUB KEGIATAN (format: "Kode - Nama")
            def _kode_from_subkegiatan(sub_str: str) -> str:
                if not sub_str:
                    return ""
                return str(sub_str).split(" - ")[0].strip()

            realisasi = 0.0
            for _, r in df_setuju.iterrows():
                sub_str = str(r.get("SUB KEGIATAN", ""))
                if _kode_from_subkegiatan(sub_str) == str(subkode).strip():
                    realisasi += parse_number(r.get("NOMINAL", 0)) or 0.0
        else:
            realisasi = 0.0
    else:
        realisasi = 0.0

    return float(pagu_awal + perubahan_lama - realisasi)


def get_ajukan_ulang_map() -> dict:
    """Peta {NO transaksi baru: NO transaksi lama} dari AUDIT_LOG (retroaktif)."""
    result = {}
    try:
        df = load_sheet("AUDIT_LOG")
    except Exception:
        return result
    if df is None or df.empty:
        return result
    cols = {str(c).upper() for c in df.columns}
    if "AKSI" not in cols or "TABEL" not in cols:
        return result
    mask = (
        df["AKSI"].astype(str).str.strip().str.upper() == "CREATE"
    ) & (df["TABEL"].astype(str).str.strip().str.upper() == "TRANSAKSI")
    for _, r in df[mask].iterrows():
        new_no_raw = r.get("RECORD_ID")
        new_vals = r.get("NEW VALUES", "")
        m = re.search(r"'REF_NO'\s*:\s*'?(\d+)'?", str(new_vals))
        if m is None:
            m = re.search(r'\"REF_NO\"\s*:\s*\"?(\d+)\"?', str(new_vals))
        if m is None or new_no_raw is None:
            continue
        try:
            new_no = int(float(new_no_raw))
            old_no = int(m.group(1))
        except (ValueError, TypeError):
            continue
        result[new_no] = old_no
    return result


def kirim_notifikasi_penolakan(row: pd.Series, alasan: str) -> bool:
    """Kirim notifikasi Telegram ke chat global saat transaksi ditolak."""
    pesan = (
        f"🚫 Transaksi Ditolak SIMKEU\n"
        f"No: {row.get('NO', '-')}\n"
        f"PPTK: {row.get('PPTK', '-')}\n"
        f"Sub Kegiatan: {row.get('SUB KEGIATAN', '-')}\n"
        f"Rekening: {row.get('KODE REKENING BELANJA', '-')}\n"
        f"Jenis: {row.get('JENIS TRANSAKSI (UP/GU/LS)', '-')}\n"
        f"Nominal: {format_rupiah(row.get('NOMINAL', 0))}\n"
        f"Tanggal: {row.get('TANGGAL PENGAJUAN', '-')}\n"
        f"Alasan: {alasan}\n"
        f"Silakan ajukan ulang melalui halaman Transaksi."
    )
    return send_telegram(pesan)


# ---------------------------------------------------------------------------
# Master CRUD
# ---------------------------------------------------------------------------
def _col_letter(n: int) -> str:
    """Konversi indeks kolom 1-based ke huruf Excel (A, B, ..., Z, AA, ...)."""
    string = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        string = chr(65 + rem) + string
    return string


def _get_transaksi_column_letters() -> dict:
    """Dapatkan huruf kolom Excel untuk NOMINAL, SUB KEGIATAN, STATUS di sheet TRANSAKSI.

    Membaca header sheet TRANSAKSI secara dinamis sehingga formula Sisa Pagu
    tetap benar meski urutan kolom di spreadsheet berubah (misal kolom ditambahkan
    atau dipindah). Mengembalikan dict {nama_kolom: huruf_kolom}, misal
    {"NOMINAL": "G", "SUB KEGIATAN": "B", "STATUS": "K"}.
    """
    df = load_sheet("TRANSAKSI")
    if df.empty:
        return {}
    col_map: dict = {}
    for col_name in ("NOMINAL", "SUB KEGIATAN", "STATUS"):
        if col_name in df.columns:
            idx = df.columns.get_loc(col_name) + 1  # 1-based Excel column index
            col_map[col_name] = _col_letter(idx)
    return col_map


def _master_kegiatan_with_formula(
    df: pd.DataFrame, transaksi_cols: dict | None = None
) -> pd.DataFrame:
    """Susun ulang MASTER_SUB_KEGIATAN dengan formula kolom Sisa Pagu.

    Kolom Sisa Pagu di spreadsheet berisi formula, bukan angka statis. Saat
    aplikasi menulis ulang sheet, formula harus ditulis kembali agar tidak
    berubah menjadi nilai biasa.

    Formula Sisa Pagu = Pagu Akhir + Perubahan Pagu − Realisasi (transaksi
    Disetujui). Kolom Perubahan Pagu dan Pagu Akhir diisi/dihitung di sisi
    spreadsheet; aplikasi hanya menuliskannya kembali sebagai formula agar
    tetap otomatis hitung saat data TRANSAKSI berubah.

    Parameter transaksi_opsional menyediakan huruf kolom TRANSAKSI untuk
    NOMINAL / SUB KEGIATAN / STATUS. Jika tidak disediakan, dibaca dari header
    sheet TRANSAKSI agar formula tidak patah jika urutan kolom berubah.
    """
    columns = [
        "Kode Sub Kegiatan", "Sub Kegiatan", "Pagu Awal",
        "Perubahan Pagu", "Pagu Akhir", "Sisa Pagu",
    ]
    df = df.copy().reset_index(drop=True)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns]

    if transaksi_cols is None:
        transaksi_cols = _get_transaksi_column_letters()

    nominal_letter = transaksi_cols.get("NOMINAL", "G")
    subkegiatan_letter = transaksi_cols.get("SUB KEGIATAN", "B")
    status_letter = transaksi_cols.get("STATUS", "K")

    idx_kode = df.columns.get_loc("Kode Sub Kegiatan") + 1
    idx_pagu_akhir = df.columns.get_loc("Pagu Akhir") + 1
    idx_perubahan = df.columns.get_loc("Perubahan Pagu") + 1
    kode_letter = _col_letter(idx_kode)
    akhir_letter = _col_letter(idx_pagu_akhir)
    perubahan_letter = _col_letter(idx_perubahan)

    df["Sisa Pagu"] = [
        f"={akhir_letter}{i + 2}+{perubahan_letter}{i + 2}"
        f"-SUMIFS(TRANSAKSI!{nominal_letter}:{nominal_letter}, "
        f"TRANSAKSI!{subkegiatan_letter}:{subkegiatan_letter}, "
        f"{kode_letter}{i + 2} & \"*\", "
        f"TRANSAKSI!{status_letter}:{status_letter}, \"Disetujui\")"
        for i in range(len(df))
    ]
    return df


def update_master_subkegiatan_perubahan_pagu(
    subkode: str, perubahan_pagu: float, user: str = "Sistem"
) -> bool:
    """Perbarui kolom Perubahan Pagu sub kegiatan dan hitung ulang Sisa Pagu.

    Sisa Pagu = Pagu Akhir + Perubahan Pagu − Realisasi (transaksi Disetujui).

    Mengupdate hanya satu sel (Perubahan Pagu) via gspread cell-level agar
    format manual di spreadsheet tidak terhapus. Kolom Sisa Pagu berisi
    formula di spreadsheet, jadi otomatis terhitung kembali saat
    Perubahan Pagu berubah.

    Operasi ini dilindungi exclusive file lock untuk mencegah race condition
    saat dua pengguna mengubah pagu bersamaan.
    """
    _acquire_write_lock()
    try:
        df = load_sheet("MASTER_SUB_KEGIATAN")
        if df.empty or "Kode Sub Kegiatan" not in df.columns:
            return False
        mask = df["Kode Sub Kegiatan"].astype(str).str.strip() == str(subkode).strip()
        if not mask.any():
            return False
        idx = int(df.index[mask][0])
        old = df.iloc[idx].to_dict()

        # Cari indeks kolom "Perubahan Pagu" (1-based)
        col_names = list(df.columns)
        if "Perubahan Pagu" not in col_names:
            return False
        col_idx = col_names.index("Perubahan Pagu") + 1

        # Baris di sheet = index dataframe + 1 (header) + 1 (0-based → 1-based)
        row_idx = idx + 2

        try:
            ws = _get_gspread_worksheet("MASTER_SUB_KEGIATAN")
            ws.update_cell(row_idx, col_idx, perubahan_pagu)
            try:
                load_sheet.clear()  # Buang cache agar data baru termuat saat rerun
            except AttributeError:
                pass  # load_sheet mungkin di-mock dalam tes tanpa method .clear()
            ok = True
        except Exception:
            st.error("❌ Gagal menyimpan ke sheet 'MASTER_SUB_KEGIATAN'.")
            ok = False

        if ok:
            write_audit_log(
                "UPDATE", "MASTER_SUB_KEGIATAN", str(idx), old,
                {"Perubahan Pagu": perubahan_pagu}, user,
            )
        return ok
    finally:
        _release_write_lock()


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
    # Validasi kebijakan password sebelum disimpan (keamanan).
    ok_policy, pesan_policy = validate_password(password)
    if not ok_policy:
        st.error(pesan_policy)
        return False
    # Simpan sebagai hash, kecuali sudah berbentuk hash (10.5 Temuan).
    if password and not is_hashed(password):
        password = hash_password(password)
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
    # Jika password dikosongkan di edit, tetap gunakan password lama; jika diisi,
    # validasi kebijakan lalu simpan sebagai hash (10.5 Temuan).
    if password:
        ok_policy, pesan_policy = validate_password(password)
        if not ok_policy:
            st.error(pesan_policy)
            return False
        if not is_hashed(password):
            password = hash_password(password)
    else:
        password = str(old.get("Password", ""))
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


def validate_password(password: str) -> tuple[bool, str]:
    """Validasi kebijakan password.

    Aturan:
    - Minimal 8 karakter.
    - Mengandung setidaknya satu huruf dan satu angka.

    Mengembalikan (is_valid, pesan_error). Jika valid, pesan_error berupa string kosong.
    """
    if not password:
        return False, "Password tidak boleh kosong."
    if len(password) < 8:
        return False, "Password minimal 8 karakter."
    if not any(c.isalpha() for c in password):
        return False, "Password harus mengandung setidaknya satu huruf."
    if not any(c.isdigit() for c in password):
        return False, "Password harus mengandung setidaknya satu angka."
    return True, ""


def update_master_subkegiatan_pagu(subkode: str, pagu_baru: float,
                                   user: str = "Sistem") -> bool:
    """Perbarui Pagu Awal sub kegiatan berdasarkan Kode Sub Kegiatan.

    Digunakan saat pengajuan perubahan pagu disetujui (lihat 10.3 Temuan).
    """
    df = load_sheet("MASTER_SUB_KEGIATAN")
    if df.empty or "Kode Sub Kegiatan" not in df.columns:
        return False
    mask = df["Kode Sub Kegiatan"].astype(str).str.strip() == str(subkode).strip()
    if not mask.any():
        return False
    idx = int(df.index[mask][0])
    return edit_master_kegiatan(
        idx,
        str(df.at[idx, "Kode Sub Kegiatan"]),
        str(df.at[idx, "Sub Kegiatan"]),
        pagu_baru,
        user=user,
    )
