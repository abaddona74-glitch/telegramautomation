from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from telegramautomation.config import load_config  # noqa: E402
from telegramautomation.sheet_grid import SheetGridFormatter  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    cfg = load_config()
    formatter = SheetGridFormatter(cfg)
    formatter.apply_if_needed(force=True)

    print("Grid format applied successfully")


if __name__ == "__main__":
    main()
