# SIMKEU Streamlit — Terhubung Google Sheets

## Langkah setup service account (sekali saja)

1. Buka [Google Cloud Console](https://console.cloud.google.com/).
2. Buat project baru (atau pakai yang sudah ada).
3. Aktifkan **Google Sheets API** dan **Google Drive API**.
4. Buat Service Account → Keys → Add Key → JSON. Unduh file JSON-nya.
5. Buka spreadsheet **DATABASE SIMKEU KECAMATAN CANDISARI 2027** di Drive.
6. Klik Share → tambahkan **email service account** (ada di JSON, field `client_email`) → beri akses **Editor**.
7. Di folder aplikasi, buat folder `.streamlit/` lalu salin `secrets.toml.example` menjadi `.streamlit/secrets.toml`.
8. Isi semua field di `secrets.toml` dari isi JSON service account.
9. Tambahkan `.streamlit/secrets.toml` ke `.gitignore`.

## Install & Jalankan

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Status saat ini
- Login dengan User Name + password.
- Bisa membaca dan menulis transaksi ke Google Sheets.
- Notifikasi Telegram.
- Dropdown menampilkan teks lengkap.
