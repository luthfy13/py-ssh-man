"""English user-visible text; same names and placeholders as ``strings.py`` (see ``i18n.py``)."""

from __future__ import annotations

# --- Application ---
VERSION_LINE = "{app} {version}"
UNHANDLED_ERROR_TITLE = "Error"
UNHANDLED_ERROR = "An unexpected error occurred ({name}). See the log file for details:\n{log_file}"

# --- Database ---
DB_CORRUPT_WARNING = (
    "The database file was damaged and has been moved to:\n{backup}\n\n"
    "A new, empty database has been created."
)
DB_NEWER_VERSION_TITLE = "Unsupported database"
DB_NEWER_VERSION = (
    "The database was created by a newer version of PySSH (schema version {found}, "
    "supported up to {supported}).\n\nFile: {path}"
)
WARNING_TITLE = "Warning"

# --- Session validation ---
ERR_NAME_REQUIRED = "Session name is required."
ERR_NAME_TOO_LONG = "Session name can be at most {max} characters."
ERR_NAME_DUPLICATE = 'Session name "{name}" is already in use.'
ERR_HOST_REQUIRED = "Host is required."
ERR_HOST_INVALID = "Host must not contain spaces or square brackets."
ERR_PORT_RANGE = "Port must be a number from 1 to 65535."
ERR_USERNAME_REQUIRED = "Username is required."
ERR_USERNAME_SPACES = "Username must not contain spaces."
ERR_AUTH_TYPE = "Invalid login method."
ERR_KEY_PATH_REQUIRED = "A private key file is required for the Private key method."
SESSION_COPY_SUFFIX = " (copy)"
SESSION_COPY_SUFFIX_N = " (copy {n})"

# --- Vault ---
VAULT_STATUS = "Vault: {state}"
VAULT_STATE_UNINITIALIZED = "not created"
VAULT_STATE_LOCKED = "locked"
VAULT_STATE_UNLOCKED = "unlocked"
VAULT_CREATE_TITLE = "Create Master Password"
VAULT_CREATE_INFO = (
    "The master password protects the passwords/passphrases you save. "
    "The master password itself is not stored anywhere."
)
VAULT_CREATE_WARNING = (
    "The master password cannot be recovered. If you forget it, all saved login data must be "
    "deleted."
)
VAULT_FIELD_PASSWORD = "Master password:"
VAULT_FIELD_CONFIRM = "Confirm:"
VAULT_FIELD_OLD = "Current master password:"
VAULT_FIELD_NEW = "New master password:"
VAULT_BUTTON_CREATE = "Create"
VAULT_BUTTON_UNLOCK = "Unlock"
VAULT_BUTTON_SKIP = "Skip"
VAULT_BUTTON_CANCEL = "Cancel"
VAULT_BUTTON_CHANGE = "Change"
VAULT_ERR_TOO_SHORT = "The master password must be at least {min} characters."
VAULT_ERR_MISMATCH = "The confirmation does not match the master password."
VAULT_UNLOCK_TITLE = "Unlock Vault"
VAULT_UNLOCK_INFO = "Enter the master password to use saved login data."
VAULT_ERR_WRONG = "Wrong master password."
VAULT_ERR_WRONG_OLD = "Wrong current master password."
VAULT_FORGOT_LINK = "Forgot master password?"
VAULT_CHANGE_TITLE = "Change Master Password"
VAULT_RESET_TITLE = "Reset Login Data"
VAULT_RESET_CONFIRM = (
    "All saved passwords/passphrases will be permanently deleted. The session list is kept. "
    "Continue?"
)
VAULT_RESET_BUTTON = "Delete Login Data"

# --- Main window menus ---
MENU_FILE = "&File"
MENU_SESSION = "&Session"
MENU_VIEW = "&View"
MENU_HELP = "&Help"
ACTION_NEW_SESSION = "New Session…"
ACTION_VAULT_CREATE = "Create Master Password…"
ACTION_VAULT_UNLOCK = "Unlock Vault…"
ACTION_VAULT_LOCK = "Lock Vault"
ACTION_VAULT_CHANGE = "Change Master Password…"
ACTION_VAULT_RESET = "Reset Login Data…"
ACTION_SETTINGS = "Settings…"
ACTION_QUIT = "Quit"

# --- Terminal widget ---
TERMINAL_COPY = "Copy"
TERMINAL_PASTE = "Paste"
TERMINAL_CLEAR_SCROLLBACK = "Clear Scrollback"
GRID_SIZE = "{cols}×{rows}"

# --- Demo ---
DEMO_TAB_TITLE = "Demo"
DEMO_INSPECTOR_HEADER = "Key inspector: press any key; non-printable bytes are shown as \\xNN."

