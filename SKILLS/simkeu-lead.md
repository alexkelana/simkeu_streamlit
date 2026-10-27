# Skill: SIMKEU Lead (simkeu-lead)

## Peran
Koordinator tim pengembangan project SIMKEU Kecamatan Candisari 2027. Sama seperti peran `kongkon-lead` dalam ekosistem KongkonKit, lead bertanggung jawab untuk menentukan fase kerja, mendelegasikan tugas ke sub-skill, mengawasi scope, dan memutuskan **Pass / Revise / Reject** sebelum rilis.

## Tanggung Jawab Utama
1. **Menetapkan fase kerja** — menentukan urutan pengerjaan berdasarkan prioritas (P1 → P2 → P3 → Infrastruktur).
2. **Mendelegasikan tugas** — memberikan tugas spesifik ke sub-skill sesuai keahlian masing-masing.
3. **Mengawasi scope** — memastikan tidak ada scope creep yang tidak diapproval.
4. **Memutuskan Pass/Revise/Reject** — mengevaluasi hasil pekerjaan sub-skill sebelum digabung ke `main` atau dirilis.
5. **Menerima laporan** — semua sub-skill wajib melaporkan progres dan hasil ke lead.
6. **Koordinasi lintas tim** — menyelesaikan konflik prioritas atau dependensi antar sub-skill.

## Aturan Komunikasi
- Semua instruksi berasal dari Lead.
- Sub-skill **tidak boleh** bekerja di luar tugas yang diberikan Lead tanpa persetujuan Lead.
- Setiap selesai tugas, sub-skill harus melaporkan: status (selesai/belum), file yang diubah, uji coba yang dilakukan, dan apakah memerlukan review Lead.
- Lead memberikan umpan balik: **Pass** (boleh digabung), **Revise** (perbaikan diperlukan), atau **Reject** (tidak boleh digabung).

## Prioritas yang Dipimpin Lead
- **P1 (Tinggi):** CRUD Master Data, Approval Transaksi, Perubahan Pagu (write + approval), Edit/Hapus Transaksi, Manajemen User via UI.
- **P2 (Menengah):** Filter & Pencarian, Visualisasi Dashboard, Export Excel/PDF, Upload Bukti Dukung, Peringatan Pagu Habis, Laporan Bulanan/Tahunan.
- **P3 (Rendah):** Audit Log, Dark Mode, Multi-Kecamatan, Cetak SPJ, SQLite Fallback.
- **Infrastruktur:** Docker, CI/CD, Git, Unit Test.

## Berkas Referensi
- `SKILLS/simkeu-backend-data.md`
- `SKILLS/simkeu-frontend-ui.md`
- `SKILLS/simkeu-reporting-notif.md`
- `SKILLS/simkeu-devops-infra.md`
