from __future__ import annotations

import sys
from pathlib import Path


def ensure_src_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    src_text = str(src_dir)
    if src_dir.exists() and src_text not in sys.path:
        sys.path.insert(0, src_text)
