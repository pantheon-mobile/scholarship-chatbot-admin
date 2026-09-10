from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import boto3
import fitz
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation


@dataclass(frozen=True)
class ConvertedDocument:
    name: str
    markdown: str
    source_url: str | None = None
    metadata: dict | None = None


PDF_CONTENT_METADATA_KEYS = (
    "document_type", "category", "business", "system", "school_type",
    "target_user", "keywords", "summary",
)

WEB_SKIP_SCHEMES = ("javascript:", "mailto:", "tel:", "data:")
WEB_SKIP_EXTENSIONS = re.compile(
    r"\.(?:pdf|docx?|xlsx?|xls|pptx?|jpe?g|png|gif|svg|webp|zip|rar|7z|mp3|mp4|mov|avi)(?:$|\?)",
    re.IGNORECASE,
)
WEB_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "yclid", "mc_cid", "mc_eid", "ref", "referrer"}
WEB_NOISE_SELECTORS = (
    "header", "footer", "nav", "menu", "aside", "script", "style", "form", "iframe",
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
    "[aria-label*='breadcrumb' i]", ".breadcrumb", ".breadcrumbs", ".cookie",
    ".cookie-banner", ".sidebar", ".side-bar", ".advertisement", ".ads",
    ".social", ".share", ".nav-item", ".local-nav", ".sub-nav", ".side-nav",
    "#cookie", "#sidebar",
)


def _extract_json_object(value: str) -> dict:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Claudeの応答にJSONがありません。")
    parsed = json.loads(cleaned[start:end + 1])
    attributes = parsed.get("metadataAttributes", parsed)
    if not isinstance(attributes, dict):
        raise ValueError("metadataAttributesがオブジェクトではありません。")
    return attributes


def generate_pdf_content_metadata(content: bytes, name: str, *, max_pages: int = 5) -> dict:
    """Generate the semantic metadata proven in the ingestion PoC."""
    pdf = fitz.open(stream=content, filetype="pdf")
    try:
        selected_pages = list(pdf)[:max_pages]
        head_text = "\n\n".join(
            f"--- ページ {index} ---\n{page.get_text('text').strip()}"
            for index, page in enumerate(selected_pages, start=1)
            if page.get_text("text").strip()
        ).strip()
        if not head_text:
            head_text = "\n\n".join(
                _vision_page_markdown(page, index)
                for index, page in enumerate(selected_pages, start=1)
            ).strip()
    finally:
        pdf.close()
    if not head_text:
        raise ValueError("PDF先頭5ページから内容を取得できませんでした。")

    model_id = (
        os.getenv("PDF_METADATA_MODEL_ID", "").strip()
        or os.getenv("PDF_VISION_MODEL_ID", "").strip()
        or os.getenv("CHAT_MODEL_ARN", "").strip()
    )
    if not model_id:
        raise RuntimeError("PDF_METADATA_MODEL_IDが未設定です。")
    prompt = f"""あなたはAmazon Bedrock Knowledge BasesのRAG設計者です。
以下のPDF先頭最大5ページとファイル名をもとに、検索補助メタデータを生成してください。

ファイル名:
{name}

PDF先頭テキスト:
{head_text}

次のJSONのみを返してください。
{{"metadataAttributes":{{"document_type":"","category":"","business":"","system":"","school_type":"","target_user":"","keywords":[],"summary":""}}}}

ルール:
- document_type: 操作マニュアル / 規程 / FAQ / データ仕様書 / 申請書 / 通知 / その他
- target_user: 学生 / 教員 / 職員 / all
- keywords: 検索で使われそうな語を10〜20個
- summary: 100文字程度
- 不明な項目は空文字とし、JSON以外を出力しない
"""
    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1500, "temperature": 0},
    )
    response_text = response["output"]["message"]["content"][0]["text"]
    raw = _extract_json_object(response_text)
    metadata = {key: raw.get(key, [] if key == "keywords" else "") for key in PDF_CONTENT_METADATA_KEYS}
    if not isinstance(metadata["keywords"], list):
        metadata["keywords"] = [str(metadata["keywords"])] if metadata["keywords"] else []
    metadata["keywords"] = [str(item).strip() for item in metadata["keywords"] if str(item).strip()][:20]
    metadata["source_file_name"] = name
    metadata["metadata_generated_at"] = datetime.now(timezone.utc).isoformat()
    metadata["metadata_source_pages"] = min(len(selected_pages), max_pages)
    metadata["metadata_generation_method"] = "claude_pdf_head"
    return metadata


