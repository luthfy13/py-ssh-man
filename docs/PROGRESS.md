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

## Fase 6 — Multi-tab & Siklus Hidup — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, offscreen), Python 3.12.3; server uji `sshd` lokal

### Yang dikerjakan
- 6.1 Judul tab unik (`Nama`, `Nama (2)`, …), tooltip `user@host:port`, ikon titik status
  (`ui/icons.py`: kuning CONNECTING, hijau CONNECTED, merah DISCONNECTED/FAILED, abu-abu lainnya),
  ikon + teks status di kiri status bar.
- 6.2 Banner reconnect, R/Enter, shortcut Hubungkan Ulang (sudah dari Fase 4, diuji ulang).
- 6.3 Tutup tab lewat tombol ×, klik tengah (event filter pada tab bar), shortcut, dan tombol banner;
  konfirmasi "Sesi masih terhubung. Tutup tab?" hanya bila CONNECTED dan `confirm_on_close`.
- 6.4 Tab berikutnya/sebelumnya, fokus ke terminal saat pindah tab, status bar mengikuti tab aktif.
- 6.5 `closeEvent`: konfirmasi "Ada {n} sesi aktif. Keluar dari PySSH?" (n = tab CONNECTED) →
  simpan geometri → `close_session()` semua tab (`blockSignals` + `stop`) → `join` dengan total batas
  1,5 s → `vault.lock()` → `database.close()`.
- 6.6 Test: tambahan `test_main_window`, `integration/test_multi_tab`.

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 594 lulus, 0 gagal |
| pytest (integration) | 16 lulus, 1 dilewati (audit secret butuh password unik, lihat Fase 5) |
| Coverage | main_window 100 %, terminal_tab 95 %, icons 100 % |

### Kriteria penerimaan
- [x] AC-6.1 Quality Gate lulus.
- [x] AC-6.2 `test_five_parallel_sessions_get_their_own_output` (5 koneksi nyata, masing-masing hanya
  menerima hasil perintahnya sendiri) dan `test_twenty_connect_disconnect_cycles_leave_no_threads`
  (setelah 20 siklus tidak ada thread `ssh-*` di `threading.enumerate()`) lulus.
- [x] AC-6.3 `close_session()` pada tab dengan koneksi nyata: 0,29–0,46 ms (5 pengukuran);
  `test_closing_connected_tab_does_not_block` memastikan < 100 ms.

### Pengukuran
| Metrik | Target | Hasil | OS |
|---|---|---|---|
| `close_session()` tab terhubung | < 100 ms | 0,29–0,46 ms | Ubuntu 24.04 (container) |
| Tutup aplikasi dengan 5 sesi aktif | ≤ 2 s (MT-6.2) | 3,6 ms; thread `ssh-*` = 0 setelahnya | Ubuntu 24.04 (container) |

### Checklist manual (diisi user)
- [ ] MT-6.1 Buka 5 tab ke server berbeda/sama, jalankan `top` di semuanya; pindah tab lancar.
  — OS: — hasil:
- [ ] MT-6.2 Tutup aplikasi dengan 5 sesi aktif → proses keluar ≤ 2 s; tidak ada proses Python
  PySSH tersisa (Task Manager / `ps aux | grep pyssh` / Activity Monitor). — OS: — hasil:
- [ ] MT-6.3 Semua shortcut §8.3.2 berfungsi sesuai platform; Ctrl+C/Ctrl+D/Ctrl+W/Ctrl+R tetap
  terkirim ke server (cek di shell: Ctrl+R memunculkan reverse-search). — OS: — hasil:

### Penyimpangan & keputusan
- "Sesi aktif" pada konfirmasi keluar dihitung dari tab berstatus CONNECTED (sama dengan aturan
  konfirmasi tutup tab).
- `MainWindow.request_close_tab()` (dengan konfirmasi) dipakai untuk semua jalur UI; `close_tab()`
  menutup tanpa bertanya (dipakai `closeEvent` dan test).
- Ikon abu-abu untuk IDLE/CLOSED (tabel §9.6.1 hanya mendefinisikan 4 state).

### Masalah yang diketahui
- Tidak ada.

## Fase 7 — Autentikasi Private Key — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, offscreen), Python 3.12.3, paramiko 5.0.0,
cryptography 50.0.2

### Verifikasi perilaku paramiko (§7.8: "wajib dibuktikan dengan key nyata")
Key dibuat dengan `cryptography` lalu dimuat dengan `paramiko.PKey.from_path`:

