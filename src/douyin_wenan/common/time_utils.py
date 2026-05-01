"""Time helpers will be added in Phase 1 implementation."""
from __future__ import annotations

from datetime import datetime


def current_timestamp_text() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
