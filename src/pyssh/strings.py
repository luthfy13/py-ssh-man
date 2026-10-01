"""All user-visible text (Bahasa Indonesia), see SPEC §9.11.

Placeholders use named ``str.format`` fields.
"""

from __future__ import annotations

# --- Application ---
VERSION_LINE = "{app} {version}"
UNHANDLED_ERROR_TITLE = "Kesalahan"
UNHANDLED_ERROR = "Terjadi kesalahan tak terduga ({name}). Lihat file log untuk detail:\n{log_file}"

# --- Database ---
DB_CORRUPT_WARNING = (
    "File database rusak dan telah dipindahkan ke:\n{backup}\n\n"
    "Database baru yang kosong telah dibuat."
)
DB_NEWER_VERSION_TITLE = "Database tidak didukung"
DB_NEWER_VERSION = (
    "Database dibuat oleh versi PySSH yang lebih baru (versi skema {found}, "
    "didukung hingga {supported}).\n\nFile: {path}"
)
WARNING_TITLE = "Peringatan"

# --- Session validation ---
ERR_NAME_REQUIRED = "Nama sesi wajib diisi."
ERR_NAME_TOO_LONG = "Nama sesi maksimal {max} karakter."
ERR_NAME_DUPLICATE = 'Nama sesi "{name}" sudah dipakai.'
ERR_HOST_REQUIRED = "Host wajib diisi."
ERR_HOST_INVALID = "Host tidak boleh mengandung spasi atau tanda kurung siku."
ERR_PORT_RANGE = "Port harus berupa angka 1-65535."
ERR_USERNAME_REQUIRED = "Username wajib diisi."
ERR_USERNAME_SPACES = "Username tidak boleh mengandung spasi."
ERR_AUTH_TYPE = "Metode login tidak valid."
ERR_KEY_PATH_REQUIRED = "File private key wajib diisi untuk metode Private key."
SESSION_COPY_SUFFIX = " (salinan)"
SESSION_COPY_SUFFIX_N = " (salinan {n})"

# --- Vault ---
VAULT_STATUS = "Vault: {state}"
VAULT_STATE_UNINITIALIZED = "belum dibuat"
VAULT_STATE_LOCKED = "terkunci"
VAULT_STATE_UNLOCKED = "terbuka"
VAULT_CREATE_TITLE = "Buat Master Password"
VAULT_CREATE_INFO = (
    "Master password melindungi password/passphrase yang Anda simpan. "
    "Master password tidak disimpan di mana pun."
)
VAULT_CREATE_WARNING = (
    "Master password tidak bisa dipulihkan. Bila lupa, semua data login tersimpan harus dihapus."
)
VAULT_FIELD_PASSWORD = "Master password:"
VAULT_FIELD_CONFIRM = "Konfirmasi:"
VAULT_FIELD_OLD = "Master password lama:"
VAULT_FIELD_NEW = "Master password baru:"
VAULT_BUTTON_CREATE = "Buat"
VAULT_BUTTON_UNLOCK = "Buka"
VAULT_BUTTON_SKIP = "Lewati"
VAULT_BUTTON_CANCEL = "Batal"
VAULT_BUTTON_CHANGE = "Ganti"
VAULT_ERR_TOO_SHORT = "Master password minimal {min} karakter."
VAULT_ERR_MISMATCH = "Konfirmasi tidak sama dengan master password."
VAULT_UNLOCK_TITLE = "Buka Vault"
VAULT_UNLOCK_INFO = "Masukkan master password untuk memakai data login tersimpan."
VAULT_ERR_WRONG = "Master password salah."
VAULT_ERR_WRONG_OLD = "Master password lama salah."
VAULT_FORGOT_LINK = "Lupa master password?"
VAULT_CHANGE_TITLE = "Ganti Master Password"
VAULT_RESET_TITLE = "Reset Data Login"
VAULT_RESET_CONFIRM = (
    "Semua password/passphrase tersimpan akan dihapus permanen. Daftar sesi tetap ada. Lanjutkan?"
)
VAULT_RESET_BUTTON = "Hapus Data Login"

