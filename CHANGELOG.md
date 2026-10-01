# Changelog

Semua perubahan penting pada PySSH dicatat di file ini.

## [0.1.0] — 2026-10-01

Rilis sumber pertama (dijalankan dengan Python; tanpa paket installer).

### Ditambahkan
- **Sesi tersimpan** di SQLite: tambah, edit, duplikat, hapus, cari (nama/host/user), "Lupakan
  Host Key".
- **Vault master password**: password/passphrase disimpan terenkripsi AES-256-GCM dengan kunci dari
  scrypt (N=2¹⁷); buat, buka (bisa dilewati), kunci, ganti, reset bila lupa.
- **Koneksi SSH** di thread worker: password (retry maks. 3×) dan private key Ed25519/ECDSA/RSA
  (OpenSSH & PEM) dengan passphrase; verifikasi host key TOFU dengan dialog fingerprint; pesan error
  yang jelas (DNS, timeout, port tertutup, host key berubah, dst.); `--connect user@host[:port]`.
- **Terminal xterm-256color** (pyte): 16/256/truecolor, atribut teks, karakter lebar, scrollback,
  seleksi (drag, double-click kata), copy/paste dengan bracketed paste, primary selection di Linux,
  zoom font, alternate screen untuk vim/htop/less/nano, resize PTY otomatis.
- **Keyboard lintas platform**: tabel shortcut per platform (macOS memakai Cmd), AltGr, Option
  sebagai Meta (macOS, opsional), key inspector di mode `--demo`.
- **Multi-tab**: judul unik, ikon status, banner reconnect (tombol atau R/Enter), konfirmasi tutup
  tab/aplikasi, penutupan aplikasi menghentikan semua sesi dan mengunci vault.
- **Pengaturan** (font, ukuran, scrollback, salin otomatis, warna tebal, konfirmasi, keepalive,
  timeout), posisi jendela tersimpan, menu Bantuan (folder data, file log, Tentang).
- Log berputar tanpa secret, `--debug`, `--version`, instrumentasi `PYSSH_DEBUG_PERF=1`.
- CI GitHub Actions: lint + unit test di Ubuntu, Windows, macOS (semua lulus).
- Alat bantu: `tools/make_ansi_demo.py`, `tools/make_icon.py`, `tools/bench_emulator.py`.
- 661 unit test dan 20 test integrasi (server SSH nyata), test arsitektur (batas impor Qt, teks UI
  dari `strings.py`, tanpa `print`, tanpa `sys.platform` di luar `config.py`).

### Diperbaiki (ditemukan selama pengembangan)
- Alasan terputus kadang salah ("Koneksi terputus.") karena OpenSSH mengirim EOF sebelum
  `exit-status`.
- Urutan CSI privat (mis. `ESC[?1;2m`) membuat pyte 0.8.2 melempar `TypeError` dan sebagian output
  hilang (terlihat saat menjalankan vim/htop).
- pyte 0.8.2 menamai latar SGR 105 `"bfightmagenta"`; kini dikenali sebagai bright magenta.
- Ctrl+C saat output membanjir butuh > 6 s; aliran data diatur ulang (window channel 128 KiB,
  backpressure 256 KiB) → ±1 s.

### Batasan yang diketahui
Lihat bagian "Batasan yang diketahui" di `README.md` (antara lain: key PKCS#8 dan `.ppk` perlu
dikonversi, tanpa mouse reporting, seleksi hilang saat ada output baru).
