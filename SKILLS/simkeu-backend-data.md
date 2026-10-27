# Skill: Backend & Data (simkeu-backend-data)

## Keahlian
Backend Python/Streamlit, Google Sheets API (`st-gsheets-connection`, `gspread`, `google-auth`), integritas data, CRUD, workflow approval, dan manajemen transaksi keuangan.

## Struktur Laporan
**Melapor ke:** `SIMKEU Lead (simkeu-lead)`  
**Mengikuti instruksi dari:** Lead

## Tugas per Prioritas

### P1 — Tinggi (Tugas Utama)
1. **CRUD Master Data** — implementasi Tambah/Edit/Hapus untuk Wilayah, Sub Kegiatan, Rekening, dan Pengguna dari UI (hanya Admin yang boleh menulis).
2. **Approval Transaksi** — tambah status transaksi (Draft → Diajuan → Disetujui / Ditolak) dengan approval oleh Admin/KASUBAG_PEK sebelum masuk realisasi.
3. **Perubahan Pagu (write + approval)** — formulir ajukan perubahan pagu, workflow approval, dan simpan ke sheet `PERUBAHAN_PAGU`.
4. **Edit & Hapus Transaksi** — fitur ubah dan hapus transaksi yang sudah ada, dengan audit log siapa yang mengubah.
5. **Manajemen User via UI** — pindahkan manajemen user dari `secrets.toml` ke Google Sheets/database agar bisa diatur dari aplikasi.

### P2 — Menengah
6. **Upload Bukti Dukung SPJ (backend)** — integrasi upload file bukti dukungan ke Google Drive dan simpan tautan file-nya di sheet.
7. **Peringatan Pagu Habis (backend logic)** — deteksi realisasi mendekati/melebihi pagu dan siapkan data notifikasi.

### P3 — Rendah
8. **Audit Log** — catat semua aksi create/update/delete dengan user, waktu, dan detail perubahan ke sheet terpisah.
9. **Multi-Kecamatan (backend)** — tambah pemisahan data per kecamatan dengan kolom `kecamatan`.
10. **SQLite Fallback** — simpan sementara ke SQLite lokal saat Google Sheets tidak bisa diakses, sinkronisasi saat online kembali.

## Contoh Laporan ke Lead
```
[Laporan Backend & Data]
Tugas: CRUD Master Data — Rekening
Status: Selesai / Belum Selesai
File yang diubah: app.py (bagian Master Data tab Rekening)
Uji coba: Tambah/Edit/Hapus rekening berhasil ditulis ke Google Sheets
Keperluan review Lead: Ya / Tidak
```
