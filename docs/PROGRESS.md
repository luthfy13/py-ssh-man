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

## Fase 3 — Terminal Offline — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, `QT_QPA_PLATFORM=offscreen`), Python 3.12.3,
PySide6 6.11.2, pyte 0.8.2

### Verifikasi API (Lampiran B) terhadap versi terpasang
- pyte 0.8.2: atribut `buffer`, `cursor` (`hidden`), `margins`, `mode`, `title`, `dirty` ada;
  `Screen.index()` membuang baris teratas dengan me-*rebind* `buffer[y]` (aman untuk disimpan di
  scrollback); `report_device_status`/`report_device_attributes` memanggil `write_process_input`
  (DSR → `ESC[1;1R`, DA → `ESC[?6c`); private mode digeser `<< 5`; `resize(lines, columns)`;
  `ByteStream` memakai incremental UTF-8 decoder; SGR 33 → `"brown"`; 256/truecolor → hex 6 digit
  huruf kecil; karakter lebar → sel berikutnya `data == ""`.
- **`pyte.modes` tidak punya konstanta `DECCKM`** → dipakai konstanta sendiri sesuai §8.1.1.
- **Bug pyte 0.8.2: `graphics.BG_AIXTERM[105] == "bfightmagenta"`** (salah ketik). Tanpa
  penanganan, latar SGR 105 tampil sebagai warna default (terlihat di screenshot uji). Ditambahkan
  alias di `ANSI_NAME_TO_INDEX`; `test_every_pyte_color_name_is_known` memastikan semua nama warna
  pyte dikenali.
- `FG_BG_256[196] == FG_BG_256[9] == "ff0000"` — dicatat untuk pemetaan 16 warna (SHOULD, Fase 8).
- PySide6 6.11.2: `Qt.Key` adalah `IntEnum`; `Qt.KeyboardModifier` adalah `Flag` (bukan int);
  `QKeyEvent.key()` mengembalikan `int`; `AA_MacDontSwapCtrlAndMeta` tersedia.

### Yang dikerjakan
- 3.1 `terminal/colors.py`: `Theme`, `ANSI_NAME_TO_INDEX`, `resolve_color()`.
- 3.2 `shortcuts.py`: tabel Windows/Linux dan macOS (kode dasar + hasil Shift), `match()`,
  `is_app_shortcut()`, `zoom_wheel_modifier()`.
- 3.3 `terminal/keymap.py`: `key_to_bytes()` urutan §8.3.5 (shortcut → Meta → Shift+PgUp/PgDn →
  tombol khusus → AltGr → Ctrl → Alt → teks). `app.py`: `AA_MacDontSwapCtrlAndMeta` sebelum
  `QApplication` di macOS.
- 3.4 `terminal/emulator.py`: `_ScrollbackScreen` + `TerminalEmulator` sesuai API §8.1.3.
- 3.5 `terminal/widget.py`: font per platform, render per *run*, pump 16 KiB/≤ 8 ms, repaint
  coalescing 16 ms, backpressure 4 MiB/1 MiB, keyboard + ShortcutOverride, IME, seleksi
  (drag, double-click kata), clipboard, bracketed paste, menu konteks, wheel (notch & pixel),
  zoom 6–32, resize debounce 120 ms, instrumentasi `PYSSH_DEBUG_PERF=1`.
- 3.6 `terminal/view.py`: widget + scrollbar tersinkron (`blockSignals`).
- 3.7 `terminal/demo_backend.py` + key inspector; `tools/make_ansi_demo.py` →
  `resources/ansi_demo.txt`.
- 3.8 `MainWindow.open_demo_tab()`, `QTabWidget`, label `cols×rows`, menu Sesi/Tampilan dengan
  QAction yang shortcut-nya dibangun dari `shortcuts.py` (teks tabel + setiap varian kode tombol).
- 3.9 `tools/bench_emulator.py`.
- 3.10 Test: `test_colors`, `test_shortcuts`, `test_keymap`, `test_emulator`, `test_widget`, ditambah
  `test_demo_backend` dan test tab di `test_main_window`.

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 472 lulus, 0 gagal |
| pytest (integration) | dilewati — belum ada test integrasi (Fase 4) |
| Coverage modul target | emulator 100 %, keymap 100 %, colors 100 %, shortcuts 100 % (widget 97 %) |

