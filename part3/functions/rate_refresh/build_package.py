# Jingrui Feng (jf4446) - database systems project part 3 - function deployment package builder
"""Create a small Azure Functions package without duplicating pricing logic."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "python" / "etl" / "run_rate_refresh.py"
FUNCTION = Path(__file__).resolve().parent
BUILD = FUNCTION / "build"


def main() -> None:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()
    for name in ("function_app.py", "host.json", "requirements.txt"):
        shutil.copy2(FUNCTION / name, BUILD / name)
    shutil.copy2(SOURCE, BUILD / "rate_refresh_core.py")
    print(BUILD)


if __name__ == "__main__":
    main()