# --- Main window menus ---
MENU_FILE = "&Berkas"
MENU_SESSION = "&Sesi"
MENU_VIEW = "&Tampilan"
MENU_HELP = "Ba&ntuan"
ACTION_NEW_SESSION = "Sesi Baru…"
ACTION_VAULT_CREATE = "Buat Master Password…"
ACTION_VAULT_UNLOCK = "Buka Vault…"
ACTION_VAULT_LOCK = "Kunci Vault"
ACTION_VAULT_CHANGE = "Ganti Master Password…"
ACTION_VAULT_RESET = "Reset Data Login…"
ACTION_SETTINGS = "Pengaturan…"
ACTION_QUIT = "Keluar"

# --- Terminal widget ---
TERMINAL_COPY = "Salin"
TERMINAL_PASTE = "Tempel"
TERMINAL_CLEAR_SCROLLBACK = "Bersihkan Scrollback"
GRID_SIZE = "{cols}×{rows}"

# --- Demo ---
DEMO_TAB_TITLE = "Demo"
DEMO_INSPECTOR_HEADER = (
    "Key inspector: tekan tombol apa saja; byte non-printable ditampilkan sebagai \\xNN."
)

# --- Menus: session and view ---
ACTION_RECONNECT = "Hubungkan Ulang"
ACTION_CLOSE_TAB = "Tutup Tab"
ACTION_NEXT_TAB = "Tab Berikutnya"
ACTION_PREV_TAB = "Tab Sebelumnya"
ACTION_ZOOM_IN = "Perbesar"
ACTION_ZOOM_OUT = "Perkecil"
ACTION_ZOOM_RESET = "Ukuran Normal"
ACTION_TOGGLE_PANEL = "Panel Sesi"

# --- Connection errors (SPEC §7.10) ---
E_HOSTKEY_REJECTED = "Koneksi dibatalkan: host key tidak diterima."
E_HOSTKEY_CHANGED = (
    "PERINGATAN: host key {host}:{port} berubah! Kemungkinan serangan man-in-the-middle, "
    "atau server diinstal ulang."
)
E_AUTH = "Autentikasi gagal untuk {username}@{host}."
E_CONNECT = "Tidak dapat terhubung ke {host}:{port}. Pastikan layanan SSH berjalan dan port benar."
E_DNS = 'Host "{host}" tidak ditemukan. Periksa nama host atau DNS.'
E_TIMEOUT = "Tidak ada respons dari {host}:{port} dalam {timeout} detik."
E_BANNER = "Layanan di {host}:{port} tidak merespons sebagai server SSH."
E_SSH = "Kesalahan protokol SSH: {detail}"
E_EOF = "Koneksi diputus oleh server."
E_NETWORK = "Kesalahan jaringan: {detail}"
E_UNKNOWN = "Kesalahan tak terduga ({name}). Lihat log untuk detail."

# --- Disconnect reasons ---
DISCONNECT_LOST = "Koneksi terputus."
DISCONNECT_BY_USER = "Koneksi ditutup."
DISCONNECT_SESSION_ENDED = "Sesi berakhir (kode keluar {code})."

# --- Password / host key dialogs (SPEC §9.7) ---
PASSWORD_TITLE = "Password"
PASSPHRASE_TITLE = "Passphrase"
PASSWORD_PROMPT = "Password untuk {target}"
PASSPHRASE_PROMPT = "Passphrase untuk {path}"
PASSWORD_FIELD = "Password:"
PASSPHRASE_FIELD = "Passphrase:"
PASSWORD_REMEMBER = "Simpan password"
PASSPHRASE_REMEMBER = "Simpan passphrase"
PASSWORD_RETRY = "Password salah, coba lagi."
BUTTON_OK = "OK"
BUTTON_CANCEL = "Batal"
HOSTKEY_TITLE = "Host Key Belum Dikenal"
HOSTKEY_UNKNOWN = "Server {host}:{port} belum dikenal."
HOSTKEY_TYPE = "Jenis key: {key_type}"
HOSTKEY_FINGERPRINT = "Fingerprint:"
HOSTKEY_VERIFY = "Pastikan fingerprint ini sesuai dengan milik server sebelum melanjutkan."
HOSTKEY_ACCEPT_SAVE = "Terima && Simpan"
HOSTKEY_ACCEPT_ONCE = "Terima Sekali Ini"
HOSTKEY_CHANGED_TITLE = "Host Key Berubah"
HOSTKEY_CHANGED_HINT_SESSION = (
    "Bila perubahan ini memang diharapkan, klik kanan sesi → Lupakan Host Key, "
    "lalu hubungkan ulang."
)
HOSTKEY_CHANGED_HINT_ADHOC = (
    "Bila perubahan ini memang diharapkan, hapus entri host ini dari file:\n{path}"
)

