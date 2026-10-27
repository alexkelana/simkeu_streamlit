# Skill: Reporting & Notifikasi (simkeu-reporting-notif)

## Keahlian
Export data ke Excel (`openpyxl`) dan PDF (`reportlab` / `fpdf`), notifikasi Telegram, laporan bulanan/tahunan, dan generate dokumen cetak (SPJ / surat keterangan realisasi).

## Struktur Laporan
**Melapor ke:** `SIMKEU Lead (simkeu-lead)`  
**Mengikuti instruksi dari:** Lead

## Tugas per Prioritas

### P1 — Tinggi
(Tidak ada tugas utama di fase P1; siapkan integrasi notifikasi Telegram yang sudah ada di `send_telegram` untuk dipakai Backend saat diperlukan Lead.)

### P2 — Menengah
1. **Export Excel / PDF** — tombol unduh laporan transaksi dan realisasi pagu ke Excel atau PDF.
2. **Laporan Bulanan / Tahunan** — ringkasan realisasi per bulan dan per tahun, difilter per sub kegiatan atau wilayah.
3. **Peringatan Pagu Habis (notifikasi)** — kirim notifikasi Telegram / in-app ketika realisasi mendekati atau melebihi pagu.

### P3 — Rendah
4. **Cetak SPJ / Surat** — generate dokumen SPJ atau surat keterangan realisasi yang bisa dicetak/diunduh.

## Contoh Laporan ke Lead
```
[Laporan Reporting & Notifikasi]
Tugas: Export Excel
Status: Selesai / Belum Selesai
File yang diubah: app.py (tombol unduh laporan)
Uji coba: Unduh file Excel berhasil dan dapat dibuka
Keperluan review Lead: Ya / Tidak
```
