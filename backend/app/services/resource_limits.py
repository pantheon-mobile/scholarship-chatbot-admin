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


class InputLimitExceeded(Exception):
    """Return a human-readable 422 before starting any mutation."""


def validate_bulk_delete_items(values):
    limit = positive_setting("BULK_DELETE_MAX_ITEMS", 1000)
    if isinstance(values, (list, tuple)) and len(values) > limit:
        raise InputLimitExceeded(f"一度に削除できる指定件数は{limit:,}件までです。選択件数を減らして再度実行してください。")
    return values


def validate_reorder_items(values):
    limit = positive_setting("REORDER_MAX_ITEMS", 1000)
    if isinstance(values, (list, tuple)) and len(values) > limit:
        raise InputLimitExceeded(f"一度に並び替えできる件数は{limit:,}件までです。システム管理者に上限設定の変更をご相談ください。")
    return values


def validate_faq_label(value):
    if isinstance(value, str) and len(value) > 100:
        raise InputLimitExceeded("区分ラベル名は100文字以内で入力してください。")
    return value


def validate_faq_value(value):
    if isinstance(value, str) and len(value) > 200:
        raise InputLimitExceeded("区分値は200文字以内で入力してください。")
    return value