# --- Menus: session and view ---
ACTION_RECONNECT = "Reconnect"
ACTION_CLOSE_TAB = "Close Tab"
ACTION_NEXT_TAB = "Next Tab"
ACTION_PREV_TAB = "Previous Tab"
ACTION_ZOOM_IN = "Zoom In"
ACTION_ZOOM_OUT = "Zoom Out"
ACTION_ZOOM_RESET = "Actual Size"
ACTION_TOGGLE_PANEL = "Session Panel"

# --- Connection errors (SPEC §7.10) ---
E_HOSTKEY_REJECTED = "Connection cancelled: the host key was not accepted."
E_HOSTKEY_CHANGED = (
    "WARNING: the host key of {host}:{port} has changed! This may be a man-in-the-middle attack, "
    "or the server was reinstalled."
)
E_AUTH = "Authentication failed for {username}@{host}."
E_CONNECT = (
    "Cannot connect to {host}:{port}. Make sure the SSH service is running and the port is correct."
)
E_DNS = 'Host "{host}" not found. Check the host name or DNS.'
E_TIMEOUT = "No response from {host}:{port} within {timeout} seconds."
E_BANNER = "The service at {host}:{port} did not respond as an SSH server."
E_SSH = "SSH protocol error: {detail}"
E_EOF = "The server closed the connection."
E_NETWORK = "Network error: {detail}"
E_UNKNOWN = "Unexpected error ({name}). See the log for details."

# --- Disconnect reasons ---
DISCONNECT_LOST = "Connection lost."
DISCONNECT_BY_USER = "Connection closed."
DISCONNECT_SESSION_ENDED = "Session ended (exit code {code})."

# --- Password / host key dialogs (SPEC §9.7) ---
PASSWORD_TITLE = "Password"
PASSPHRASE_TITLE = "Passphrase"
PASSWORD_PROMPT = "Password for {target}"
PASSPHRASE_PROMPT = "Passphrase for {path}"
PASSWORD_FIELD = "Password:"
PASSPHRASE_FIELD = "Passphrase:"
PASSWORD_REMEMBER = "Save password"
PASSPHRASE_REMEMBER = "Save passphrase"
PASSWORD_RETRY = "Wrong password, try again."
BUTTON_OK = "OK"
BUTTON_CANCEL = "Cancel"
HOSTKEY_TITLE = "Unknown Host Key"
HOSTKEY_UNKNOWN = "The server {host}:{port} is not known yet."
HOSTKEY_TYPE = "Key type: {key_type}"
HOSTKEY_FINGERPRINT = "Fingerprint:"
HOSTKEY_VERIFY = "Make sure this fingerprint matches the server's before continuing."
HOSTKEY_ACCEPT_SAVE = "Accept && Save"
HOSTKEY_ACCEPT_ONCE = "Accept Once"
HOSTKEY_CHANGED_TITLE = "Host Key Changed"
HOSTKEY_CHANGED_HINT_SESSION = (
    "If this change is expected, right-click the session → Forget Host Key, then reconnect."
)
HOSTKEY_CHANGED_HINT_ADHOC = (
    "If this change is expected, remove this host's entry from the file:\n{path}"
)

# --- Terminal tab (SPEC §9.6) ---
CONNECTING = "Connecting to {target} …"
STATE_IDLE = "Not connected"
STATE_CONNECTING = "Connecting…"
STATE_CONNECTED = "Connected"
STATE_DISCONNECTED = "Disconnected"
STATE_FAILED = "Failed"
STATUS_LINE = "{state} — {target}"
CANCELLED_BY_USER = "Cancelled by the user."
PRESS_R_TO_RECONNECT = "{reason} Press R to reconnect."
KEY_REJECTED = "The server rejected this private key."
BANNER_RECONNECT = "Reconnect"
BANNER_CLOSE = "Close Tab"
SECRET_NOT_SAVED_VAULT = "The password was not saved because the vault is not unlocked."

# --- Command line ---
ERR_CONNECT_ARG = "--connect must be in the form user@host[:port]"

# --- Session dialog (SPEC §9.5) ---
SESSION_NEW_TITLE = "New Session"
SESSION_EDIT_TITLE = "Edit Session"
FIELD_NAME = "Name:"
FIELD_HOST = "Host:"
FIELD_PORT = "Port:"
FIELD_USERNAME = "Username:"
FIELD_AUTH = "Login method:"
AUTH_PASSWORD = "Password"
AUTH_KEY = "Private key"
FIELD_PASSWORD = "Password:"
FIELD_KEY_PATH = "Private key file:"
FIELD_PASSPHRASE = "Passphrase:"
BROWSE = "Browse…"
BROWSE_TITLE = "Choose Private Key File"
BROWSE_FILTER = "All files (*)"
REMEMBER_SECRET = "Save password/passphrase"
SECRET_STORED_PLACEHOLDER = "(saved — leave empty to keep it)"
VAULT_HINT_CREATE = "You will be asked to create a master password."
VAULT_HINT_UNLOCK = "You will be asked to unlock the vault."
BUTTON_SAVE = "Save"
ERR_KEY_FILE_MISSING = "Private key file not found."
SESSION_SAVED_WITHOUT_SECRET = (
    "The session was saved without the password because the vault is not unlocked."
)

