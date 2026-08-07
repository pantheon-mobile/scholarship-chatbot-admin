from dataclasses import dataclass
from pathlib import Path, PurePath

from fastapi import UploadFile


MAX_FILE_COUNT = 20
MAX_TOTAL_SIZE = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"}

OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

ALLOWED_CONTENT_TYPES = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "xls": {"application/vnd.ms-excel"},
    "ppt": {"application/vnd.ms-powerpoint"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "txt": {"text/plain"},
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
}


class FileUploadValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedUpload:
    upload: UploadFile
    file_name: str
    extension: str
    size_bytes: int
    content_type: str


def _actual_size(upload: UploadFile) -> int:
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    return size


def _safe_file_name(filename: str | None) -> str:
    if not filename or filename in {".", ".."} or "\x00" in filename:
        raise FileUploadValidationError("UNSAFE_FILE_NAME", "安全でないファイル名です。")
    if PurePath(filename).name != filename or "/" in filename or "\\" in filename or len(filename) > 500:
        raise FileUploadValidationError("UNSAFE_FILE_NAME", "安全でないファイル名です。")
    return filename


def _validate_content(upload: UploadFile, extension: str, content_type: str) -> None:
    allowed_types = ALLOWED_CONTENT_TYPES[extension]
    if content_type and content_type != "application/octet-stream" and content_type not in allowed_types:
        raise FileUploadValidationError("FILE_SIGNATURE_MISMATCH", "ファイルの形式と内容が一致していません。")

    upload.file.seek(0)
    header = upload.file.read(8)
    valid = False
    if extension == "pdf":
        valid = header.startswith(b"%PDF-")
    elif extension in {"doc", "xls", "ppt"}:
        valid = header.startswith(OLE_SIGNATURE)
    elif extension in {"docx", "xlsx", "pptx"}:
        valid = header.startswith(ZIP_SIGNATURES)
    else:
        upload.file.seek(0)
        content = upload.file.read()
        if b"\x00" not in content:
            for encoding in ("utf-8-sig", "cp932"):
                try:
                    content.decode(encoding)
                    valid = True
                    break
                except UnicodeDecodeError:
                    continue
    upload.file.seek(0)
    if not valid:
        raise FileUploadValidationError("FILE_SIGNATURE_MISMATCH", "ファイルの形式と内容が一致していません。")


def validate_uploads(files: list[UploadFile]) -> list[ValidatedUpload]:
    if not files:
        raise FileUploadValidationError("FILE_REQUIRED", "ファイルを選択してください。")
    if len(files) > MAX_FILE_COUNT:
        raise FileUploadValidationError("FILE_COUNT_EXCEEDED", "一度に選択できるファイルは20件までです。")

    validated: list[ValidatedUpload] = []
    names: set[str] = set()
    total_size = 0
    for upload in files:
        file_name = _safe_file_name(upload.filename)
        normalized_name = file_name.casefold()
        if normalized_name in names:
            raise FileUploadValidationError("DUPLICATE_FILE_NAME", "同じ名前のファイルが選択されています。")
        names.add(normalized_name)

        extension = Path(file_name).suffix.lower().lstrip(".")
        if extension not in ALLOWED_EXTENSIONS:
            raise FileUploadValidationError("UNSUPPORTED_FILE_TYPE", "対応していないファイル形式です。")
        size = _actual_size(upload)
        if size == 0:
            raise FileUploadValidationError("EMPTY_FILE", "0バイトのファイルは追加できません。")
        total_size += size
        if total_size > MAX_TOTAL_SIZE:
            raise FileUploadValidationError("TOTAL_SIZE_EXCEEDED", "ファイルの合計サイズは100MB以下にしてください。")
        content_type = (upload.content_type or "").lower().split(";", 1)[0].strip()
        _validate_content(upload, extension, content_type)
        validated.append(ValidatedUpload(upload, file_name, extension, size, content_type))
    return validated
