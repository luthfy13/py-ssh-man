"""Entry point for ``python -m pyssh``."""

from __future__ import annotations

import sys

from pyssh.app import main

if __name__ == "__main__":
    sys.exit(main())
