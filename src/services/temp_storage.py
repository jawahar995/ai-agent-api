from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import uuid


@dataclass
class TempUpload:
    upload_id: str
    file_path: str
    size_bytes: int


def _base_dir() -> Path:
    base = os.getenv("TMP_STORAGE_DIR", "/tmp/ai-agent/uploads")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _upload_path(upload_id: str, suffix: str = ".txt") -> Path:
    return _base_dir() / f"{upload_id}{suffix}"


def save_temp_content(content: str, file_name: str | None = None) -> TempUpload:
    upload_id = str(uuid.uuid4())
    suffix = Path(file_name).suffix if file_name else ".txt"
    if not suffix:
        suffix = ".txt"

    path = _upload_path(upload_id=upload_id, suffix=suffix)
    path.write_text(content, encoding="utf-8")

    return TempUpload(
        upload_id=upload_id,
        file_path=str(path),
        size_bytes=path.stat().st_size,
    )


def resolve_upload_path(upload_id: str) -> Path | None:
    base = _base_dir()
    matches = list(base.glob(f"{upload_id}.*"))
    if not matches:
        return None
    return matches[0]


def purge_upload(upload_id: str) -> bool:
    path = resolve_upload_path(upload_id)
    if path is None:
        return False
    path.unlink(missing_ok=True)
    return True
