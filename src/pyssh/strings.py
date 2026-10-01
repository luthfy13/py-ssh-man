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