def _table_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    escaped = [[str(value or "").replace("|", "\\|").replace("\n", "<br>") for value in row]
               for row in normalized]
    return "\n".join([
        "| " + " | ".join(escaped[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
        *("| " + " | ".join(row) + " |" for row in escaped[1:]),
    ])


def convert_xlsx(content: bytes, name: str) -> list[ConvertedDocument]:
    workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    documents = []
    for index, sheet in enumerate(workbook.worksheets, start=1):
        if sheet.sheet_state != "visible":
            continue
        rows = [["" if value is None else str(value) for value in row]
                for row in sheet.iter_rows(values_only=True)]
        while rows and not any(cell for cell in rows[-1]):
            rows.pop()
        if not rows:
            continue
        documents.append(ConvertedDocument(
            name=f"sheet-{index:03d}.md",
            markdown=f"# {name}\n\n## シート: {sheet.title}\n\n{_table_markdown(rows)}",
            metadata={"sheet_name": sheet.title, "sheet_index": index},
        ))
    workbook.close()
    return documents


def convert_docx(content: bytes, name: str) -> list[ConvertedDocument]:
    document = Document(io.BytesIO(content))
    blocks: list[str] = [f"# {name}"]
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name or "").lower() if paragraph.style else ""
        if style.startswith("heading"):
            level = int("".join(character for character in style if character.isdigit()) or "1")
            blocks.append(f"{'#' * min(level + 1, 6)} {text}")
        elif "bullet" in style or "箇条書き" in style:
            blocks.append(f"- {text}")
        else:
            blocks.append(text)
    for table in document.tables:
        blocks.append(_table_markdown([[cell.text.strip() for cell in row.cells] for row in table.rows]))
    return [ConvertedDocument("source.md", "\n\n".join(blocks))]


def convert_pptx(content: bytes, name: str) -> list[ConvertedDocument]:
    presentation = Presentation(io.BytesIO(content))
    blocks = [f"# {name}"]
    for slide_number, slide in enumerate(presentation.slides, start=1):
        title = slide.shapes.title.text.strip() if slide.shapes.title else f"スライド {slide_number}"
        blocks.extend([f"## {slide_number}. {title}", f"<!-- slide {slide_number} -->"])
        for shape in slide.shapes:
            if getattr(shape, "has_table", False):
                blocks.append(_table_markdown(
                    [[cell.text.strip() for cell in row.cells] for row in shape.table.rows]
                ))
            elif getattr(shape, "has_text_frame", False):
                text = shape.text.strip()
                if text and text != title:
                    blocks.append(text)
        try:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            notes = ""
        if notes:
            blocks.extend(["### 発表者ノート", notes])
    return [ConvertedDocument("source.md", "\n\n".join(blocks))]


def _vision_page_markdown(page, page_number: int) -> str:
    model_id = os.getenv("PDF_VISION_MODEL_ID", "").strip()
    if not model_id:
        raise RuntimeError(
            "画像中心のPDFです。PDF_VISION_MODEL_IDを設定してVision変換を有効にしてください。"
        )
    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    image = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image}},
                {"type": "text", "text": "このページを、見出し・箇条書き・表を保った日本語Markdownに変換してください。Markdown本文だけを返してください。"},
            ]}],
        }).encode("utf-8"),
    )
    body = json.loads(response["body"].read())
    return "\n".join(item["text"] for item in body.get("content", []) if item.get("type") == "text")


