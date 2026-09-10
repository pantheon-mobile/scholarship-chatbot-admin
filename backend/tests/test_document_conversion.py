from io import BytesIO

from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches
import requests

from app.services.document_conversion import crawl_website, convert_docx, convert_pdf, convert_pptx, convert_xlsx


def test_xlsx_is_split_into_visible_markdown_sheets():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "入力"
    sheet.append(["項目", "金額"])
    sheet.append(["授業料", 1000])
    hidden = workbook.create_sheet("非表示")
    hidden.sheet_state = "hidden"
    hidden.append(["秘密"])
    output = BytesIO()
    workbook.save(output)

    documents = convert_xlsx(output.getvalue(), "sample.xlsx")

    assert len(documents) == 1
    assert documents[0].name == "sheet-001.md"
    assert "## シート: 入力" in documents[0].markdown
    assert "| 授業料 | 1000 |" in documents[0].markdown


def test_docx_keeps_headings_paragraphs_and_tables():
    document = Document()
    document.add_heading("奨学金案内", level=1)
    document.add_paragraph("申請してください。")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "区分"
    table.cell(0, 1).text = "金額"
    table.cell(1, 0).text = "第一種"
    table.cell(1, 1).text = "50000"
    output = BytesIO()
    document.save(output)

    converted = convert_docx(output.getvalue(), "guide.docx")[0].markdown

    assert "## 奨学金案内" in converted
    assert "申請してください。" in converted
    assert "| 第一種 | 50000 |" in converted


def test_pptx_keeps_slide_order_text_and_tables():
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "制度概要"
    textbox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(5), Inches(1))
    textbox.text = "対象者は学生です。"
    output = BytesIO()
    presentation.save(output)

    converted = convert_pptx(output.getvalue(), "guide.pptx")[0].markdown

    assert "## 1. 制度概要" in converted
    assert "対象者は学生です。" in converted


class FakeWebResponse:
    def __init__(self, text: str, status: int = 200, content_type: str = "text/html"):
        self.text = text
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_web_crawl_preserves_structure_normalizes_urls_and_continues_errors(monkeypatch):
    pages = {
        "https://www.jasso.go.jp/guide/": FakeWebResponse(
            "<html><head><title>制度案内</title></head><body>"
            "<header><a href='/noise'>メニュー</a></header><main>"
            "<h1>奨学金</h1><p>十分な長さの制度説明です。<a href='detail?utm_source=x'>詳細</a></p>"
            "<table><tr><th>区分</th><th>金額</th></tr><tr><td>第一種</td><td>50000</td></tr></table>"
            "<a href='missing'>失敗</a><a href='file.pdf'>PDF</a></main></body></html>"
        ),
        "https://www.jasso.go.jp/guide/detail": FakeWebResponse(
            "<html><body><main><h2>申請</h2><p>申請方法についての十分な説明本文です。</p></main></body></html>"
        ),
        "https://www.jasso.go.jp/guide/missing": FakeWebResponse("not found", 404),
    }

    class FakeSession:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout):
            return pages[url]

    monkeypatch.setenv("WEB_CRAWL_RESPECT_ROBOTS", "false")
    monkeypatch.setenv("WEB_CRAWL_INTERVAL_SECONDS", "0")
    monkeypatch.setattr("app.services.document_conversion.requests.Session", FakeSession)
    report = {}

    documents = crawl_website("https://www.jasso.go.jp/guide/", report)

    assert len(documents) == 2
    assert "| 区分 | 金額 |" in documents[0].markdown
    assert "メニュー" not in documents[0].markdown
    assert documents[0].metadata["source_authority"] == "high"
    assert documents[0].metadata["content_hash"]
    assert report["summary"]["fetched"] == 2
    assert any(item["reason"].startswith("HTTP 404") for item in report["errors"])
    assert any(item["reason"] == "unsupported_extension" for item in report["skipped"])


def test_pdf_complex_tables_select_vision_and_falls_back_to_text(monkeypatch):
    class Tables:
        tables = [object(), object(), object()]

    class Page:
        def get_text(self, mode):
            return "抽出済み本文" * 50

        def get_images(self, full=True):
            return []

        def find_tables(self):
            return Tables()

    class Pdf(list):
        def close(self):
            pass

    monkeypatch.setattr("app.services.document_conversion.fitz.open", lambda **_: Pdf([Page()]))
    monkeypatch.setattr(
        "app.services.document_conversion._vision_page_markdown",
        lambda *_: (_ for _ in ()).throw(RuntimeError("vision unavailable")),
    )

    document = convert_pdf(b"pdf", "table.pdf")[0]

    assert document.metadata["conversion_method"] == "TEXT_MARKDOWN_FALLBACK"
    assert "complex_tables" in document.metadata["selection_reason"]
    assert document.metadata["table_count"] == 3
    assert document.metadata["vision_fallback_page_count"] == 1
