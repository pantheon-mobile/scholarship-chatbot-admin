"""Customer-approved limits; no silent clipping or disabled-by-invalid-setting fallback."""
import os


def positive_setting(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def export_max_rows() -> int:
    return positive_setting("REPORT_EXPORT_MAX_ROWS", 10000)


class ExportLimitExceeded(Exception):
    def __init__(self, limit):
        super().__init__(f"一度に出力できる件数は{limit:,}件までです。期間や検索条件を絞って、もう一度ダウンロードしてください。")


class ExcelExpansionLimitExceeded(Exception):
    def __init__(self, limit_mb):
        super().__init__(f"Excelファイルの展開後サイズが上限の{limit_mb}MBを超えています。不要なシートやデータを削除するか、ファイルを分割して再度取り込んでください。")
