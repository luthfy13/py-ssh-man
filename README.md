# PySSH

Aplikasi desktop SSH client lintas platform (Windows, Linux, macOS) yang terinspirasi MobaXterm,
khusus untuk sesi SSH interaktif. Ditulis dengan Python, PySide6 (Qt 6), paramiko, dan pyte.

- Daftar sesi tersimpan di database SQLite lokal (tambah, edit, duplikat, hapus, cari).
- Password/passphrase bisa disimpan **terenkripsi** (AES-256-GCM, kunci dari master password lewat
  scrypt).
- Banyak tab dengan koneksi independen, status per tab, reconnect.
- Login dengan password atau private key Ed25519/ECDSA/RSA (format OpenSSH atau PEM), termasuk
  passphrase.
- Verifikasi host key (Trust On First Use) dengan file `known_hosts` milik aplikasi.
- Terminal `xterm-256color`: 16/256/truecolor, atribut teks, scrollback, seleksi, copy/paste
  (termasuk bracketed paste), zoom font, alternate screen untuk vim/htop/less.

Spesifikasi lengkap: [`docs/SPEC.md`](docs/SPEC.md). Laporan per fase:
[`docs/PROGRESS.md`](docs/PROGRESS.md).

## Kebutuhan

- Python **3.11 atau lebih baru** (disarankan 3.12).
- Linux: pustaka sistem untuk Qt.
  - Debian/Ubuntu: `sudo apt install python3-venv libxcb-cursor0`
    (`python3.12-venv` bila memakai Python 3.12 dari deadsnakes).
  - Fedora: `sudo dnf install xcb-util-cursor`.
  - Lingkungan tanpa layar (container/CI) juga butuh `libegl1` dan minimal satu font monospace
    (mis. `fonts-dejavu-core`).

## Instalasi (dari source)

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"     # atau: pip install .   (tanpa alat pengembangan)
```

Linux / macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"     # atau: pip install .
```

## Menjalankan

```bash
python -m pyssh                         # atau perintah: pyssh
python -m pyssh --demo                  # tab demo warna + key inspector (tanpa jaringan)
python -m pyssh --connect user@host     # koneksi cepat; juga user@host:2222 dan user@[::1]:22
python -m pyssh --debug                 # log level DEBUG
python -m pyssh --version
```

Catatan Windows: perintah `pyssh` dipasang sebagai *gui-script* (tanpa jendela konsol), sehingga
keluaran `pyssh --version` kemungkinan tidak terlihat di terminal; gunakan
`python -m pyssh --version`.

### Folder data

| OS | Lokasi |
|---|---|
| Windows | `%APPDATA%\PySSH` |
| macOS | `~/Library/Application Support/PySSH` |
| Linux | `$XDG_DATA_HOME/pyssh` atau `~/.local/share/pyssh` |

Variabel `PYSSH_HOME` mengganti lokasi tersebut. Isinya: `pyssh.db` (sesi + secret terenkripsi),
`settings.json`, `known_hosts`, dan `logs/pyssh.log`. Di Linux/macOS folder dibuat dengan izin
`0700` dan file sensitif `0600`.

### Master password

- Dibuat saat pertama kali menyimpan password/passphrase (atau lewat **Berkas → Buat Master
  Password…**). Minimal 8 karakter.
- Master password **tidak disimpan** dan **tidak bisa dipulihkan**. Bila lupa, pilih
  "Lupa master password?" atau **Berkas → Reset Data Login…**: semua password/passphrase tersimpan
  dihapus, daftar sesi tetap ada.
- Saat aplikasi dibuka, vault bisa dibuka atau **dilewati**; bila dilewati, password diminta saat
  koneksi.

### Shortcut utama