### Kriteria penerimaan
- [x] AC-3.1 Quality Gate lulus; coverage modul target ≥ 85 %.
- [x] AC-3.2 `test_keymap.py` = 126 kasus (Windows/Linux dan macOS); `test_emulator.py` mencakup
  semua kasus §10.2 (teks, SGR 31, 256-color, DECCKM, bracketed paste, DSR, scrollback penuh
  100/10/50, scroll region parsial, resize, karakter lebar, UTF-8 terpotong, `text_between`).
- [x] AC-3.3 `python tools/bench_emulator.py`: 5,0 MB dalam 6,75 s → **0,740 MB/s** (target
  informatif ≥ 0,3 MB/s).

Verifikasi visual tanpa layar: `python -m pyssh --demo` dirender ke PNG lalu diperiksa — 16 warna
fg/bg, grid 256, gradasi truecolor, atribut teks, box drawing tersambung, `漢字` dua kolom, key
inspector (`\x1b` cyan + `[A`), status bar `130×38`.

### Checklist manual (diisi user, jalankan `python -m pyssh --demo`)
- [ ] MT-3.1 16 warna fg/bg, grid 256 warna, dan gradasi truecolor tampil benar. — OS: — hasil:
- [ ] MT-3.2 Bold, italic, underline, reverse, strikethrough tampil benar. — OS: — hasil:
- [ ] MT-3.3 Box drawing tersambung tanpa celah; `漢字` menempati 2 kolom per karakter; teks Bahasa
  Indonesia benar. — OS: — hasil:
- [ ] MT-3.4 Key inspector: tekan Up/Down/Left/Right (`\x1b[A` … `\x1b[D`), Home/End
  (`\x1b[H`/`\x1b[F`), F1–F12 (`\x1bOP` … `\x1b[24~`), Ctrl+A (`\x01`), Ctrl+C (`\x03`), Alt+x
  (`\x1bx`), Shift+Tab (`\x1b[Z`). macOS: Ctrl+C → `\x03`; Option+e menghasilkan karakter aksen
  (atau `\x1be` bila "Option sebagai Meta" aktif, Fase 8). — OS: — hasil:
- [ ] MT-3.5 Ubah ukuran jendela → status bar menampilkan `cols×rows` baru; tampilan tidak rusak.
  — OS: — hasil:
- [ ] MT-3.6 Wheel dan Shift+PageUp menampilkan scrollback; mengetik apa saja kembali ke bawah.
  — OS: — hasil:
- [ ] MT-3.7 Drag seleksi → tempel di editor teks lain sama persis; klik kanan → menu konteks
  (Salin/Tempel/Bersihkan Scrollback) berfungsi. — OS: — hasil:
- [ ] MT-3.8 Ctrl+wheel (Cmd+wheel di macOS) mengubah ukuran font (batas 6–32); grid menyesuaikan.
  — OS: — hasil:

### Penyimpangan & keputusan
- `key_to_bytes()` mengikuti urutan §8.3.5 secara harfiah: Ctrl+Shift+C/V (shortcut *widget*)
  menghasilkan `\x03`/`\x16` bila dipanggil langsung; `keyPressEvent` mencegatnya lebih dulu
  (§8.4.5 langkah 2), sehingga tidak pernah terkirim.
- Ctrl+? (`Key_Question`) → `\x7f` sesuai tabel §8.3.4 (catatan §8.3.4 menyebut pasangan
  `Key_Slash`/`Key_Question`, tetapi tabel memetakan keduanya ke byte berbeda; tabel diikuti).
- `TerminalEmulator.scrolled_total` (penghitung baris yang pernah masuk scrollback) ditambahkan agar
  tampilan yang sedang di-scroll ke atas tetap diam walau scrollback sudah penuh.
- Tiap QAction mendapat beberapa `QKeySequence`: teks dari tabel ditambah kombinasi untuk setiap
  kode tombol (`Key_Equal`/`Key_Plus`, dst.), agar cocok dengan apa pun yang dilaporkan Qt.
- `ruff`: `allowed-confusables = ["×", "–", "´"]` ditambahkan di `pyproject.toml` (karakter
  disengaja: format `cols×rows` di UI, rentang di dokumentasi, karakter Option di test macOS).
- Triple-click (COULD) dan primary selection Linux (COULD, Fase 8) belum dibuat.
- `write_local(text, color)` menerima nama warna ANSI (`"red"`, `"yellow"`, `"cyan"`, …).
- Demo memakai teks hitam pada latar terang agar nomor warna terbaca.

