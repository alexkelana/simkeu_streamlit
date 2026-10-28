# SIMKEU Streamlit — Terhubung Google Sheets

Aplikasi manajemen keuangan kecamatan (SIMKEU) berbasis Streamlit 1.6x, terhubung ke Google Sheets sebagai backend.

## Struktur aplikasi

```
streamlit_app.py      # Entrypoint (st.navigation + page config)
db.py                 # Koneksi Google Sheets + SPREADSHEET_URL
app_pages/            # Setiap halaman sebagai st.Page
  __init__.py
  login.py            # Halaman masuk
  logout.py           # Keluar
  transaksi.py        # Input & daftar transaksi
  dashboard.py        # KPI, grafik, export
  manajerial.py       # Analisis manajerial (khusus manajer)
  perubahan_pagu.py   # Ajukan perubahan pagu (khusus manajer)
  master_data.py      # CRUD Wilayah, Sub Kegiatan, Rekening, Pengguna, Audit Log
  helpers.py          # Logika backend bersama (baca/tulis sheet, format, export, audit)
tests/                # Tes AppTest
```

Nama worksheet dan header kolom yang dipakai aplikasi bersifat **case-sensitive** dan mengikuti spreadsheet asli:

`TRANSAKSI`, `PENGGUNA`, `MASTER_WILAYAH`, `MASTER_REKENING`, `MASTER_SUB_KEGIATAN`, `PERUBAHAN_PAGU`, `AUDIT_LOG`.

Detail header ada di [`SPECS_SPREADSHEET.md`](SPECS_SPREADSHEET.md).

## Langkah setup service account (sekali saja)

1. Buka [Google Cloud Console](https://console.cloud.google.com/).
2. Buat project baru (atau pakai yang sudah ada).
3. Aktifkan **Google Sheets API** dan **Google Drive API**.
4. Buat Service Account → Keys → Add Key → JSON. Unduh file JSON-nya.
5. Buka spreadsheet **DATABASE SIMKEU KECAMATAN CANDISARI 2027** di Drive.
6. Klik Share → tambahkan **email service account** (ada di JSON, field `client_email`) → beri akses **Editor**.
7. Di folder aplikasi, buat folder `.streamlit/` lalu salin `secrets.toml.example` menjadi `.streamlit/secrets.toml`.
8. Isi semua field di `secrets.toml` dari isi JSON service account.
9. Tambahkan `.streamlit/secrets.toml` ke `.gitignore` (sudah tercantum). **Jangan commit file asli.**

## Install & Jalankan

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Navigasi

- `streamlit_app.py` adalah tunggal entrypoint menggunakan `st.navigation`.
- Halaman dikelompokkan: **Utama** (Transaksi, Dashboard), **Manajemen** (Manajerial, Perubahan Pagu, Master Data — hanya ADMIN/KASUBAG_PEK), dan **Akun** (Keluar).
- Pengguna PPTK hanya melihat data miliknya sendiri (filter otomatis setelah login).

## Docker

```bash
docker-compose up --build
```

`secrets.toml` dipasang melalui volume (tidak ada dalam image). Healthcheck tersedia di `/_stcore/health`.

## Tes

```bash
pytest -q
```

## Performa

- Setiap pemakaian sheet dibungkus `@st.cache_data(ttl=300)` — tidak ada re-baca berulang per interaksi.
- Koneksi Google Sheets memakai `st.connection` (sudah di-cache internal, tidak dibungkus ulang).
- Data difilter dan diagregasi sebelum ditampilkan di `st.dataframe(width="stretch")`.
- Semua widget memiliki `key=` stabil agar state tidak hilang antar halaman.
