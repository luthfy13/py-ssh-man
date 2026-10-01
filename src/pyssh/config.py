"""Application constants and platform flags.

Data paths (``AppPaths``, ``get_paths()``) are added in Phase 1 (SPEC §7.1).
"""

from __future__ import annotations

import sys

APP_NAME = "PySSH"
APP_ORG = "PySSH"

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