### Masalah yang diketahui
- Perilaku keyboard nyata (AltGr Windows, Option/Cmd macOS, IME, Wayland) hanya bisa dipastikan
  lewat MT-3.4 dan MT-9.x; test otomatis memakai event sintetis.

## Fase 4 — Koneksi SSH dengan Password — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, offscreen), Python 3.12.3, paramiko 5.0.0
**Server uji:** Opsi A (Docker) tidak tersedia — daemon Docker tidak berjalan
(`/var/run/docker.sock` tidak ada). Dipakai **Opsi C**: `openssh-server` 9.6p1 di container,
`sshd -p 2222`, user `tester`/`secret`, key uji di `tests/keys/` (di-ignore git).

### Verifikasi API (Lampiran B) terhadap paramiko 5.0.0
- `SSHClient.connect(..., timeout, banner_timeout, auth_timeout, allow_agent, look_for_keys)`,
  `invoke_shell(term, width, height)`, `Channel.resize_pty/recv/sendall/closed/exit_status_ready/
  recv_exit_status/fileno`, `Transport.set_keepalive/is_active`,
  `MissingHostKeyPolicy.missing_host_key(client, hostname, key)` — ada dengan signature sesuai.
- `SSHClient.save_host_keys()` memuat ulang file `known_hosts` sebelum menulis (penyimpanan dari
  beberapa tab tidak saling menimpa).
- `Transport.stop_thread()` tidak menunggu lama setelah `packetizer.close()` → `stop()` dari GUI
  thread tidak memblokir.
- `NoValidConnectionsError` ⊂ `OSError`; `BadHostKeyException` ⊂ `SSHException`;
  `PasswordRequiredException` dan `BadAuthenticationType` ⊂ `AuthenticationException`;
  `socket.timeout is TimeoutError` → urutan §7.10 diperlukan dan diuji.
- **`PKey.from_path(path, password=None)`** — parameternya bernama `password`, bukan `passphrase`
  seperti tertulis di §7.8 (dipakai di Fase 7).
- `HostKeys.__delitem__` hanya menghapus satu entri per panggilan → `forget_host` mengulang sampai
  semua jenis key host tersebut terhapus.

### Yang dikerjakan
- 4.1 `core/errors.py`: `UserError`, `HostKeyRejected`, `describe_error()` (12 baris §7.10).
- 4.2 `core/known_hosts.py`: `ensure_file` (+ `0o600`), `fingerprint_sha256`, `entry_name`,
  `forget_host` dengan lock modul.
- 4.3 `core/ssh_worker.py`: `ConnectParams` (secret `repr=False`), `HostKeyDecision`,
  `WorkerProtocol`, `SSHWorker` (thread daemon `ssh-<host>`, queue keluar, resize terbaru, backpressure,
  `stop()` tanpa menunggu, `join()`), `_InteractivePolicy`.
- 4.4 `ui/dialogs.py`: `PasswordDialog.ask()`, `HostKeyDialog.ask()` (tutup = REJECT), `confirm()`.
- 4.5 `ui/terminal_tab.py`: `TabState`, state machine §9.6.1, banner (Hubungkan Ulang/Tutup Tab),
  alur §9.6.3 untuk password termasuk retry maks. 3×, host key dialog, pesan `E_HOSTKEY_CHANGED`,
  R/Enter untuk reconnect; sinyal dari worker lama diabaikan.
- 4.6 `MainWindow.open_adhoc()`, `open_session()`, `active_tab()`, aksi Hubungkan Ulang, teks status
  kiri; `--connect user@host[:port]` (juga `[ipv6]:port`) dengan pesan error argparse.
- 4.7 `tests/fakes.py`: `FakeWorker` + `WorkerFactory`.
- 4.8 Test: `test_errors`, `test_known_hosts`, `test_terminal_tab`, `test_dialogs`, parsing
  `--connect` di `test_app`, `integration/conftest.py` + `integration/test_ssh_password.py`.