| Kasus | Perilaku nyata paramiko 5.0.0 | Asumsi §7.8 |
|---|---|---|
| Parameter passphrase | bernama `password` dan **wajib `bytes`** (`str` → `TypeError: password must be bytes`) | `passphrase=` |
| Key terenkripsi tanpa password | `TypeError` ("…password was not provided" / "Password was not given…") | `PasswordRequiredException` |
| Password salah | `ValueError` (OpenSSH: pesan menyesatkan "no BEGIN/END delimiters"; PEM: "Incorrect password") | `PasswordRequiredException`/`SSHException` |
| Password untuk key tidak terenkripsi | `TypeError` ("Password was given but private key is not encrypted") | — |
| Key DSA | `UnknownKeyType` | sama |
| PKCS#8 (terenkripsi maupun tidak) | `SSHException` "not a valid … private key file", bahkan dengan password benar | — |
| File sampah | `ValueError` | sama |

`load_private_key()` mengikuti tabel di atas: passphrase dikodekan UTF-8; `TypeError` tanpa passphrase →
`PassphraseRequired`; passphrase untuk key tidak terenkripsi → dimuat ulang tanpa passphrase;
`ValueError`/`SSHException` → `KEY_BAD_PASSPHRASE` (bila passphrase diberikan) atau `KEY_INVALID`;
header PKCS#8 dideteksi lebih dulu → `KEY_INVALID` dengan petunjuk `ssh-keygen -p -f <file>`.

### Yang dikerjakan
- 7.1 `core/key_loader.py`: `KeyLoadError(code, message)`, `PassphraseRequired`,
  `load_private_key()` (ekspansi `~`, `KEY_NOT_FOUND`, `KEY_PPK_UNSUPPORTED` dengan instruksi
  PuTTYgen/puttygen, `KEY_BAD_PASSPHRASE`, `KEY_UNSUPPORTED_TYPE`, `KEY_INVALID`).
- 7.2 Field key di `SessionDialog` (sudah dari Fase 5): tombol Telusuri, filter "Semua file (*)",
  folder awal `~/.ssh`.
- 7.3 `TerminalTab`: key tanpa passphrase langsung dipakai; key terenkripsi → passphrase tersimpan
  (bila ada) lalu prompt "Passphrase" maks. 3× dengan pesan "Passphrase salah, coba lagi."; error
  key lain → FAILED dengan pesannya; server menolak key → "Server menolak private key ini."
  (tanpa retry); passphrase dari prompt disimpan hanya setelah tersambung; kursor tunggu selama
  memuat key (pengecualian A1).
- 7.4 Test: `test_key_loader` (14 kasus), tambahan `test_terminal_tab` (9 kasus key),
  `integration/test_ssh_key` (3 kasus).

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 617 lulus, 0 gagal |
| pytest (integration) | 19 lulus, 1 dilewati (audit secret butuh password unik, lihat Fase 5) |
| Coverage modul target | key_loader 91 % |

### Kriteria penerimaan
- [x] AC-7.1 Quality Gate lulus; coverage `core/key_loader` ≥ 90 %.
- [x] AC-7.2 Semua kasus `test_key_loader` §10.2 (Ed25519 OpenSSH dengan & tanpa passphrase, RSA PEM,
  ECDSA; tanpa passphrase → `PassphraseRequired`; salah → `KEY_BAD_PASSPHRASE`; PuTTY →
  `KEY_PPK_UNSUPPORTED`; tidak ada → `KEY_NOT_FOUND`; sampah → `KEY_INVALID`; path `~`) dan
  `test_ssh_key` (login Ed25519 tanpa & dengan passphrase dari `ssh-keygen`; key tak terdaftar →
  `auth_failed`) lulus.

Verifikasi tambahan tanpa layar (alur aplikasi nyata): sesi key `id_ed25519_pass` dengan "Simpan"
dicentang → prompt "Passphrase" sekali → tersambung → passphrase tersimpan terenkripsi; sesi dibuka
lagi → tersambung tanpa prompt.

### Checklist manual (diisi user)
- [ ] MT-7.1 Login dengan key Ed25519 tanpa passphrase. — OS: — hasil:
- [ ] MT-7.2 Login dengan key berpassphrase; centang simpan → restart, buka vault → koneksi berikutnya
  tanpa prompt. — OS: — hasil:
- [ ] MT-7.3 Passphrase salah → pesan jelas dan prompt ulang (maks. 3×). — OS: — hasil:
- [ ] MT-7.4 Pilih file `.ppk` → pesan instruksi konversi. — OS: — hasil:

### Penyimpangan & keputusan
- Pemanggilan `PKey.from_path` memakai `password=<bytes>` (nama & tipe sesuai paramiko 5.0.0),
  bukan `passphrase=<str>` seperti tertulis di §7.8.
