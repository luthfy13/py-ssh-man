# Changelog

Semua perubahan penting pada PySSH dicatat di file ini.

## [Belum dirilis]

### Ditambahkan
- Fase 0: kerangka proyek (`pyproject.toml`, struktur paket `src/pyssh`, `python -m pyssh`
  menampilkan jendela kosong "PySSH"), konfigurasi test (`pytest`, `pytest-qt`), dan
  dokumen `docs/SPEC.md` (v2.1) serta `docs/PROGRESS.md`.
- Fase 1: lokasi folder data per OS, database SQLite (skema v1, penanganan file rusak dan versi
  lebih baru), penyimpanan sesi, pengaturan `settings.json`, log berputar, `--version`.
