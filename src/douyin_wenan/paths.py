from __future__ import annotations

from pathlib import Path


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def iter_author_dirs(legacy_input_root: Path, *, author: str | None = None) -> list[Path]:
    items: list[Path] = []
    if not legacy_input_root.exists():
        return items

    normalized_author = (author or "").strip()
    for child in legacy_input_root.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            continue
        if normalized_author and child.name != normalized_author:
            continue
        tidy_dir = child / "整理版"
        if tidy_dir.exists():
            items.append(child)
    return sorted(items, key=lambda item: item.name)


def iter_standard_transcript_files(legacy_input_root: Path, *, author: str | None = None) -> list[Path]:
    files: list[Path] = []
    for author_dir in iter_author_dirs(legacy_input_root, author=author):
        tidy_dir = author_dir / "整理版"
        for txt_path in sorted(tidy_dir.glob("*.txt"), key=lambda item: item.name):
            if txt_path.name[:2].isdigit():
                files.append(txt_path)
    return files