# --- Session panel (SPEC §9.4) ---
SEARCH_PLACEHOLDER = "Search sessions…"
BUTTON_NEW = "+ New"
BUTTON_EDIT = "Edit"
BUTTON_DELETE = "Delete"
PANEL_EMPTY = "No sessions yet. Click + New."
MENU_OPEN = "Open"
MENU_EDIT = "Edit…"
MENU_DUPLICATE = "Duplicate"
MENU_DELETE = "Delete…"
MENU_FORGET_HOST_KEY = "Forget Host Key"
DELETE_TITLE = "Delete Session"
DELETE_CONFIRM = 'Delete session "{name}"? Its saved password/passphrase is deleted too.'
FORGET_TITLE = "Forget Host Key"
FORGET_DONE = (
    "The host key for {target} has been removed. The next connection will ask for confirmation."
)
FORGET_NONE = "No host key is saved for {target}."

# --- Welcome page ---
WELCOME = "Double-click a session to open it, or press {shortcut} to create a new session."

# --- Closing (SPEC §9.7, §9.9) ---
CLOSE_TAB_TITLE = "Close Tab"
CLOSE_TAB_CONFIRM = "The session is still connected. Close the tab?"
QUIT_TITLE = "Quit"
QUIT_CONFIRM = "Active sessions: {n}. Quit {app}?"

# --- Private keys (SPEC §7.8) ---
KEY_NOT_FOUND = "Private key file not found: {path}"
KEY_PPK_UNSUPPORTED = (
    ".ppk (PuTTY) files are not supported. Convert to OpenSSH format: PuTTYgen → Load → "
    "Conversions → Export OpenSSH key, or on Linux/macOS: "
    "puttygen key.ppk -O private-openssh -o id_key"
)
KEY_PKCS8_UNSUPPORTED = (
    "PKCS#8 format is not supported. Convert it to OpenSSH format with: ssh-keygen -p -f {path}"
)
KEY_BAD_PASSPHRASE = "Wrong passphrase."
KEY_UNSUPPORTED_TYPE = "Unsupported private key type (only Ed25519, ECDSA, and RSA)."
KEY_INVALID = "Not a valid private key file: {path}"
PASSPHRASE_RETRY = "Wrong passphrase, try again."

# --- Settings dialog (SPEC §9.10) ---
SETTINGS_TITLE = "Settings"
SETTINGS_FONT = "Font:"
SETTINGS_FONT_AUTO = "Automatic (operating system default)"
SETTINGS_FONT_SIZE = "Font size:"
SETTINGS_SCROLLBACK = "Scrollback lines:"
SETTINGS_COPY_ON_SELECT = "Copy automatically on selection"
SETTINGS_BOLD_BRIGHT = "Bold text uses bright colors"
SETTINGS_CONFIRM_CLOSE = "Confirm when closing a tab/the application"
SETTINGS_KEEPALIVE = "Keepalive (seconds, 0 = off):"
SETTINGS_TIMEOUT = "Connection timeout (seconds):"
SETTINGS_OPTION_META = "Use Option as Meta"
SETTINGS_NOTE = (
    "Font and size apply immediately. Scrollback lines, keepalive, and timeout apply to new "
    "tabs/connections. Language applies after the application is restarted."
)

# --- Language (setting; applies after restart) ---
SETTINGS_LANGUAGE = "Language:"
LANGUAGE_NAME_ID = "Bahasa Indonesia"
LANGUAGE_NAME_EN = "English"
LANGUAGE_RESTART_TITLE = "Language"
LANGUAGE_RESTART = "The new language will be used after {app} is restarted."

# --- Help menu (SPEC §9.1) ---
ACTION_OPEN_DATA_FOLDER = "Open Data Folder"
ACTION_OPEN_LOG = "Open Log File"
ACTION_ABOUT = "About {app}"
ABOUT_TITLE = "About {app}"
ABOUT_TEXT = (
    "{app} {version}\n\n"
    "Cross-platform desktop SSH client.\n\n"
    "Python {python}\nQt {qt} (PySide6 {pyside})\n\n"
    "Libraries: PySide6 (LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only), "
    "paramiko (LGPL-2.1), pyte (LGPLv3), cryptography (Apache-2.0 OR BSD-3-Clause)."
)
