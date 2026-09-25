"""Validate all ZIP members before an XLSX parser allocates document trees."""
from io import BytesIO
from zipfile import ZipFile
from app.services.resource_limits import ExcelExpansionLimitExceeded, positive_setting


def validate_excel_expansion(source):
    stream = BytesIO(source) if isinstance(source, bytes) else source
    position = stream.tell()
    limit_mb = positive_setting("EXCEL_EXPANDED_MAX_MB", 100)
    limit = limit_mb * 1024 * 1024
    try:
        stream.seek(0)
        with ZipFile(stream) as archive:
            if sum(item.file_size for item in archive.infolist()) > limit:
                raise ExcelExpansionLimitExceeded(limit_mb)
            # Verify actual expansion and CRC as well as untrusted ZIP metadata.
            total = 0
            for item in archive.infolist():
                if item.is_dir():
                    continue
                with archive.open(item) as member:
                    while chunk := member.read(min(1024 * 1024, limit - total + 1)):
                        total += len(chunk)
                        if total > limit:
                            raise ExcelExpansionLimitExceeded(limit_mb)
    finally:
        stream.seek(position)