| Aksi | Windows / Linux | macOS |
|---|---|---|
| Sesi baru | Ctrl+Shift+N | Cmd+N |
| Tutup tab | Ctrl+Shift+W | Cmd+W |
| Hubungkan ulang | Ctrl+Shift+R (atau R/Enter di tab terputus) | Cmd+R |
| Tab berikutnya / sebelumnya | Ctrl+Tab / Ctrl+Shift+Tab | sama, atau Cmd+Shift+] / [ |
| Perbesar / perkecil / normal | Ctrl+Shift+= / - / 0 | Cmd+= / - / 0 |
| Salin / tempel | Ctrl+Shift+C / V | Cmd+C / V |
| Scrollback | Shift+PageUp / PageDown | sama |

Kombinasi Ctrl lainnya (Ctrl+C, Ctrl+D, Ctrl+R, Ctrl+W, …) selalu dikirim ke server.

## Pengembangan

### Quality Gate

```bash
ruff check src tests
ruff format --check src tests
pytest -q -m "not integration" --cov=pyssh --cov-report=term-missing
pytest -q -m integration        # butuh server SSH uji; tanpa server semua test di-skip
```

Di Linux tanpa layar, test otomatis memakai `QT_QPA_PLATFORM=offscreen`.

### Server SSH uji

Variabel lingkungan (default dalam kurung): `PYSSH_TEST_HOST` (`127.0.0.1`), `PYSSH_TEST_PORT`
(`2222`), `PYSSH_TEST_USER` (`tester`), `PYSSH_TEST_PASSWORD` (`secret`), `PYSSH_TEST_KEY`
(`tests/keys/id_ed25519`), `PYSSH_TEST_KEY_PASS` (`tests/keys/id_ed25519_pass`),
`PYSSH_TEST_KEY_PASSPHRASE` (`testpass`).

Key uji:

```bash
mkdir -p tests/keys
ssh-keygen -t ed25519 -f tests/keys/id_ed25519 -N ""
ssh-keygen -t ed25519 -f tests/keys/id_ed25519_pass -N "testpass"
```

Docker (Linux/macOS; di Windows ganti `\` dengan `` ` `` dan `$PWD` dengan `${PWD}`):

```bash
docker run -d --name pyssh-test -p 2222:2222 \
  -e PUID=1000 -e PGID=1000 \
  -e USER_NAME=tester -e USER_PASSWORD=secret -e PASSWORD_ACCESS=true \
  -e PUBLIC_KEY_DIR=/pubkeys -v "$PWD/tests/keys:/pubkeys:ro" \
  lscr.io/linuxserver/openssh-server:latest
```

Tanpa Docker (container/VM Linux, sebagai root): pasang `openssh-server`, buat user `tester`, isi
`authorized_keys` dengan `tests/keys/*.pub`, lalu
`/usr/sbin/sshd -p 2222 -o PasswordAuthentication=yes -o PermitRootLogin=no` (langkah lengkap di
`docs/SPEC.md` §10.3, Opsi C).

`tests/integration/test_secret_audit.py` mencari password login sebagai bytes di semua file folder
data, sehingga butuh password uji yang **unik** (≥ 12 karakter, mis. `secret-Z9q7-unique`) di server
dan di `PYSSH_TEST_PASSWORD`; dengan password `secret` test ini di-skip.

### CI (belum aktif)

`docs/ci/github-actions-test.yml` menjalankan unit test di Ubuntu, Windows, dan macOS. GitHub hanya
menjalankan workflow di `.github/workflows/`; pindahkan file itu ke sana untuk mengaktifkannya.

### Alat bantu

- `python tools/make_ansi_demo.py` — membuat ulang `src/pyssh/resources/ansi_demo.txt`.
- `python tools/make_icon.py` — membuat ulang `src/pyssh/resources/icon.png`.
- `python tools/bench_emulator.py` — throughput emulator (MB/s).
- `PYSSH_DEBUG_PERF=1 python -m pyssh` — log lag event loop dan throughput setiap 5 detik.

## Batasan yang diketahui

- Seleksi hilang saat ada output baru.
- Baris yang ter-wrap disalin sebagai beberapa baris.
- Mengecilkan jumlah baris membuang baris teratas layar (tidak masuk scrollback).
- Tanpa mouse reporting ke aplikasi remote.
- Membuka private key ber-passphrase dan membuka vault bisa menahan tampilan sesaat (kursor tunggu).
- Metadata sesi (nama, host, username, path key) tidak dienkripsi.
- Menjalankan dua instance bersamaan tidak didukung resmi.
- Secret di memori tidak bisa dijamin terhapus (batasan Python).
- Key format PKCS#8 (`BEGIN PRIVATE KEY`) tidak didukung paramiko; ubah dengan
  `ssh-keygen -p -f <file>`. File `.ppk` PuTTY perlu diekspor ke format OpenSSH.
- Scrollback baru dari Pengaturan hanya berlaku untuk tab baru.
- Di luar cakupan versi ini: SFTP, X11 forwarding, port forwarding, jump host, SSH agent/Pageant,
  2FA interaktif, split pane, paket installer.

## Lisensi pustaka

PySide6 (LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only), paramiko (LGPL-2.1), pyte (LGPLv3),
cryptography (Apache-2.0 OR BSD-3-Clause) — sesuai metadata paket yang terpasang.
