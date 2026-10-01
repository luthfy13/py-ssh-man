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
