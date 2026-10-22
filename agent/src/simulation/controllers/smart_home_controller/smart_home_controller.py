from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[3]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from beacon_hub.main import app, main

__all__ = ["app", "main"]

if __name__ == "__main__":
    main()
