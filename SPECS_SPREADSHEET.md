# 📊 Format Spreadsheet — SIMKEU Kecamatan Candisari 2027

Berikut adalah format worksheet yang diperlukan di Google Sheets untuk aplikasi SIMKEU. Buat satu spreadsheet dengan beberapa worksheet (tab) berikut.

---

## 1. PENGGUNA (Manajemen User)

Digunakan untuk login dan manajemen user. **Wajib memiliki kolom `user_name` dan `password`.**

| Kolom | Tipe | Wajib | Contoh | Keterangan |
|-------|------|-------|--------|------------|
| `user_name` | Text | Ya | `admin` | Username untuk login (case-insensitive) |
| `password` | Text | Ya | `admin123` | Password untuk login |
| `nama` | Text | Ya | `Budi Santoso` | Nama lengkap user (tampilkan di sidebar) |
| `peran` | Text | Ya | `ADMIN` | Peran: `ADMIN`, `KASUBAG_PEK`, atau `PPTK` |

**Contoh data:**

| user_name | password | nama | peran |
|-----------|----------|------|-------|
| admin | admin123 | Budi Santoso | ADMIN |
| kasubag | kasubag123 | Siti Rahayu | KASUBAG_PEK |
| pptk1 | pptk123 | Agus Setiawan | PPTK |

---

## 2. MASTER_WILAYAH (Data Wilayah)

Digunakan di menu Master Data → tab Wilayah.

| Kolom | Tipe | Wajib | Contoh | Keterangan |
|-------|------|-------|--------|------------|
| `nama_wilayah` | Text | Ya | `Kecamatan Candisari` | Nama wilayah |
| `kode_wilayah` | Text | Ya | `KC01` | Kode wilayah |

**Contoh data:**

| nama_wilayah | kode_wilayah |
|--------------|--------------|
| Kecamatan Candisari | KC01 |
| Kelurahan Candisari | KL01 |
| Kelurahan Jebres | KL02 |

---

## 3. MASTER_REKENING (Data Rekening Belanja)

Digunakan di menu Master Data → tab Rekening, dan dropdown rekening pada formulir transaksi.

| Kolom | Tipe | Wajib | Contoh | Keterangan |
|-------|------|-------|--------|------------|
| `kode_rekening` | Text | Ya | `5.2.1.01` | Kode rekening belanja |
| `uraian_rekening` | Text | Ya | `Honorarium PPTK` | Uraian rekening |

**Contoh data:**

| kode_rekening | uraian_rekening |
|---------------|-----------------|
| 5.2.1.01 | Honorarium PPTK |
| 5.2.1.02 | Bahan Tulis Kantor |
| 5.2.1.03 | Sewa Peralatan |

---

## 4. MASTER_KEGIATAN (Data Sub Kegiatan)

Digunakan di menu Master Data → tab Sub Kegiatan, dropdown sub kegiatan pada formulir transaksi, dan dashboard.

| Kolom | Tipe | Wajib | Contoh | Keterangan |
|-------|------|-------|--------|------------|
| `subkegiatan` | Text | Ya | `SK001` | Kode sub kegiatan |
| `nama_kegiatan` | Text | Ya | `Pembinaan Keuangan Desa` | Nama kegiatan |
| `pagu_awal` | Angka | Ya | `50000000` | Pagu awal (Rp) |

**Contoh data:**

| subkegiatan | nama_kegiatan | pagu_awal |
|-------------|---------------|-----------|
| SK001 | Pembinaan Keuangan Desa | 50000000 |
| SK002 | Pengawasan Keuangan | 30000000 |
| SK003 | Pelaporan Keuangan | 20000000 |

---

## 5. TRANSAKSI (Data Transaksi)

Digunakan di menu Transaksi dan Dashboard. Sheet ini akan ditulis oleh aplikasi saat ada transaksi baru.

| Kolom | Tipe | Wajib | Contoh | Keterangan |
|-------|------|-------|--------|------------|
| `NO` | Angka | Ya | `1` | Nomor urut (diisi otomatis aplikasi) |
| `SUB KEGIATAN` | Text | Ya | `SK001 - Pembinaan Keuangan Desa` | Sub kegiatan (format: kode - nama) |
| `KODE REKENING BELANJA` | Text | Ya | `5.2.1.01` | Kode rekening |
| `PENGELOMPOKAN BELANJA (#)` | Text | Tidak | `Bahan Konsumsi` | Pengelompokan belanja |
| `URAIAN` | Text | Ya | `Honorarium bulanan PPTK` | Uraian transaksi |
| `JENIS TRANSAKSI (UP/GU/LS)` | Text | Ya | `UP/GU` | Jenis: `UP/GU` atau `LS` |
| `NOMINAL` | Angka | Ya | `2500000` | Nominal transaksi (Rp) |
| `TANGGAL PENGAJUAN` | Text | Ya | `01/01/2027` | Tanggal pengajuan (DD/MM/YYYY) |
| `BUKTI DUKUNG SPJ` | Text | Tidak | `SPJ-001/2027` | Tautan atau nomor bukti dukungan |
| `PPTK` | Text | Ya | `Agus Setiawan (pptk1)` | Nama dan user PPTK |
| `STATUS` | Text | Tidak | `Draft` | Status: `Draft`, `Diajuan`, `Disetujui`, `Ditolak` (diisi aplikasi) |
| `DISETUJUI_OLEH` | Text | Tidak | `Budi Santoso` | Nama yang menyetujui (diisi aplikasi) |
| `TANGGAL_APPROVAL` | Text | Tidak | `02/01/2027` | Tanggal approval (diisi aplikasi) |