# --- Terminal tab (SPEC §9.6) ---
CONNECTING = "Menghubungkan ke {target} …"
STATE_IDLE = "Belum terhubung"
STATE_CONNECTING = "Menghubungkan…"
STATE_CONNECTED = "Terhubung"
STATE_DISCONNECTED = "Terputus"
STATE_FAILED = "Gagal"
STATUS_LINE = "{state} — {target}"
CANCELLED_BY_USER = "Dibatalkan oleh pengguna."
PRESS_R_TO_RECONNECT = "{reason} Tekan R untuk menghubungkan ulang."
KEY_REJECTED = "Server menolak private key ini."
BANNER_RECONNECT = "Hubungkan Ulang"
BANNER_CLOSE = "Tutup Tab"
SECRET_NOT_SAVED_VAULT = "Password tidak disimpan karena vault tidak dibuka."

# --- Command line ---
ERR_CONNECT_ARG = "format --connect harus user@host[:port]"

# --- Session dialog (SPEC §9.5) ---
SESSION_NEW_TITLE = "Sesi Baru"
SESSION_EDIT_TITLE = "Edit Sesi"
FIELD_NAME = "Nama:"
FIELD_HOST = "Host:"
FIELD_PORT = "Port:"
FIELD_USERNAME = "Username:"
FIELD_AUTH = "Metode login:"
AUTH_PASSWORD = "Password"
AUTH_KEY = "Private key"
FIELD_PASSWORD = "Password:"
FIELD_KEY_PATH = "File private key:"
FIELD_PASSPHRASE = "Passphrase:"
BROWSE = "Telusuri…"
BROWSE_TITLE = "Pilih File Private Key"
BROWSE_FILTER = "Semua file (*)"
REMEMBER_SECRET = "Simpan password/passphrase"
SECRET_STORED_PLACEHOLDER = "(tersimpan — kosongkan untuk tidak mengubah)"
VAULT_HINT_CREATE = "Anda akan diminta membuat master password."
VAULT_HINT_UNLOCK = "Anda akan diminta membuka vault."
BUTTON_SAVE = "Simpan"
ERR_KEY_FILE_MISSING = "File private key tidak ditemukan."
SESSION_SAVED_WITHOUT_SECRET = "Sesi disimpan tanpa password karena vault tidak dibuka."

# --- Session panel (SPEC §9.4) ---
SEARCH_PLACEHOLDER = "Cari sesi…"
BUTTON_NEW = "+ Baru"
BUTTON_EDIT = "Edit"
BUTTON_DELETE = "Hapus"
PANEL_EMPTY = "Belum ada sesi. Klik + Baru."
MENU_OPEN = "Buka"
MENU_EDIT = "Edit…"
MENU_DUPLICATE = "Duplikat"
MENU_DELETE = "Hapus…"
MENU_FORGET_HOST_KEY = "Lupakan Host Key"
DELETE_TITLE = "Hapus Sesi"
DELETE_CONFIRM = 'Hapus sesi "{name}"? Password/passphrase tersimpannya ikut dihapus.'
FORGET_TITLE = "Lupakan Host Key"
FORGET_DONE = "Host key untuk {target} telah dihapus. Koneksi berikutnya akan meminta konfirmasi."
FORGET_NONE = "Tidak ada host key tersimpan untuk {target}."

# --- Welcome page ---
WELCOME = "Klik dua kali sebuah sesi untuk membuka, atau tekan {shortcut} untuk membuat sesi baru."

# --- Closing (SPEC §9.7, §9.9) ---
CLOSE_TAB_TITLE = "Tutup Tab"
CLOSE_TAB_CONFIRM = "Sesi masih terhubung. Tutup tab?"
QUIT_TITLE = "Keluar"
QUIT_CONFIRM = "Ada {n} sesi aktif. Keluar dari {app}?"
