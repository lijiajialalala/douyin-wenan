from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parent
    src_dir = repo_root / "src"
    src_text = str(src_dir)
    if src_dir.exists() and src_text not in sys.path:
        sys.path.insert(0, src_text)


_ensure_src_on_path()
