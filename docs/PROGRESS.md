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

## Fase 1 — Model, Database & Sesi — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, tanpa layar), Python 3.12.3, SQLite 3.45.1

### Yang dikerjakan
- 1.1 `config.py`: `APP_NAME`, `IS_*`, `AppPaths`, `get_paths(platform=, env=, home=)` (urutan §6.1),
  `ensure_dirs()` (`0o700` di POSIX), `restrict_file()` (`0o600` di POSIX, no-op di Windows).
- 1.2 `models.py`: `AuthType`, `now_iso()`, `SessionConfig.validate()/target()`, `AppSettings`,
  `default_settings(mac=)` (font 12 di macOS).
- 1.3 `core/database.py`: PRAGMA `foreign_keys`/`secure_delete`, `quick_check`, skema v1 dibuat dalam
  satu transaksi bersama `user_version = 1`, file rusak → `pyssh.db.corrupt-YYYYmmdd-HHMMSS`,
  `user_version` lebih baru → `DatabaseVersionError` tanpa mengubah file.
- 1.4 `core/session_store.py`: CRUD, nama unik (casefold), `duplicate`, `touch`, `set_remember`,
  baris tidak valid dilewati + WARNING.
- 1.5 `core/settings_store.py`: default, clamp, tipe salah → default, JSON rusak → backup + default,
  penulisan atomic (`.tmp` → flush → fsync → `os.replace`) + `restrict_file`.
- 1.6 `logging_setup.py`: `RotatingFileHandler` 1 MB × 3, format §6.8, level INFO/DEBUG, logger
  `paramiko` WARNING/DEBUG.
- 1.7 `services.py`: `AppServices` (paths, database, session_store, settings_store, worker_factory).
- 1.8 `app.py`: argparse (`--demo`, `--connect`, `--debug`, `--version`), `ensure_dirs`, logging,
  excepthook (`sys` + `threading`; message box hanya di GUI thread), `Database.open()` (kode keluar 2
  untuk database lebih baru; peringatan file rusak ditampilkan setelah jendela muncul), stores,
  `MainWindow`, log `startup_ms`.
- 1.9 `strings.py`: teks aplikasi, database, dan validasi sesi.
- 1.10 Test: `test_architecture`, `test_config`, `test_models`, `test_database`, `test_session_store`,
  `test_settings_store`, ditambah `test_app`.

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 144 lulus, 0 gagal |
| pytest (integration) | dilewati — belum ada test integrasi (Fase 4) |
| Coverage modul target | config 100 %, models 100 %, database 95 %, session_store 98 %, settings_store 98 % |

### Kriteria penerimaan
- [x] AC-1.1 Quality Gate lulus; semua modul target ≥ 90 %.
- [x] AC-1.2 `test_schema_matches_spec` membandingkan `PRAGMA table_info` (nama, tipe, NOT NULL, PK)
  ketiga tabel dengan §6.3; ditambah cek UNIQUE `name_key`, FK `ON DELETE CASCADE`, dan CHECK.
- [x] AC-1.3 `test_architecture.py` lulus (A6 per tabel §5.3, A11 `print`, A12 `sys.platform`,
  `from __future__ import annotations` di semua modul).
- [x] AC-1.4 `python -m pyssh --version` → `PySSH 0.1.0`. Menjalankan aplikasi (tanpa `PYSSH_HOME`)
  membuat `~/.local/share/pyssh/` (`drwx------`), `logs/` (`drwx------`), `pyssh.db` (`-rw-------`,
  `user_version` 1, tabel `sessions`/`vault`/`secrets`), dan log berisi `startup startup_ms=11`.

### Checklist manual (diisi user)
- [ ] MT-1.1 Jalankan `python -m pyssh` lalu tutup. Cek folder data sesuai OS (§6.1): Windows
  `%APPDATA%\PySSH`, macOS `~/Library/Application Support/PySSH`, Linux `~/.local/share/pyssh`.
  Isinya `pyssh.db` dan `logs/pyssh.log` (berisi `startup_ms`). Di Linux/macOS: `ls -la` menunjukkan
  folder `drwx------` dan `pyssh.db` `-rw-------`. — OS: — hasil:

### Penyimpangan & keputusan
- `settings.json` dengan struktur tak terduga (bukan objek, `version` ≠ 1, `settings` bukan objek)
  diperlakukan sama dengan JSON rusak (backup + default); spesifikasi hanya menyebut "JSON rusak".
- `SessionConfig.validate()` menolak host yang berisi `[`/`]`; pembuangan bracket IPv6 dilakukan
  `SessionDialog` (§9.5) sebelum validasi.
- Nama salinan: `"<nama> (salinan)"`, lalu `"<nama> (salinan 2)"`, dst.; nama dasar dipotong agar
  total tetap ≤ 64 karakter.
- `set_remember()` melempar `KeyError` untuk id yang tidak ada (konsisten dengan `update()`).
- Windows tanpa `APPDATA`: fallback ke `~/AppData/Roaming/PySSH`.
- `app.main()` memakai `QApplication.instance()` bila sudah ada (agar bisa diuji dengan pytest-qt).
- Peringatan database rusak ditampilkan oleh `app.main()` setelah jendela muncul. Saat `SessionPanel`
  dibuat (Fase 5), tampilan ini tetap satu kali saja.
- `worker_factory` di `AppServices` bernilai `None` sampai `SSHWorker` dibuat (Fase 4).
- File log tidak di-`chmod 0o600` (§6.1 hanya menyebut `pyssh.db`, `settings.json`, `known_hosts`);
  folder `logs/` sudah `0o700`.

### Masalah yang diketahui
- Tidak ada.
