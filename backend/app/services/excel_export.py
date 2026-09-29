"""Synchronous Excel rendering, called in a worker with plain cell values."""
from io import BytesIO

from openpyxl import Workbook

from app.services.excel_format import append_safe_row, apply_download_format


def render_excel(title: str, rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    try:
        worksheet = workbook.active
        worksheet.title = title
        for row in rows:
            append_safe_row(worksheet, row)
        apply_download_format(worksheet)
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()