def convert_pdf(content: bytes, name: str) -> list[ConvertedDocument]:
    pdf = fitz.open(stream=content, filetype="pdf")
    page_texts = [page.get_text("text").strip() for page in pdf]
    page_image_counts = [len(page.get_images(full=True)) for page in pdf]
    image_count = sum(page_image_counts)
    image_page_count = sum(count > 0 for count in page_image_counts)
    table_count = 0
    for page in pdf:
        try:
            table_count += len(page.find_tables().tables)
        except Exception:
            # Table detection is an aid to selection; unsupported PDFs must still ingest.
            pass
    extracted_characters = sum(len(text) for text in page_texts)
    chars_per_page = extracted_characters / max(len(pdf), 1)
    image_page_ratio = image_page_count / max(len(pdf), 1)
    min_chars = float(os.getenv("PDF_VISION_MIN_CHARS_PER_PAGE", "100"))
    image_ratio_threshold = float(os.getenv("PDF_VISION_IMAGE_PAGE_RATIO", "0.5"))
    table_threshold = int(os.getenv("PDF_VISION_MIN_TABLES", "3"))
    use_vision = (
        chars_per_page < min_chars
        or (image_page_ratio >= image_ratio_threshold and chars_per_page < min_chars * 5)
        or table_count >= table_threshold
    )
    pages = []
    page_methods: list[str] = []
    vision_failed_pages: list[int] = []
    for index, page in enumerate(pdf, start=1):
        extracted_text = page_texts[index - 1]
        page_needs_vision = use_vision or (
            page_image_counts[index - 1] > 0 and len(extracted_text) < min_chars
        )
        if page_needs_vision:
            try:
                text = _vision_page_markdown(page, index)
                page_methods.append("VISION_MARKDOWN")
            except Exception:
                if not extracted_text:
                    pdf.close()
                    raise
                text = extracted_text
                page_methods.append("TEXT_MARKDOWN_FALLBACK")
                vision_failed_pages.append(index)
        else:
            text = extracted_text
            page_methods.append("TEXT_MARKDOWN")
        pages.append(f"## ページ {index}\n\n{text}")
    distinct_methods = set(page_methods)
    method = next(iter(distinct_methods)) if len(distinct_methods) == 1 else "HYBRID_MARKDOWN"
    reasons = []
    if chars_per_page < min_chars:
        reasons.append("low_text_density")
    if image_page_ratio >= image_ratio_threshold:
        reasons.append("image_heavy")
    if table_count >= table_threshold:
        reasons.append("complex_tables")
    if not reasons:
        reasons.append("text_extraction_sufficient")
    metadata = {
        "conversion_method": method,
        "selection_reason": ",".join(reasons),
        "page_count": len(pdf),
        "image_count": image_count,
        "image_page_count": image_page_count,
        "image_page_ratio": round(image_page_ratio, 4),
        "table_count": table_count,
        "extracted_characters": extracted_characters,
        "characters_per_page": round(chars_per_page, 1),
        "vision_page_count": page_methods.count("VISION_MARKDOWN"),
        "text_page_count": page_methods.count("TEXT_MARKDOWN"),
        "vision_fallback_page_count": page_methods.count("TEXT_MARKDOWN_FALLBACK"),
        "vision_failed_pages": ",".join(str(page) for page in vision_failed_pages),
    }
    pdf.close()
    return [ConvertedDocument("source.md", f"# {name}\n\n" + "\n\n".join(pages), metadata=metadata)]


def convert_plain_text(content: bytes, name: str) -> list[ConvertedDocument]:
    text = content.decode("utf-8-sig", errors="replace")
    if name.lower().endswith(".csv"):
        rows = list(csv.reader(io.StringIO(text)))
        text = _table_markdown(rows)
    return [ConvertedDocument("source.md", f"# {name}\n\n{text}")]


def _normalize_url(url: str, base: str = "") -> str:
    raw = (url or "").strip()
    if not raw or raw.lower().startswith(WEB_SKIP_SCHEMES) or raw.startswith("#"):
        return ""
    parts = urlsplit(urljoin(base, raw))
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return ""
    if WEB_SKIP_EXTENSIONS.search(parts.path):
        return ""
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    query = urlencode(sorted(
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in WEB_TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
    ))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.lower(), parts.hostname.lower() + port, path, query, ""))


def _web_table_markdown(table: Tag) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return _table_markdown(rows)


def _web_element_markdown(element: Tag, base_url: str) -> str:
    name = element.name.lower()
    if re.fullmatch(r"h[1-6]", name):
        return f"{'#' * int(name[1])} {element.get_text(' ', strip=True)}"
    if name == "p":
        pieces: list[str] = []
        for child in element.descendants:
            if not isinstance(child, NavigableString) or child.parent.name in {"script", "style"}:
                continue
            if child.parent.name == "a" and child.parent.get("href"):
                if child is next(iter(child.parent.children), None):
                    label = child.parent.get_text(" ", strip=True)
                    href = _normalize_url(child.parent["href"], base_url)
                    pieces.append(f"[{label}]({href})" if href else label)
            elif child.find_parent("a") is None:
                pieces.append(str(child))
        return re.sub(r"\s+", " ", "".join(pieces)).strip()
    if name in {"ul", "ol"}:
        return "\n".join(
            f"{f'{index}.' if name == 'ol' else '-'} {li.get_text(' ', strip=True)}"
            for index, li in enumerate(element.find_all("li", recursive=False), start=1)
        )
    if name == "table":
        return _web_table_markdown(element)
    return ""