- PKCS#8 (`BEGIN PRIVATE KEY` / `BEGIN ENCRYPTED PRIVATE KEY`) tidak didukung paramiko 5.0.0; dilaporkan
  sebagai `KEY_INVALID` dengan petunjuk konversi, bukan pesan "passphrase salah" yang menyesatkan.
- Passphrase tersimpan yang salah tidak dihitung sebagai salah satu dari 3 percobaan prompt.

### Masalah yang diketahui
- Key PKCS#8 harus dikonversi ke format OpenSSH (`ssh-keygen -p -f <file>`) sebelum dipakai.

## Fase 8 — Hardening & Penyempurnaan — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, offscreen), Python 3.12.3,
Intel Xeon 2,1 GHz, 4 core; server uji `sshd` lokal (loopback)

### Yang dikerjakan
- 8.1 Pengukuran N-02 s.d. N-07 lewat jalur aplikasi nyata (`MainWindow` → `TerminalTab` →
  `SSHWorker` → `TerminalWidget`) dengan skrip headless; lag diukur dengan timer 100 ms seperti
  `PYSSH_DEBUG_PERF=1` (instrumentasi bawaan juga diverifikasi menulis baris `perf max_lag_ms=…`).
- 8.2 Optimasi (berdasarkan profil, lihat di bawah): window channel SSH 128 KiB, ambang
  backpressure 256 KiB/64 KiB, chunk pump 2 KiB, repaint adaptif (50 ms saat antrean masih ada),
  cache gaya sel.
- 8.3 Alternate screen (F-17): `_ScrollbackScreen.set_mode/reset_mode` untuk private 47/1047/1049
  menyimpan `dict(buffer)` + salinan kursor, mengosongkan layar, memulihkan saat keluar; scrollback
  tidak bertambah selama alternate screen.
- 8.4 `SettingsDialog` (§9.10) + menu Berkas → Pengaturan… (`PreferencesRole`); font & ukuran
  langsung diterapkan ke semua tab terbuka.
- 8.5 Item SHOULD/COULD: daftar sesi 2 baris (Fase 5), judul OSC di tooltip tab, pemetaan hex 16
  warna pertama pyte → tema, primary selection Linux (salin saat seleksi, klik tengah menempel),
  `tools/make_icon.py` → `resources/icon.png` sebagai ikon jendela.
- 8.6 Audit: semua pemanggilan `log.*` ditinjau (tidak ada secret, master password, kunci,
  ciphertext, atau data terminal; hanya host/port/username/kode/kelas exception);
  `test_ui_text_comes_from_strings_module` (AST) memastikan tidak ada literal teks UI di luar
  `strings.py` (diuji juga dengan kontrol negatif).
- 8.7 `README.md`: instalasi per OS, menjalankan, folder data, master password, shortcut, test,
  server uji, batasan yang diketahui, lisensi pustaka (diverifikasi dari metadata paket).
- Tambahan: menu **Bantuan** §9.1 (Buka Folder Data, Buka File Log, Tentang PySSH dengan versi
  aplikasi/Python/Qt dan lisensi; `AboutRole`) yang belum ada di fase sebelumnya.

### Bug yang ditemukan & diperbaiki
- **pyte 0.8.2 + CSI privat**: `ESC[?…<final>` untuk 22 handler (mis. `ESC[?1;2m`) melempar
  `TypeError: … unexpected keyword argument 'private'`; sisa data dalam panggilan `feed` hilang dan
  exception merambat ke event Qt. Muncul nyata saat menjalankan vim/htop lewat SSH. Varian privat yang
  tidak didukung kini diabaikan, dan error parser lain dicatat (tanpa isi data) tanpa merambat.
  Regresi: `test_private_csi_variants_do_not_break_parsing` (22 kasus).

### Profil & keputusan optimasi (8.2)
- cProfile flood `seq 1 200000`: ~94 % waktu di `pyte.ByteStream.feed` (`draw`, `linefeed`), painting
  tidak signifikan → kecepatan pyte (~0,3 MB/s pada jalur penuh) adalah batas.
- N-04 gagal awalnya (6,38 s) karena antrean setelah Ctrl+C: `pending` widget (hingga 4 MiB) + window
  channel paramiko (default 2 MiB = `paramiko.common.DEFAULT_WINDOW_SIZE`). Diperkecil menjadi
  256 KiB + 128 KiB.
- Satu chunk 16 KiB butuh ~50 ms di pyte (melebihi anggaran 8 ms) → lag 388 ms saat 5 tab banjir
  output; chunk 2 KiB → 93 ms.