### Bug yang ditemukan & diperbaiki
- **Race `exit-status`**: OpenSSH dapat mengirim EOF channel sebelum `exit-status`. Loop I/O lalu
  melaporkan "Koneksi terputus." alih-alih "Sesi berakhir (kode keluar N)". Terukur 10 dari 20
  percobaan sebelum perbaikan; setelah `_wait_exit_status()` (tunggu ≤ 1 s selama transport aktif)
  30/30 benar. Regresi dijaga `test_12_exit_status_reported_reliably`.

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 549 lulus, 0 gagal |
| pytest (integration) | 12 lulus (11 skenario §10.3 + 1 regresi) |
| Coverage modul target | errors 100 %, known_hosts 100 %, ssh_worker 91 % (unit + integrasi) |

### Kriteria penerimaan
- [x] AC-4.1 Quality Gate lulus; coverage `core/errors`, `core/known_hosts` ≥ 90 %,
  `core/ssh_worker` ≥ 70 %.
- [x] AC-4.2 Seluruh 11 skenario §10.3 lulus terhadap `sshd` nyata.
- [x] AC-4.3 `test_ui_does_not_import_paramiko`: tidak ada modul `ui/` yang mengimpor `paramiko`;
  semua panggilan jaringan ada di `SSHWorker._run` (thread worker).

Verifikasi tambahan tanpa layar (aplikasi sungguhan, `--connect tester@127.0.0.1:2222`): dialog
password → dialog host key (fingerprint sama dengan `ssh-keygen -lf
/etc/ssh/ssh_host_ed25519_key.pub`) → "Terhubung"; ketikan lewat keyboard simulasi menghasilkan
`pyssh-42`; `tput cols/lines` = `130 38` = grid status bar; `exit` → banner "Sesi berakhir (kode
keluar 0)."; tombol R → menghubungkan ulang.

### Checklist manual (diisi user; server Linux nyata, `python -m pyssh --connect user@host`)
- [ ] MT-4.1 `ls --color`, `htop`, `vim`, `nano`, `less /etc/services` tampil dan bisa dioperasikan;
  setelah keluar dari vim, prompt bisa dipakai normal. — OS: — hasil:
- [ ] MT-4.2 `ping 8.8.8.8` lalu Ctrl+C berhenti ≤ 1 s. — OS: — hasil:
- [ ] MT-4.3 Resize jendela saat `htop` → htop menyesuaikan ukuran. — OS: — hasil:
- [ ] MT-4.4 `tput cols; tput lines` sama dengan `cols×rows` di status bar. — OS: — hasil:
- [ ] MT-4.5 Host baru → dialog fingerprint muncul; sama dengan
  `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` di server. — OS: — hasil:
- [ ] MT-4.6 Ketik `exit` → banner "Terputus"/"Sesi berakhir"; tekan R → terhubung lagi.
  — OS: — hasil:
- [ ] MT-4.7 Putuskan jaringan → aplikasi tetap responsif; status "Terputus" muncul ≤ 3 menit.
  — OS: — hasil:

### Penyimpangan & keputusan
- Alur secret tersimpan (§9.6.3 langkah 2, 5, 7) sudah dibuat di Fase 4 karena satu alur dengan
  login password; diuji di Fase 4 dan dilanjutkan di Fase 5.
- Lock `known_hosts` bernama publik `KNOWN_HOSTS_LOCK` (dipakai juga oleh `ssh_worker`).
- `TerminalTab.info_message` (sinyal) ditambahkan agar info "password tidak disimpan" tampil di status
  bar `MainWindow` (§9.6.3 langkah 5).
- Login private key (`_connect_with_key`) masih placeholder yang gagal dengan pesan; dikerjakan Fase 7.
- Log hanya mencatat nama kelas exception saat koneksi putus di loop I/O (tanpa isi pesan).

### Masalah yang diketahui
- MT-4.7 (koneksi putus mendadak) bergantung pada keepalive 30 s + perilaku TCP OS; hanya bisa
  diverifikasi manual.

## Fase 5 — Manajemen Sesi — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, offscreen), Python 3.12.3

### Yang dikerjakan
- 5.1 `ui/session_dialog.py`: form §9.5 (nama ≤ 64 & unik, host tanpa spasi dengan bracket IPv6
  dibuang, port 1–65535, username, metode Password/Private key, file key + Telusuri, passphrase,
  checkbox simpan, keterangan vault), tombol Simpan nonaktif selama invalid, label error field
  pertama, placeholder "(tersimpan — …)", aturan simpan/hapus secret §6.6/§9.5, ganti metode
  menghapus secret lama.