def crawl_website(root_url: str, report: dict | None = None) -> list[ConvertedDocument]:
    started = datetime.now(timezone.utc).isoformat()
    report = report if report is not None else {}
    report.update({"started_at": started, "pages": [], "errors": [], "skipped": []})
    root = _normalize_url(root_url)
    if not root:
        raise RuntimeError("クロール起点URLが不正です。")
    root_parts = urlsplit(root)
    root_path = root_parts.path if root_parts.path.endswith("/") else root_parts.path.rsplit("/", 1)[0] + "/"
    max_pages = int(os.getenv("WEB_CRAWL_MAX_PAGES", "500"))
    max_depth = int(os.getenv("WEB_CRAWL_MAX_DEPTH", "5"))
    timeout = float(os.getenv("WEB_CRAWL_TIMEOUT_SECONDS", "20"))
    interval = max(float(os.getenv("WEB_CRAWL_INTERVAL_SECONDS", "0.5")), 0.0)
    session = requests.Session()
    session.headers["User-Agent"] = os.getenv("WEB_CRAWL_USER_AGENT", "ScholarshipChatbotCrawler/1.0")
    robots = None
    if os.getenv("WEB_CRAWL_RESPECT_ROBOTS", "true").lower() in {"1", "true", "yes", "on"}:
        robots = RobotFileParser(f"{root_parts.scheme}://{root_parts.netloc}/robots.txt")
        try:
            robots.read()
        except Exception:
            robots = None
    pending = [(root, 0)]
    visited: set[str] = set()
    documents: list[ConvertedDocument] = []
    last_request_at = 0.0
    while pending and len(documents) < max_pages:
        url, depth = pending.pop(0)
        if url in visited:
            continue
        if depth > max_depth:
            report["skipped"].append({"url": url, "depth": depth, "reason": "max_depth"})
            continue
        visited.add(url)
        parts = urlsplit(url)
        if parts.hostname != root_parts.hostname or not parts.path.startswith(root_path):
            report["skipped"].append({"url": url, "depth": depth, "reason": "outside_scope"})
            continue
        if robots and not robots.can_fetch(session.headers["User-Agent"], url):
            report["skipped"].append({"url": url, "depth": depth, "reason": "robots_disallowed"})
            continue
        response = None
        last_error = None
        for attempt in range(3):
            wait = interval - (time.monotonic() - last_request_at)
            if wait > 0:
                time.sleep(wait)
            try:
                response = session.get(url, timeout=timeout)
                last_request_at = time.monotonic()
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After", "")
                    last_error = requests.HTTPError(
                        f"HTTP {response.status_code}", response=response
                    )
                    response = None
                    if attempt < 2:
                        time.sleep(float(retry_after) if retry_after.isdigit() else 2 ** attempt)
                    continue
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error = exc
                response = None
                if attempt < 2:
                    time.sleep(2 ** attempt)
        if response is None:
            report["errors"].append({"url": url, "depth": depth, "reason": str(last_error or "request_failed")})
            continue
        if "html" not in response.headers.get("Content-Type", "").lower():
            report["skipped"].append({"url": url, "depth": depth, "reason": "non_html"})
            continue
        response.encoding = response.apparent_encoding or response.encoding
        soup = BeautifulSoup(response.text, "lxml")
        for selector in WEB_NOISE_SELECTORS:
            for node in soup.select(selector):
                node.decompose()
        main = soup.find("main") or soup.find("article") or soup.body
        if main is None:
            report["skipped"].append({"url": url, "depth": depth, "reason": "main_not_found"})
            continue
        title = soup.title.get_text(" ", strip=True) if soup.title else url
        text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
        if len(text) >= 20:
            page_id = hashlib.sha256(url.encode()).hexdigest()[:20]
            blocks = [f"# {title}", f"元URL: {url}"]
            for element in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table"]):
                if element.find_parent(["ul", "ol", "table"]):
                    continue
                block = _web_element_markdown(element, url)
                if block:
                    blocks.append(block)
            markdown = "\n\n".join(blocks)
            content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
            authority = "high" if (parts.hostname or "").endswith("jasso.go.jp") else "medium"
            documents.append(ConvertedDocument(
                f"web-{page_id}.md", markdown,
                source_url=url, metadata={
                    "crawl_depth": depth, "content_hash": content_hash,
                    "source_authority": authority, "page_title": title,
                },
            ))
            report["pages"].append({
                "page_id": page_id, "source_url": url, "title": title,
                "depth": depth, "content_hash": content_hash, "source_authority": authority,
            })
        else:
            report["skipped"].append({"url": url, "depth": depth, "reason": "content_too_short"})
        for anchor in main.find_all("a", href=True):
            raw_href = anchor["href"]
            child = _normalize_url(raw_href, url)
            if child and child not in visited:
                pending.append((child, depth + 1))
            elif not child and WEB_SKIP_EXTENSIONS.search(urlsplit(urljoin(url, raw_href)).path):
                report["skipped"].append({
                    "url": urljoin(url, raw_href), "depth": depth + 1,
                    "reason": "unsupported_extension",
                })
    if pending and len(documents) >= max_pages:
        report["skipped"].append({
            "url": root, "depth": 0, "reason": f"max_pages_reached:{max_pages}",
        })
    if not documents:
        raise RuntimeError("Webサイトから本文を取得できませんでした。")
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["summary"] = {
        "fetched": len(documents), "errors": len(report["errors"]),
        "skipped": len(report["skipped"]), "visited": len(visited),
    }
    return documents
