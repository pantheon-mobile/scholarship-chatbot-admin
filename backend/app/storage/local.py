from pathlib import Path
import os
import shutil
import uuid


class LocalStorage:
    def __init__(self, upload_dir: str | Path | None = None) -> None:
        configured = Path(upload_dir or os.getenv("UPLOAD_DIR", "/app/storage/uploads"))
        self.upload_dir = configured.resolve()
        self.temporary_dir = self.upload_dir / ".tmp"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.temporary_dir.mkdir(parents=True, exist_ok=True)

    def create_storage_key(self, extension: str) -> str:
        normalized = extension.lower().lstrip(".")
        return f"{uuid.uuid4().hex}.{normalized}"

    def _final_path(self, storage_key: str) -> Path:
        candidate = (self.upload_dir / storage_key).resolve()
        if candidate.parent != self.upload_dir:
            raise ValueError("invalid_storage_key")
        return candidate

    def save_temporary(self, source) -> Path:
        temporary_path = self.temporary_dir / f"{uuid.uuid4().hex}.upload"
        source.seek(0)
        with temporary_path.open("xb") as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        return temporary_path

    def finalize(self, temporary_path: Path, storage_key: str) -> None:
        final_path = self._final_path(storage_key)
        if final_path.exists():
            raise FileExistsError(storage_key)
        temporary_path.replace(final_path)

    def delete_temporary(self, temporary_path: Path) -> None:
        temporary_path.unlink(missing_ok=True)

    def delete(self, storage_key: str) -> None:
        self._final_path(storage_key).unlink(missing_ok=True)

    def exists(self, storage_key: str) -> bool:
        return self._final_path(storage_key).is_file()

    def read(self, storage_key: str) -> bytes:
        return self._final_path(storage_key).read_bytes()
