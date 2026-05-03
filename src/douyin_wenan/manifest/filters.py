from __future__ import annotations


def select_download_pending(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: _status(row, "download_status") == "pending" and _has_text(row, "video_link"),
        limit=limit,
        author=author,
    )


def select_download_retryable(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
    max_failure_count: int = 2,
    include_nonretryable: bool = False,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: (
            _status(row, "download_status") == "failed"
            and _has_text(row, "video_link")
            and _is_retryable_failure(
                row,
                class_field="download_failure_class",
                count_field="download_failure_count",
                max_failure_count=max_failure_count,
                include_nonretryable=include_nonretryable,
            )
        ),
        limit=limit,
        author=author,
    )


def select_asr_pending(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: _status(row, "download_status") == "ok" and _status(row, "asr_status") == "pending",
        limit=limit,
        author=author,
    )


def select_asr_retryable(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
    max_failure_count: int = 2,
    include_nonretryable: bool = False,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: (
            _status(row, "download_status") == "ok"
            and _status(row, "asr_status") == "failed"
            and _is_retryable_failure(
                row,
                class_field="asr_failure_class",
                count_field="asr_failure_count",
                max_failure_count=max_failure_count,
                include_nonretryable=include_nonretryable,
            )
        ),
        limit=limit,
        author=author,
    )


def select_asr_completed(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: _status(row, "asr_status") == "ok" and _has_text(row, "asr_text_path"),
        limit=limit,
        author=author,
    )


def select_txt_sync_pending(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: (
            _status(row, "asr_status") == "ok"
            and _status(row, "txt_sync_status") == "pending"
            and _has_text(row, "asr_text_path")
        ),
        limit=limit,
        author=author,
    )


def select_txt_sync_rebuildable(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: _status(row, "asr_status") == "ok" and _has_text(row, "asr_text_path"),
        limit=limit,
        author=author,
    )


def select_dedup_pending(
    rows: list[dict[str, str]],
    *,
    limit: int = 0,
    author: str | None = None,
) -> list[dict[str, str]]:
    return _select_rows(
        rows,
        predicate=lambda row: (
            _status(row, "txt_sync_status") == "ok"
            and _status(row, "dedup_status") == "unknown"
            and _has_text(row, "txt_path")
        ),
        limit=limit,
        author=author,
    )


def _select_rows(
    rows: list[dict[str, str]],
    *,
    predicate,
    limit: int,
    author: str | None,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    normalized_author = (author or "").strip()

    for row in rows:
        if normalized_author and (row.get("author", "") or "").strip() != normalized_author:
            continue
        if not predicate(row):
            continue
        selected.append(row)
        if limit > 0 and len(selected) >= limit:
            break
    return selected


def _status(row: dict[str, str], field: str) -> str:
    return (row.get(field, "") or "").strip()


def _has_text(row: dict[str, str], field: str) -> bool:
    return bool((row.get(field, "") or "").strip())


def _is_retryable_failure(
    row: dict[str, str],
    *,
    class_field: str,
    count_field: str,
    max_failure_count: int,
    include_nonretryable: bool,
) -> bool:
    if include_nonretryable:
        return True

    failure_class = _status(row, class_field)
    if failure_class not in {"", "retryable"}:
        return False

    failure_count_text = _status(row, count_field)
    if not failure_count_text:
        return True
    try:
        failure_count = int(failure_count_text)
    except ValueError:
        return False
    return failure_count < max(1, max_failure_count)