**Catatan:** Kolom `STATUS`, `DISETUJUI_OLEH`, dan `TANGGAL_APPROVAL` akan ditambahkan otomatis oleh aplikasi jika belum ada.

**Contoh data:**

| NO | SUB KEGIATAN | KODE REKENING BELANJA | PENGELOMPOKAN BELANJA (#) | URAIAN | JENIS TRANSAKSI | NOMINAL | TANGGAL PENGAJUAN | BUKTI DUKUNG SPJ | PPTK | STATUS |
|----|--------------|-----------------------|---------------------------|--------|-----------------|---------|-------------------|------------------|------|--------|
| 1 | SK001 - Pembinaan Keuangan Desa | 5.2.1.01 | Bahan Konsumsi | Honorarium bulanan PPTK | UP/GU | 2500000 | 01/01/2027 | SPJ-001/2027 | Agus Setiawan (pptk1) | Disetujui |
| 2 | SK002 - Pengawasan Keuangan | 5.2.1.02 | Alat Tulis | Pembelian spidol | LS | 150000 | 02/01/2027 | - | Agus Setiawan (pptk1) | Draft |

---

## 6. PERUBAHAN_PAGU (Perubahan Pagu)

Digunakan di menu Perubahan Pagu.

| Kolom | Tipe | Wajib | Contoh | Keterangan |
|-------|------|-------|--------|------------|
| `SUB KEGIATAN` | Text | Ya | `SK001` | Kode sub kegiatan |
| `PAGU_BARU` | Angka | Ya | `60000000` | Pagu baru (Rp) |
| `ALASAN` | Text | Ya | `Penambahan dana dari pemda` | Alasan perubahan |
| `DIAJUKAN_OLEH` | Text | Ya | `Budi Santoso` | Nama yang mengajukan |
| `TANGGAL_AJUAN` | Text | Ya | `05/01/2027` | Tanggal pengajuan (DD/MM/YYYY) |
| `STATUS` | Text | Tidak | `Menunggu Approval` | Status: `Menunggu Approval`, `Disetujui`, `Ditolak` |

**Contoh data:**

| SUB KEGIATAN | PAGU_BARU | ALASAN | DIAJUKAN_OLEH | TANGGAL_AJUAN | STATUS |
|--------------|-----------|--------|---------------|---------------|--------|
| SK001 | 60000000 | Penambahan dana dari pemda | Budi Santoso | 05/01/2027 | Menunggu Approval |

---

## 7. AUDIT_LOG (Riwayat Perubahan)

Digunakan di menu Master Data → tab Audit Log. Sheet ini akan ditulis otomatis oleh aplikasi.

| Kolom | Tipe | Contoh | Keterangan |
|-------|------|--------|------------|
| `WAKTU` | Text | `01/01/2027 08:30:00` | Waktu aksi dilakukan |
| `USER` | Text | `Budi Santoso` | User yang melakukan aksi |
| `AKSI` | Text | `CREATE`, `UPDATE`, `DELETE`, `UPDATE_STATUS` | Jenis aksi |
| `TABEL` | Text | `TRANSAKSI`, `MASTER_REKENING`, `PENGGUNA` | Tabel yang diubah |
| `RECORD_ID` | Text | `1`, `SK001` | ID record yang diubah |
| `OLD_VALUES` | Text | `{"STATUS": "Draft"}` | Nilai sebelum diubah |
| `NEW_VALUES` | Text | `{"STATUS": "Disetujui"}` | Nilai setelah diubah |

---

## 📋 Ringkasan Struktur Spreadsheet

```
Spreadsheet: DATABASE SIMKEU KECAMATAN CANDISARI 2027
├── Worksheet: PENGGUNA
├── Worksheet: MASTER_WILAYAH
├── Worksheet: MASTER_REKENING
├── Worksheet: MASTER_KEGIATAN
├── Worksheet: TRANSAKSI
├── Worksheet: PERUBAHAN_PAGU
└── Worksheet: AUDIT_LOG (dibuat otomatis aplikasi)
```

---

## ⚙️ Langkah Setup Google Sheets

1. Buat spreadsheet baru di Google Drive dengan nama `DATABASE SIMKEU KECAMATAN CANDISARI 2027`
2. Buat 6 worksheet (tab) sesuai daftar di atas dengan nama yang **sama persis** (case-sensitive):
   - `PENGGUNA`
   - `MASTER_WILAYAH`
   - `MASTER_REKENING`
   - `MASTER_KEGIATAN`
   - `TRANSAKSI`
   - `PERUBAHAN_PAGU`
3. Isi kolom header pada setiap worksheet sesuai tabel di atas
4. Share spreadsheet ke email Service Account Google Cloud dengan akses **Editor**
5. Masukkan Spreadsheet URL dan kunci Service Account di `.streamlit/secrets.toml`

---

## 🔐 Catatan Keamanan

- **Jangan** menambahkan column `password` ke dalam tampilan publik
- Pastikan Service Account memiliki akses Editor ke spreadsheet
- File `.streamlit/secrets.toml` **jangan di-commit ke Git** (sudah di `.gitignore`)
