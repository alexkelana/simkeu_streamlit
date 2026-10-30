# SIMKEU Streamlit — Terhubung Google Sheets

Aplikasi manajemen keuangan kecamatan (SIMKEU) berbasis Streamlit 1.6x, terhubung ke Google Sheets sebagai backend.

## Struktur aplikasi

```
streamlit_app.py      # Entrypoint (st.navigation + page config)
db.py                 # Koneksi Google Sheets + SPREADSHEET_URL
app_pages/            # Setiap halaman sebagai st.Page
  __init__.py
  login.py            # Halaman masuk (st.spinner saat memuat pengguna)
  logout.py           # Keluar
  transaksi.py        # Input & daftar transaksi (export di sidebar)
  dashboard.py        # KPI, grafik, informasi Kasubag, transaksi hari ini, export, toggle Telegram (ADMIN)
  manajerial.py       # Antrian approval transaksi & pengajuan pagu (khusus KASUBAG_PEK)
  perubahan_pagu.py   # Ajukan & lihat pengajuan pagu sendiri (khusus PPTK)
  master_data.py      # CRUD Wilayah, Sub Kegiatan, Rekening, Pengguna, Audit Log
  helpers.py          # Logika backend bersama (baca/tulis sheet, format, export, audit, reset_form_keys, get_ajukan_ulang_map, load/save_telegram_setting)
tests/                # Tes AppTest
.streamlit/app_settings.json  # Setting Telegram persistente (telegram_enabled)
```

## Fitur utama

- **Login**: pesan loading internal disembunyikan dengan `st.spinner("Memuat data pengguna…")`.
- **Reset form otomatis**: semua widget form dikosongkan kembali ke default setelah setiap aksi sukses (simpan, edit, hapus, ajukan ulang, approval, master CRUD).
- **Peringatan ditolak hilang setelah diatasi**: banner "transaksi ditolak" tidak muncul lagi untuk baris yang sudah diajukan ulang atau yang penggantinya disetujui.
- **Grafik dapat di-collapse**: grafik di Dashboard dibungkus `st.expander`.
- **Dashboard = informasi, Manajerial = aksi**: Dashboard Kasubag memuat KPI, grafik, dan Ringkasan Realisasi per PPTK, Peringatan Pagu ≥90%, serta Peringkat PPTK. Dashboard ADMIN berisi informasi kesehatan sistem (status koneksi, jumlah baris worksheet, status Telegram, audit log) tanpa data keuangan. Manajerial hanya berisi antrian yang butuh tindakan.
- **Transaksi hari ini**: Dashboard hanya menampilkan transaksi dengan `TANGGAL PENGAJUAN` hari ini; daftar lengkap ada di menu Transaksi.
- **Ekspor di sidebar**: export transaksi tersedia di sidebar halaman Dashboard dan Transaksi.
- **Toggle Telegram hanya untuk ADMIN**: tersedia di bagian Kesehatan Sistem pada Dashboard (toggle Aktifkan/Matikan). Pengaturan tersimpan persisten di `.streamlit/app_settings.json` (tidak hilang setelah restart server).
- **Aksi PPTK pada Transaksi**: tombol input adalah "Ajukan Transaksi". PPTK dapat mengedit **semua field** (sub kegiatan, rekening, pengelompokan, uraian, jenis, nominal, bukti dukung) dan menghapus transaksi miliknya yang masih Draft atau Ditolak melalui panel "Kelola transaksi saya". Saat memilih transaksi untuk diedit, semua input otomatis terisi sesuai data transaksi yang dipilih (terutama sub-kegiatan dan kode rekening). Panel "Kelola transaksi saya" bersifat collapsible (expander). Transaksi yang dihapus dipindah ke sheet `TRANSAKSI DIHAPUS`. Transaksi yang sudah Disetujui tidak dapat diedit atau dihapus.
- **Pengajuan Pagu dihapus untuk PPTK**: menu dan fitur Pengajuan Pagu tidak lagi tersedia untuk peran PPTK. Manajerial Kasubag kini menampilkan aksi "Perubahan Pagu" (ganti pengajuan pagu menunggu approval) untuk mengubah pagu sub kegiatan secara langsung.
- **Perubahan Pagu di Manajerial**: KASUBAG_PEK memilih sub kegiatan, input nominal penambahan/pengurangan, dan mencatatnya ke kolom `Perubahan Pagu` di sheet `MASTER_SUB_KEGIATAN`. Sisa Pagu dihitung otomatis sebagai `Pagu Akhir + Perubahan Pagu − Realisasi (Disetujui)`.
- **Formula Sisa Pagu dinamis**: huruf kolom TRANSAKSI (NOMINAL, SUB KEGIATAN, STATUS) dalam formula `Sisa Pagu` dibaca secara otomatis dari header spreadsheet, sehingga formula tidak patah jika urutan kolom berubah.
- **Locking write eksklusif**: setiap operasi tulis Google Sheets (simpan transaksi, edit/hapus, perubahan pagu, master data) dilindungi exclusive file lock untuk mencegah race condition saat dua pengguna menyimpan bersamaan.
- **Kebijakan password**: password minimal 8 karakter, mengandung setidaknya satu huruf dan satu angka. Divalidasi saat menambah dan mengedit pengguna di Master Data.
- **Label sub kegiatan lengkap**: dropdown dan label transaksi menampilkan uraian sub kegiatan penuh tanpa pemotongan karakter.
- **Format tanggal lengkap**: semua record tanggal (`TANGGAL PENGAJUAN`, `TANGGAL AJUAN`, `TANGGAL_APPROVAL`, `TANGGAL_HAPUS`) disimpan dengan format `dd/mm/yyyy hh:mm:ss`.
- **Arsip transaksi dihapus**: transaksi yang dihapus PPTK dipindah ke sheet `TRANSAKSI DIHAPUS` dengan kolom `TANGGAL_HAPUS` mencatat waktu penghapusan, tanpa menyisakan baris kosong di `TRANSAKSI`.
- **Notifikasi Telegram saat off**: saat toggle Telegram dimatikan, pesan gagal kirim tidak ditampilkan (hanya status sukses saat ON).

Nama worksheet dan header kolom yang dipakai aplikasi bersifat **case-sensitive** dan mengikuti spreadsheet asli:

`TRANSAKSI`, `TRANSAKSI DIHAPUS`, `PENGGUNA`, `MASTER_WILAYAH`, `MASTER_REKENING`, `MASTER_SUB_KEGIATAN`, `PERUBAHAN_PAGU`, `AUDIT_LOG`.

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
- Halaman awal setelah login adalah **Dashboard**.
- Menu per role:
  - **KASUBAG_PEK**: Dashboard, Transaksi, Manajerial.
  - **PPTK**: Dashboard, Transaksi. (Fitur Pengajuan Pagu dinonaktifkan; perubahan pagu hanya dilakukan KASUBAG_PEK di Manajerial.)
  - **ADMIN**: Dashboard, Master Data (tidak ada menu Transaksi; Dashboard berisi informasi kesehatan sistem tanpa data keuangan).
- **Manajerial** hanya untuk Kasubag dan berisi antrian approval transaksi + perubahan pagu langsung (tidak melalui pengajuan PPTK).
- **Master Data** hanya untuk ADMIN.
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
