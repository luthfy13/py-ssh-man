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

## Fase 2 — Vault & Enkripsi — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, tanpa layar), Python 3.12.3, cryptography 50.0.2

### Yang dikerjakan
- 2.1 `core/crypto.py`: `KdfParams` (default N=2¹⁷, r=8, p=1), `derive_key` (NFC → UTF-8 → scrypt
  32 byte), `new_salt`, `new_key`, `encrypt` (AES-256-GCM, nonce acak 12 byte), `decrypt`
  (`InvalidTag`/`ValueError` → `DecryptError`).
- 2.2 `core/vault.py`: state UNINITIALIZED/LOCKED/UNLOCKED; `initialize`, `unlock` (parameter KDF dari
  tabel `vault`, log `unlock_ms`), `lock`, `change_master_password` (salt baru + KDF default terbaru,
  satu transaksi), `reset` (satu transaksi), `encrypt_secret`/`decrypt_secret` dengan AAD
  `b"pyssh/secret/v1/" + session_id`; DEK dibungkus dengan AAD `b"pyssh/dek/v1"`.
- 2.3 `core/secret_store.py`: `can_store`, `get_secret`, `set_secret` (INSERT OR REPLACE +
  `remember_secret = 1`), `delete_secret`, `has_secret`.
- 2.4 `ui/vault_dialogs.py`: `CreateMasterPasswordDialog`, `UnlockDialog` (Lewati/Batal, tautan
  "Lupa master password?"), `ChangeMasterPasswordDialog`, konfirmasi reset, `ensure_vault_unlocked()`;
  kursor tunggu (`ui/dialogs.py: wait_cursor`) selama scrypt.
- 2.5 `AppServices` + `vault` & `secret_store`; startup langkah 6: vault LOCKED → `UnlockDialog`
  (mode startup); waktu dialog dikurangkan dari `startup_ms`; vault dikunci saat aplikasi selesai.
- 2.6 Menu Berkas (Buat/Buka/Kunci/Ganti/Reset sesuai state, Keluar dengan `QuitRole`), label status
  "Vault: …", `refresh_vault_ui()`.
- 2.7 Test: `test_crypto`, `test_vault`, `test_secret_store`, `test_vault_dialogs`, ditambah
  `test_main_window` (menu vault) dan test startup di `test_app`. Fixture `fast_kdf` dan `services`
  ditambahkan ke `tests/conftest.py`.

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 195 lulus, 0 gagal |
| pytest (integration) | dilewati — belum ada test integrasi (Fase 4) |
| Coverage modul target | crypto 100 %, vault 98 %, secret_store 100 % (vault_dialogs 99 %) |

### Kriteria penerimaan
- [x] AC-2.1 Quality Gate lulus; coverage `core/crypto`, `core/vault`, `core/secret_store` ≥ 95 %.
- [x] AC-2.2 `test_raw_database_file_contains_no_plaintext`: bytes mentah `pyssh.db` tidak memuat
  secret uji (UTF-8 maupun UTF-16-LE).
- [x] AC-2.3 KDF default (scrypt N=131072, r=8, p=1) di mesin dev: `unlock_ms` = 398, 401, 379 ms
  (berhasil) dan 376 ms (password salah); lewat dialog startup sungguhan: 783 ms (salah) dan 378 ms
  (benar). Semua dalam rentang 200–2000 ms.
- [x] AC-2.4 `test_log_contains_no_secrets`: setelah initialize/unlock salah/unlock benar/ganti
  password dengan log level DEBUG, file log tidak memuat master password, secret, DEK, nonce, atau
  ciphertext (teks maupun hex/bytes mentah).

Verifikasi tambahan tanpa layar (aplikasi sungguhan, tanpa monkeypatch): vault LOCKED → dialog startup
muncul; password salah → "Master password salah."; password benar → jendela utama tampil dengan
"Vault: terbuka"; tombol "Lewati" → jendela utama tampil dengan "Vault: terkunci".

### Checklist manual (diisi user)
- [ ] MT-2.1 Berkas → Buat Master Password → restart → dialog buka vault muncul; password salah
  menampilkan error; password benar membuka; status bar "Vault: terbuka". — OS: — hasil:
- [ ] MT-2.2 Pilih **Lewati** saat startup → status "Vault: terkunci"; Berkas → Buka Vault berfungsi.
  — OS: — hasil:
- [ ] MT-2.3 Berkas → Ganti Master Password → restart → password baru berhasil, password lama gagal.
  — OS: — hasil:
- [ ] MT-2.4 Di dialog buka vault klik "Lupa master password?" → konfirmasi "Hapus Data Login" →
  status "Vault: belum dibuat" (dialog buat master password langsung ditawarkan bila dibuka lewat
  alur yang membutuhkan vault). — OS: — hasil:

### Penyimpangan & keputusan
- `Vault.add_listener()` ditambahkan (tanpa Qt) agar setiap perubahan state, dari mana pun asalnya
  (menu, `SessionDialog`, `TerminalTab`), memanggil `MainWindow.refresh_vault_ui()` (§9.3).
- `Vault.unlock()` pada vault UNINITIALIZED mengembalikan `False`.
- `change_master_password()` yang berhasil membiarkan vault dalam state UNLOCKED (DEK sudah terbuka
  untuk membungkus ulang), termasuk bila sebelumnya LOCKED.
- `ensure_vault_unlocked()`: bila user mereset vault dari `UnlockDialog`, dialog pembuatan master
  password langsung menyusul (alternatifnya mengembalikan `False`, yang membuat secret tidak tersimpan).
- Menu "Reset Data Login…" dan "Ganti Master Password…" hanya terlihat bila vault sudah dibuat.
- `SecretStore.set_secret()` melempar `KeyError` bila sesi tidak ada (sebelum insert).
- Item menu Sesi Baru (Fase 5) dan Pengaturan (Fase 8) ditambahkan di fase masing-masing.

### Masalah yang diketahui
- Di mode `QT_QPA_PLATFORM=offscreen` Qt mencetak "This plugin does not support
  propagateSizeHints()" saat dialog ditampilkan; ini pesan plugin offscreen, bukan error aplikasi.