- 5.2 `ui/session_panel.py`: filter "Cari sesi…", daftar dua baris + tooltip, tombol +Baru/Edit/Hapus,
  Enter/klik dua kali → buka, F2 → edit, Delete (Backspace di macOS) → hapus dengan konfirmasi,
  menu konteks Buka/Edit/Duplikat/Hapus/Lupakan Host Key, label daftar kosong.
- 5.3 `MainWindow`: `QSplitter` (panel 240 px | `QStackedWidget` sambutan/tab), menu Sesi Baru
  (shortcut tabel), Panel Sesi (toggle), geometri/state/splitter disimpan ke `settings.json` saat
  jendela ditutup dan dipulihkan saat dibuka.
- 5.4 Alur secret di `TerminalTab` (§9.6.3 langkah 2, 5, 7) — dibuat di Fase 4, diuji lagi di sini.
- 5.5 Test: `test_session_dialog`, `test_session_panel`, tambahan `test_main_window`,
  `integration/test_secret_audit`.

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 585 lulus, 0 gagal |
| pytest (integration) | default `PYSSH_TEST_PASSWORD=secret`: 12 lulus, 1 dilewati (audit, lihat di bawah); dengan password unik: **13 lulus** |
| Coverage | session_dialog 99 %, session_panel 97 %, main_window 100 % |

### Kriteria penerimaan
- [x] AC-5.1 Quality Gate lulus.
- [x] AC-5.2 `test_secret_audit` lulus (N-01) dengan password server unik `secret-Z9q7-unique`:
  alur nyata prompt → login SSH → simpan lewat vault → tutup DB; password login dan master password
  tidak ditemukan sebagai bytes UTF-8 di file mana pun di folder data (`pyssh.db`, `known_hosts`,
  log level DEBUG termasuk logger paramiko).
- [x] AC-5.3 `test_terminal_tab::test_secret_saved_only_after_connected`,
  `test_wrong_stored_secret_is_replaced`, `test_failed_connection_does_not_save` dan
  `test_session_dialog::test_secret_saved_immediately_when_vault_open` lulus.

### Checklist manual (diisi user)
- [ ] MT-5.1 Tambah, edit, duplikat, hapus sesi lewat UI; restart aplikasi → data tetap. — OS: — hasil:
- [ ] MT-5.2 Sesi dengan "Simpan password" → restart → buka vault → koneksi tanpa prompt.
  — OS: — hasil:
- [ ] MT-5.3 Restart → **Lewati** vault → koneksi meminta password. — OS: — hasil:
- [ ] MT-5.4 Buka `pyssh.db` dengan `sqlite3` CLI / DB Browser for SQLite → kolom `ciphertext`
  berupa data biner, password tidak terbaca. — OS: — hasil:
- [ ] MT-5.5 Pencarian memfilter berdasarkan nama/host/user. — OS: — hasil:
- [ ] MT-5.6 Klik kanan sesi → Lupakan Host Key → koneksi berikutnya menampilkan dialog fingerprint
  lagi. — OS: — hasil:

### Penyimpangan & keputusan
- **Audit secret butuh password uji unik.** Dengan password default `secret`, pencarian byte selalu
  "menemukan" kata itu di skema database (tabel `secrets`), jadi test di-skip dengan alasan tertulis
  bila `PYSSH_TEST_PASSWORD` < 12 karakter. Untuk AC-5.2 password user `tester` di server uji diganti
  sementara menjadi `secret-Z9q7-unique` lalu dikembalikan. Server Docker (§10.3 Opsi A) bisa
  dijalankan dengan `-e USER_PASSWORD=secret-Z9q7-unique` dan `PYSSH_TEST_PASSWORD` yang sama.
- Field private key, tombol Telusuri, dan passphrase di `SessionDialog` sudah dibuat di fase ini
  (tugas 7.2) karena satu form; login dengan key tetap dikerjakan di Fase 7.
- Keterangan vault di bawah checkbox selalu tampil sesuai state (bukan hanya saat dicentang).
- Peringatan database rusak tetap ditampilkan oleh `app.main()` setelah jendela muncul (satu kali),
  bukan oleh `SessionPanel`.
- Saat sesi disimpan dengan "Simpan" dicentang dan field secret diisi, sesi disimpan dulu dengan
  `remember_secret = 0`; flag menjadi 1 hanya setelah secret benar-benar tersimpan.
- `MainWindow.closeEvent` sudah menyimpan geometri; penghentian semua sesi ditambahkan di Fase 6.

### Masalah yang diketahui
- Tidak ada.