- Satu repaint penuh 101×39 ≈ 6,4–6,7 ms; pada 60 fps saat flood memakan ~40 % waktu → repaint
  adaptif 20 fps selama antrean ada.

### Pengukuran (agent, headless)
| Metrik | Target | Sebelum optimasi | Sesudah | Catatan |
|---|---|---|---|---|
| N-02 lag maks. saat `seq 1 200000` | < 150 ms | 69 ms | **18,2 ms** | lag saat 5 tab banjir bersamaan: 388 → 92,5 ms |
| N-03 `seq 1 200000` tampil | ≤ 10 s | 4,08 s | **4,78 s** | grid 101×38 |
| N-04 Ctrl+C saat flood | ≤ 2 s | **6,38 s ✗** | **1,07 s** | waktu dari `\x03` sampai `echo` berikutnya tampil |
| N-05 startup | ≤ 2 s | — | **26–39 ms** | `startup_ms` di log, offscreen (tanpa render nyata) |
| N-06 CPU idle 5 tab, 30 s | ≤ 2 % total | 1,44 % | **1,50 %** total (6,0 % dari 1 core) | 4 core; di mesin 2 core setara ±3 % — perlu diukur user |
| N-07 RSS 5 tab setelah `seq 1 10000` | ≤ 300 MB | 142,8 MB | **142,9 MB** | `/proc/self/status` VmRSS |
| Benchmark emulator | ≥ 0,3 MB/s (informatif) | 0,730 MB/s | **0,740 MB/s** | `tools/bench_emulator.py` |

Angka final di desktop nyata (render GPU/Windows/macOS, jaringan nyata) **diukur user** lewat MT-8.2.

Verifikasi tambahan tanpa layar (SSH nyata, paket `vim htop less nano` dipasang di server uji):
vim, htop, less, nano masuk & keluar alternate screen dan layar sebelumnya pulih; setelah jendela
di-resize saat htop berjalan, `stty size` = grid widget (45×24).

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus |
| pytest (unit) | 661 lulus, 0 gagal |
| pytest (integration) | 19 lulus, 1 dilewati (audit secret butuh password unik, lihat Fase 5) |
| Coverage | emulator 100 %, colors 100 %, widget 98 %, settings_dialog 100 %, total 98 % |

### Kriteria penerimaan
- [x] AC-8.1 Quality Gate lulus.
- [x] AC-8.2 Tabel N-02 s.d. N-07 di atas: semua memenuhi target di lingkungan headless; angka desktop
  menunggu MT-8.2.
- [x] AC-8.3 `test_alternate_screen_restores_main_screen`: setelah `\x1b[?1049h` + teks +
  `\x1b[?1049l` isi layar dan kursor kembali seperti sebelumnya.

### Checklist manual (diisi user)
- [ ] MT-8.1 Keluar dari vim/htop → layar kembali ke isi sebelumnya. — OS: — hasil:
- [ ] MT-8.2 `seq 1 200000` ≤ 10 s; Ctrl+C saat flood (`seq 1 100000000`) ≤ 2 s; pindah tab tetap
  responsif; catat CPU idle 5 tab (N-06, Task Manager/`top`/Activity Monitor) dan memori (N-07).
  Jalankan dengan `PYSSH_DEBUG_PERF=1` dan lihat baris `perf max_lag_ms=…` di log. — OS: — hasil:
- [ ] MT-8.3 Ubah font dan ukuran di Pengaturan → tab terbuka langsung berubah; tersimpan setelah
  restart. — OS: — hasil:

### Penyimpangan & keputusan
- **Parameter §8.4.3 diubah berdasarkan pengukuran** (tugas 8.2): chunk pump 16 KiB → 2 KiB, ambang
  backpressure 4 MiB/1 MiB → 256 KiB/64 KiB, repaint 50 ms selama antrean masih ada (16 ms saat
  idle); window channel SSH 128 KiB (`Transport.open_session(window_size=…)` + `get_pty` +
  `invoke_shell`, sama dengan langkah `SSHClient.invoke_shell`).
- `SettingsDialog`: pilihan "Otomatis" berupa checkbox di samping `QFontComboBox` (QFontComboBox tidak
  menyediakan item tambahan).
- Pemetaan 16 warna berdasarkan nilai hex: indeks 256-color lain atau truecolor dengan hex yang sama
  persis (mis. 196 = `ff0000` = indeks 9) ikut memakai warna tema.
- Varian privat CSI yang tidak dikenali pyte diabaikan (tidak ada respons untuk mis. `ESC[?6n`).

