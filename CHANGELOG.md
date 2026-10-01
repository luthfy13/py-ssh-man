# Changelog

Semua perubahan penting pada PySSH dicatat di file ini.

## [Belum dirilis]

### Ditambahkan
- Fase 0: kerangka proyek (`pyproject.toml`, struktur paket `src/pyssh`, `python -m pyssh`
  menampilkan jendela kosong "PySSH"), konfigurasi test (`pytest`, `pytest-qt`), dan
  dokumen `docs/SPEC.md` (v2.1) serta `docs/PROGRESS.md`.
- Fase 1: lokasi folder data per OS, database SQLite (skema v1, penanganan file rusak dan versi
  lebih baru), penyimpanan sesi, pengaturan `settings.json`, log berputar, `--version`.
- Fase 2: vault master password (scrypt + AES-256-GCM), penyimpanan secret terenkripsi, dialog
  buat/buka/ganti/reset master password, status vault di menu dan status bar.
- Fase 3: emulator terminal (pyte + scrollback), widget terminal (render, keyboard lintas
  platform, seleksi, clipboard, bracketed paste, zoom, backpressure), tabel shortcut per platform,
  mode `--demo` dengan key inspector, benchmark emulator.
- Fase 4: koneksi SSH dengan password di thread worker, verifikasi host key (TOFU), pemetaan
  error, tab terminal dengan state, banner reconnect, `--connect user@host[:port]`.
- Fase 5: panel sesi (cari, buat, edit, duplikat, hapus, lupakan host key), dialog sesi dengan
  penyimpanan password/passphrase terenkripsi, halaman sambutan, posisi jendela tersimpan.
- Fase 6: banyak tab dengan judul unik dan ikon status, konfirmasi tutup tab/aplikasi, klik tengah
  menutup tab, penutupan aplikasi menghentikan semua sesi dan mengunci vault.
- Fase 7: login dengan private key Ed25519/ECDSA/RSA (OpenSSH & PEM) dan passphrase (bisa
  disimpan terenkripsi); file `.ppk` dan PKCS#8 dideteksi dengan petunjuk konversi.

### Diperbaiki
- Alasan terputus kadang salah ("Koneksi terputus.") karena OpenSSH mengirim EOF sebelum
  `exit-status`.
