"""Atomic original-file storage and bounded recovery validation."""
import os
from pathlib import Path
import tempfile

from bson import ObjectId


def original_path(root: Path, document: dict) -> Path:
    file_id = str(document["_id"])
    filename = document.get("filename", "")
    if not ObjectId.is_valid(file_id) or not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ValueError("Invalid saved document reference.")
    root = root.resolve()
    directory = (root / file_id).resolve()
    candidate = (directory / filename).resolve()
    if directory.parent != root or directory.name != file_id or candidate.parent != directory:
        raise ValueError("Invalid saved document reference.")
    return candidate


def save_original(path: Path, content: bytes) -> None:
    """A crash may leave a temporary file, but never a partially written original."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".upload-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def recoverable_original(root: Path, document: dict) -> Path:
    path = original_path(root, document)
    expected = document.get("upload_size_bytes")
    if not path.is_file() or not isinstance(expected, int) or path.stat().st_size != expected:
        raise ValueError("The saved PDF is unavailable or incomplete. Select the original file again.")
    with path.open("rb") as stream:
        if b"%PDF-" not in stream.read(1024):
            raise ValueError("The saved PDF is unavailable or incomplete. Select the original file again.")
    return path
