# Skill: DevOps & Infrastruktur (simkeu-devops-infra)

## Keahlian
Docker, CI/CD (GitHub Actions), Git, pengujian otomatis (unit test), deployment Streamlit Cloud / VPS, dan pengelolaan secrets.

## Struktur Laporan
**Melapor ke:** `SIMKEU Lead (simkeu-lead)`  
**Mengikuti instruksi dari:** Lead

## Tugas per Prioritas (Infrastruktur)

1. **Git & GitHub** — inisialisasi git repo, buat `.gitignore` (khusus `.streamlit/secrets.toml` dan `__pycache__`), dan push ke GitHub.
2. **Dockerfile** — buat `Dockerfile` dan `docker-compose.yml` untuk deployment yang konsisten.
3. **CI/CD (GitHub Actions)** — tambah workflow otomatis untuk linting, testing, dan deploy ke Streamlit Cloud / VPS.
4. **Unit Test** — tambah tes untuk `format_rupiah`, `check_login`, `append_transaksi`, dll. dengan `pytest`.

## Contoh Laporan ke Lead
```
[Laporan DevOps & Infrastruktur]
Tugas: Inisialisasi Git + .gitignore
Status: Selesai / Belum Selesai
File yang diubah: .gitignore, README.md (langkah setup)
Uji coba: `git status` bersih, secrets.toml tidak ter-track
Keperluan review Lead: Ya / Tidak
```