### Masalah yang diketahui
- Primary selection hanya bisa diuji dengan clipboard tiruan di lingkungan offscreen
  (`supportsSelection()` = False); verifikasi nyata di Linux X11/Wayland lewat MT-9.2/9.3.

## Fase 9 — Uji Lintas Platform & Rilis Sumber — 2026-10-01

**Status:** MENUNGGU VERIFIKASI MANUAL (Windows/macOS/Linux desktop oleh user)
**OS pengembangan:** Ubuntu 24.04.4 LTS (container, offscreen), Python 3.12.3

### Yang dikerjakan
- 9.1 Instalasi bersih di Linux: venv baru → `pip install .` (bukan editable) sukses;
  `pyssh --version` dan `python -m pyssh --version` mencetak `PySSH 0.1.0`; `ansi_demo.txt` dan
  `icon.png` ikut terpasang dan terbaca dari paket terpasang. Langkah instalasi Windows/macOS ada di
  `README.md`.
- 9.2 Quality Gate Linux lulus (di bawah). Unit test Windows/macOS → MT-9.0 (user).
- 9.3 Persiapan lintas platform: test `test_settings_dialog` tidak lagi bergantung pada font
  "DejaVu Sans Mono" (memakai font monospace yang tersedia di mesin). Belum ada laporan masalah
  platform dari user.
- 9.4 (COULD) Workflow GitHub Actions (unit test di Ubuntu/Windows/macOS) dibuat sebagai
  `docs/ci/github-actions-test.yml` — **tidak aktif**, karena workflow hanya boleh diaktifkan
  dengan izin (§10.5). Untuk mengaktifkan: pindahkan ke `.github/workflows/test.yml`.
- 9.5 `CHANGELOG.md` dilengkapi untuk 0.1.0; versi `0.1.0` di `pyproject.toml` dan
  `pyssh.__version__`. **Tag `v0.1.0` belum dibuat** (menunggu izin eksplisit).

### Quality Gate
| Cek | Hasil |
|---|---|
| ruff check | 0 error |
| ruff format --check | lulus (73 file) |
| pytest (unit) | 661 lulus, 0 gagal |
| pytest (integration) | password default `secret`: 19 lulus, 1 dilewati (audit); password unik `secret-Z9q7-unique`: **20 lulus** |
| Coverage total | 98 % |

### Kriteria penerimaan
- [x] AC-9.1 Unit test lulus 100 % di Linux (agent). Hasil Windows/macOS dari MT-9.0: *menunggu
  user*.
- [x] AC-9.2 Instalasi bersih (`pip install .`) sukses di Linux; `pyssh --version` mencetak versi.

### Checklist manual (diisi user; catat OS, versi OS, versi Python, sesi grafis)
- [ ] MT-9.0 **Windows** (dan macOS bila ada): di venv bersih jalankan `pip install -e ".[dev]"` lalu
  `pytest -q -m "not integration"` → semua lulus; lalu `pip install .` dan
  `python -m pyssh --version` (lihat catatan gui-script di bawah). — OS: — hasil:
- [ ] MT-9.1 **Windows 10/11**: ulangi MT-3.4, MT-4.1, MT-5.2, MT-6.2, MT-7.2. — OS: — hasil:
- [ ] MT-9.2 **Linux X11**: ulangi daftar MT-9.1; cek juga primary selection (seleksi lalu klik
  tengah). — OS: — hasil:
- [ ] MT-9.3 **Linux Wayland**: aplikasi tampil, keyboard dan clipboard berfungsi (MT-3.4, MT-3.7,
  MT-4.1). — OS: — hasil:
- [ ] MT-9.4 **macOS** (bila perangkat tersedia): MT-3.4 (Ctrl ke terminal, Cmd untuk aksi
  aplikasi), MT-3.7 (Cmd+C/Cmd+V), MT-4.1, MT-5.2; menu "Pengaturan…"/"Keluar"/"Tentang" berada di
  menu aplikasi. — OS: — hasil:

### Penyimpangan & keputusan
- **Windows dan gui-script**: `[project.gui-scripts]` (§3.1) membuat perintah `pyssh` di Windows
  berjalan tanpa konsol, sehingga keluaran `pyssh --version` kemungkinan tidak tampil. README
  menyarankan `python -m pyssh --version`. Belum diverifikasi di Windows (agent bekerja di Linux).
- Workflow CI disimpan di luar `.github/workflows/` agar tidak berjalan tanpa izin.

### Masalah yang diketahui
- Semua hal khusus Windows/macOS (font, keyboard AltGr/Option/Cmd, menu aplikasi macOS, izin file,
  Wayland) hanya diuji lewat parameter injeksi di Linux; perilaku nyata menunggu MT-9.x.
