# Laporan Progres PySSH

Laporan per fase sesuai template SPEC §11.13.

## Fase 0 — Setup Proyek — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, tanpa layar, `QT_QPA_PLATFORM=offscreen`), Python 3.12.3

### Yang dikerjakan
- 0.1 Repository sudah ada (`git init` tidak diperlukan); `.gitignore` sesuai daftar tugas 0.1.
- 0.2 `pyproject.toml` sama persis dengan §3.1.
- 0.3 Virtualenv `.venv` (Python 3.12.3) + `pip install -e ".[dev]"`. Versi terpasang:
  PySide6 6.11.2, paramiko 5.0.0, pyte 0.8.2, cryptography 50.0.2, pytest 9.1.1,
  pytest-qt 4.5.0, pytest-cov 7.1.0, ruff 0.16.9.
- 0.4 Seluruh struktur §5.2 dibuat: setiap modul berisi docstring + `from __future__ import annotations`.
- 0.5 `__main__.py` dan `app.main()` menampilkan `MainWindow` (`QMainWindow` kosong, judul dari
  `config.APP_NAME` = "PySSH", ukuran awal 1200×750).
- 0.6 `tests/conftest.py`: fixture autouse `PYSSH_HOME` → `tmp_path`; `QT_QPA_PLATFORM=offscreen`
  di Linux tanpa `DISPLAY`/`WAYLAND_DISPLAY`. `tests/test_smoke.py`: impor semua modul paket,
  versi, dan `MainWindow` dibuat lewat `qtbot`.
- 0.7 `docs/SPEC.md` (salinan v2.1, identik byte per byte), `docs/PROGRESS.md`, `CHANGELOG.md`.

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus (69 file) |
| pytest (unit) | 38 lulus, 0 gagal |
| pytest (integration) | dilewati — belum ada test integrasi di Fase 0 (0 test terkumpul) |
| Coverage modul target | tidak ada target di Fase 0 (total 82 %) |

### Kriteria penerimaan
- [x] AC-0.1 `pip install -e ".[dev]"` sukses tanpa error.
- [x] AC-0.2 `python -m pyssh` membuka jendela "PySSH"; ditutup tanpa error di konsol.
  Diverifikasi headless: `app.main()` dijalankan, jendela tampil dengan judul "PySSH", ditutup
  otomatis setelah 200 ms, `main()` mengembalikan 0, tanpa output error. Perintah `pyssh`
  (entry point) juga berjalan.
- [x] AC-0.3 Quality Gate lulus (38 test ≥ 2).

### Checklist manual (diisi user)
- [ ] MT-0.1 Di desktop: aktifkan venv, jalankan `python -m pyssh` → jendela berjudul "PySSH"
  muncul; tutup jendela → tidak ada error di konsol. — OS: — hasil:

### Penyimpangan & keputusan
- Fixture `fast_kdf` (§10.1) belum dibuat karena `KdfParams` baru ada di Fase 2; akan ditambahkan di Fase 2.
- `config.py` sudah berisi `APP_NAME`, `APP_ORG`, dan `IS_*` (§7.1) karena judul jendela wajib
  memakai `config.APP_NAME` (§1.4). `AppPaths`/`get_paths()` tetap dikerjakan di Fase 1.
- `resources/ansi_demo.txt` dan `resources/icon.png` belum dibuat (dihasilkan oleh tools di Fase 3
  dan Fase 8); folder `resources/` diisi `.gitkeep` agar tercatat di git.
- `tests/integration/conftest.py` masih kosong (logika skip server uji dikerjakan di Fase 4).
- Lingkungan headless butuh paket sistem `libegl1` agar PySide6 bisa dimuat (tidak tercantum di §3);
  dipasang bersama `libxcb-cursor0`. Akan dicatat di README (Fase 8).
- Versi terpasang lebih baru dari minimum di §3: paramiko 5.0.0 (spesifikasi ditulis untuk 3.x).
  `PKey.from_path` dan `pkey.UnknownKeyType` terverifikasi ada; perilaku API lain diverifikasi
  di fase yang memakainya (Lampiran B).

### Masalah yang diketahui
- Tidak ada.
