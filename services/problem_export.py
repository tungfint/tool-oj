"""Helpers for exporting problem statements from DMOJ-compatible sites."""

from __future__ import annotations

import html
import io
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

import requests

from services.hncode import public_problem_snapshot_from_html
from services import problem_pdf


CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
PROBLEM_LINK_PATTERN = re.compile(
    r"/(?:problem|problems)/([A-Za-z0-9_-]+)(?:[/?#]|$)", re.IGNORECASE
)
IMAGE_URL_PATTERN = re.compile(
    r"(?:https?://|data:image/)[^\s<>'\")]+?(?:\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?[^\s<>'\")]+)?|;base64,[A-Za-z0-9+/=]+)",
    re.IGNORECASE,
)


def contest_key(value: str) -> str:
    text = (value or "").strip()
    match = re.search(r"/contest/([^/?#\s]+)", text, re.IGNORECASE)
    key = html.unescape(match.group(1)).strip("/") if match else text.strip("/")
    if not CODE_PATTERN.fullmatch(key):
        raise ValueError("Không đọc được mã contest.")
    return key


def lesson_ref(value: str) -> tuple[str, str]:
    text = (value or "").strip()
    match = re.search(
        r"/course/([^/?#\s]+)/(?:lesson|edit_lessons_new)/(\d+)", text, re.IGNORECASE
    )
    if not match:
        raise ValueError(
            "Không đọc được lesson. Hãy nhập URL dạng /course/<ma_khoa_hoc>/lesson/<id>."
        )
    return html.unescape(match.group(1)), match.group(2)


def problem_codes(value: str) -> list[str]:
    """Parse problem links or plain codes while preserving input order."""
    text = html.unescape(value or "")
    found: list[str] = []
    seen: set[str] = set()

    def add(code: str) -> None:
        code = code.strip().strip("/")
        if CODE_PATTERN.fullmatch(code) and code not in seen:
            seen.add(code)
            found.append(code)

    def replace_url(match: re.Match[str]) -> str:
        problem_match = PROBLEM_LINK_PATTERN.search(match.group(0))
        return f" {problem_match.group(1)} " if problem_match else " "

    normalized = re.sub(r"https?://\S+", replace_url, text)
    normalized = PROBLEM_LINK_PATTERN.sub(lambda match: f" {match.group(1)} ", normalized)
    for token in re.split(r"[\s,;|]+", normalized):
        if token:
            add(token)
    return found


def detect_input_type(value: str, requested: str = "auto") -> str:
    if requested in {"contest", "lesson", "codes"}:
        return requested
    text = (value or "").strip()
    if re.search(r"/course/[^/?#\s]+/(?:lesson|edit_lessons_new)/\d+", text, re.I):
        return "lesson"
    if re.search(r"/contest/[^/?#\s]+", text, re.I):
        return "contest"
    tokens = problem_codes(text)
    if len(tokens) > 1 or re.search(r"/(?:problem|problems)/", text, re.I):
        return "codes"
    return "auto_single"


def absolute_asset_urls(markdown: str, base_url: str) -> str:
    """Make relative Markdown and HTML asset links portable."""

    def markdown_repl(match: re.Match[str]) -> str:
        prefix, raw_url, suffix = match.group(1), html.unescape(match.group(2)), match.group(3)
        if re.match(r"^(?:https?:)?//|mailto:|data:|#", raw_url, re.I):
            return match.group(0)
        return f"{prefix}{urljoin(base_url.rstrip('/') + '/', raw_url)}{suffix}"

    def html_repl(match: re.Match[str]) -> str:
        prefix, raw_url, suffix = match.group(1), html.unescape(match.group(2)), match.group(3)
        if re.match(r"^(?:https?:)?//|mailto:|data:|#", raw_url, re.I):
            return match.group(0)
        return f"{prefix}{urljoin(base_url.rstrip('/') + '/', raw_url)}{suffix}"

    result = re.sub(r"(!?\[[^\]]*\]\()([^\s)>]+)(\))", markdown_repl, markdown)
    return re.sub(
        r"(<(?:img|a)\b[^>]*(?:src|href)=[\"'])([^\"']+)([\"'])",
        html_repl,
        result,
        flags=re.I,
    )


def _field_value(page: str, name: str) -> str:
    textarea = re.search(
        r'<textarea\b[^>]*name=["\']'
        + re.escape(name)
        + r'["\'][^>]*>(.*?)</textarea>',
        page,
        re.I | re.S,
    )
    if textarea:
        return html.unescape(textarea.group(1))
    input_match = re.search(
        r'<input\b[^>]*name=["\']' + re.escape(name) + r'["\'][^>]*>',
        page,
        re.I | re.S,
    )
    if not input_match:
        return ""
    value = re.search(r'value=["\']([^"\']*)["\']', input_match.group(0), re.I | re.S)
    return html.unescape(value.group(1)) if value else ""


def _pdf_fallback(page: str, page_url: str) -> str:
    matches = re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', page, re.I)
    if not matches:
        matches = re.findall(r'https?://[^"\'<>\s]+\.pdf(?:\?[^"\'<>\s]+)?', page, re.I)
    if not matches:
        return ""
    return f"Đề bài dạng PDF: [Tải file đề bài]({urljoin(page_url, html.unescape(matches[0]))})"


def statement_image_urls(statement: str) -> list[str]:
    """Return image assets referenced by Markdown, HTML, links, or bare URLs."""
    text = html.unescape(statement or "")
    candidates: list[str] = []
    candidates.extend(
        re.findall(r"!\[[^\]]*\]\(\s*<?([^\s)>]+)>?(?:\s+[^)]*)?\)", text, re.I)
    )
    candidates.extend(
        re.findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", text, re.I | re.S)
    )
    for url in re.findall(r"\[[^\]]*\]\(\s*<?([^\s)>]+)>?(?:\s+[^)]*)?\)", text, re.I):
        if re.search(r"\.(?:png|jpe?g|gif|webp|bmp|svg)(?:[?#].*)?$", url, re.I):
            candidates.append(url)
    candidates.extend(match.group(0) for match in IMAGE_URL_PATTERN.finditer(text))
    result: list[str] = []
    seen: set[str] = set()
    for raw_url in candidates:
        url = raw_url.strip().strip("<>")
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


def requires_pdf(problem: dict[str, Any]) -> bool:
    return bool(problem.get("pdf_path") or problem.get("pdf_url") or statement_image_urls(str(problem.get("statement") or "")))


def _looks_like_math(value: str) -> bool:
    content = value.strip()
    if not content:
        return False
    if re.search(r"\\[A-Za-z]+|[0-9=<>_^{}+*/%]|(?:^|\s)-\s*\d", content):
        return True
    return bool(re.fullmatch(r"[A-Za-z](?:_[A-Za-z0-9{}]+)?", content))


def _normalize_tilde_math_block(block: str, aggressive: bool) -> str:
    protected: list[str] = []

    def protect(value: str) -> str:
        protected.append(value)
        return f"@@TOOLOJ_PROTECTED_{len(protected) - 1}@@"

    text = re.sub(
        r"(`+)(.*?)(\1)",
        lambda match: protect(match.group(0)),
        block,
        flags=re.S,
    )
    text = re.sub(
        r"(?<!\\)\$\$(.+?)(?<!\\)\$\$",
        lambda match: protect(match.group(0)),
        text,
        flags=re.S,
    )
    text = re.sub(
        r"(?<![\\$])\$(?!\$)([^$\r\n]+?)(?<!\\)\$(?!\$)",
        lambda match: protect(match.group(0)),
        text,
    )
    text = re.sub(r"https?://[^\s<>'\")]+", lambda match: protect(match.group(0)), text)
    text = re.sub(r"\\~", lambda match: protect(match.group(0)), text)

    def replace_double(match: re.Match[str]) -> str:
        content = match.group(1)
        return f"$${content}$$" if aggressive or _looks_like_math(content) else match.group(0)

    def replace_single(match: re.Match[str]) -> str:
        content = match.group(1)
        return f"${content}$" if aggressive or _looks_like_math(content) else match.group(0)

    text = re.sub(r"(?<!~)~~(?!~)(.+?)(?<!~)~~(?!~)", replace_double, text, flags=re.S)
    text = re.sub(r"(?<!~)~(?!~)([^~\r\n]+?)(?<!~)~(?!~)", replace_single, text)
    for index, value in reversed(list(enumerate(protected))):
        text = text.replace(f"@@TOOLOJ_PROTECTED_{index}@@", value)
    return text


def canonical_markdown_math(statement: str, *, aggressive: bool = False) -> str:
    """Convert HNOJ tilde math to canonical dollar math without touching code/URLs."""
    lines = (statement or "").splitlines(keepends=True)
    output: list[str] = []
    normal_block: list[str] = []
    fence_char = ""

    def flush_normal() -> None:
        if normal_block:
            output.append(_normalize_tilde_math_block("".join(normal_block), aggressive))
            normal_block.clear()

    for line in lines:
        fence = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_char:
            output.append(line)
            if fence and fence.group(1).startswith(fence_char):
                fence_char = ""
            continue
        if fence:
            flush_normal()
            fence_char = fence.group(1)[0]
            output.append(line)
            continue
        normal_block.append(line)
    flush_normal()
    return "".join(output)


def _download_pdf(
    session: requests.Session,
    pdf_url: str,
    code: str,
    output_dir: Path,
    timeout: int,
) -> Path:
    response = session.get(pdf_url, timeout=max(timeout, 60), allow_redirects=True)
    if not response.ok:
        raise RuntimeError(f"Tải PDF nguồn {code} lỗi HTTP {response.status_code}.")
    content = response.content
    if not content.lstrip().startswith(b"%PDF"):
        content_type = response.headers.get("Content-Type", "")
        raise RuntimeError(
            f"Link PDF nguồn {code} không trả dữ liệu PDF (Content-Type: {content_type or 'không rõ'})."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{code}.pdf"
    path.write_bytes(content)
    return path


def fetch_statement(
    session: requests.Session,
    base_url: str,
    code: str,
    timeout: int = 45,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Fetch editor Markdown plus the original PDF when the problem uses one."""
    edit_url = urljoin(base_url, f"/problem/{code}/edit")
    edit = session.get(edit_url, timeout=timeout, allow_redirects=True)
    edit_page = ""
    name = code
    statement = ""
    if edit.ok and "/login" not in edit.url:
        edit_page = edit.text
        name = _field_value(edit_page, "name").strip() or code
        statement = _field_value(edit_page, "description").strip()

    public_url = urljoin(base_url, f"/problem/{code}")
    public = session.get(public_url, timeout=timeout, allow_redirects=True)
    if not public.ok:
        raise RuntimeError(f"Không mở được bài {code}: HTTP {public.status_code}.")
    pdf_url = problem_pdf.find_problem_pdf_url(base_url, code, public.text, edit_page)
    pdf_path: Path | None = None
    if pdf_url and output_dir is not None:
        pdf_path = _download_pdf(session, pdf_url, code, output_dir, timeout)
    if not statement and not pdf_url:
        snapshot = public_problem_snapshot_from_html(public.text, code, base_url)
        name = str(snapshot.get("name") or name or code)
        statement = str(snapshot.get("statement") or "")
    result: dict[str, Any] = {
        "code": code,
        "name": name,
        "statement": absolute_asset_urls(statement, base_url),
        "link": public_url,
        "pdf_url": pdf_url,
        "pdf_path": str(pdf_path) if pdf_path else "",
    }
    return result


def one_problem_markdown(problem: dict[str, Any], site: str = "") -> str:
    title = (problem.get("name") or problem["code"]).strip()
    statement = canonical_markdown_math(
        str(problem.get("statement") or ""), aggressive=site == "hnoj"
    ).strip()
    return f"{title} | {problem['code']}\n\n{statement}\n"


def combined_markdown(
    problems: Iterable[dict[str, Any]], source_label: str, site: str = ""
) -> str:
    rows = list(problems)
    lines = ["# Tổng hợp đề bài", "", f"Nguồn: **{source_label}**", ""]
    for index, problem in enumerate(rows, 1):
        title = (problem.get("name") or problem["code"]).strip()
        lines.extend(
            [
                f"## {index}. {title} (`{problem['code']}`)",
                "",
                canonical_markdown_math(
                    str(problem.get("statement") or ""), aggressive=site == "hnoj"
                ).strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _font_paths() -> tuple[str | None, str | None]:
    candidates = [
        (
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ),
    ]
    for regular, bold in candidates:
        if Path(regular).is_file():
            return regular, bold if Path(bold).is_file() else regular
    return None, None


def _register_pdf_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular, bold = _font_paths()
    if not regular:
        return "Helvetica", "Helvetica-Bold"
    regular_name = "ToolOJUnicode"
    bold_name = "ToolOJUnicodeBold"
    if regular_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(regular_name, regular))
    if bold_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(bold_name, bold or regular))
    return regular_name, bold_name


def _image_markers(statement: str) -> tuple[str, list[str]]:
    images: list[str] = []

    def marker(url: str) -> str:
        clean = html.unescape(url).strip().strip("<>")
        try:
            index = images.index(clean)
        except ValueError:
            images.append(clean)
            index = len(images) - 1
        return f"\n@@TOOLOJ_IMAGE_{index}@@\n"

    text = statement or ""
    text = re.sub(
        r"!\[[^\]]*\]\(\s*<?([^\s)>]+)>?(?:\s+[^)]*)?\)",
        lambda match: marker(match.group(1)),
        text,
        flags=re.I,
    )
    text = re.sub(
        r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>",
        lambda match: marker(match.group(1)),
        text,
        flags=re.I | re.S,
    )
    text = re.sub(
        r"\[[^\]]*\]\(\s*<?([^\s)>]+\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?[^\s)>]*)?)>?(?:\s+[^)]*)?\)",
        lambda match: marker(match.group(1)),
        text,
        flags=re.I,
    )
    text = re.sub(
        r"<a\b[^>]*\bhref=[\"']([^\"']+\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?[^\"']*)?)[\"'][^>]*>.*?</a>",
        lambda match: marker(match.group(1)),
        text,
        flags=re.I | re.S,
    )
    text = IMAGE_URL_PATTERN.sub(lambda match: marker(match.group(0)), text)
    return text, images


def _image_flowable(session: requests.Session, image_url: str, max_width: float):
    from PIL import Image as PillowImage
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet

    try:
        if image_url.lower().startswith("data:image/"):
            import base64

            encoded = image_url.split(",", 1)[1]
            raw = base64.b64decode(encoded)
        else:
            response = session.get(image_url, timeout=60, allow_redirects=True)
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status_code}")
            raw = response.content
        source = io.BytesIO(raw)
        with PillowImage.open(source) as opened:
            if getattr(opened, "n_frames", 1) > 1:
                opened.seek(0)
            converted = opened.convert("RGB")
            converted.thumbnail((2400, 3200))
            normalized = io.BytesIO()
            converted.save(normalized, format="PNG")
        normalized.seek(0)
        reader = ImageReader(normalized)
        width, height = reader.getSize()
        scale = min(1.0, max_width / max(width, 1), 680 / max(height, 1))
        flowable = Image(normalized, width=width * scale, height=height * scale)
        flowable.hAlign = "CENTER"
        return flowable
    except Exception as exc:
        style = getSampleStyleSheet()["BodyText"]
        return Paragraph(
            f"[Không tải được ảnh: {html.escape(image_url)} - {html.escape(str(exc))}]",
            style,
        )


def _plain_markdown_text(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^\s*(?:!!!|\?\?\?\+?)\s*", "", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    return text


def render_problem_pdf(
    path: Path,
    problem: dict[str, Any],
    session: requests.Session | None = None,
) -> Path:
    """Render text/image statements to a readable Unicode PDF."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        Preformatted,
        SimpleDocTemplate,
        Spacer,
    )

    session = session or requests.Session()
    regular_font, bold_font = _register_pdf_fonts()
    path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=str(problem.get("name") or problem.get("code") or "Đề bài"),
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ToolOJBody",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=10.5,
        leading=15,
        spaceAfter=4,
    )
    title_style = ParagraphStyle(
        "ToolOJTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=17,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#153f6f"),
        spaceAfter=12,
    )
    heading = ParagraphStyle(
        "ToolOJHeading",
        parent=body,
        fontName=bold_font,
        fontSize=12,
        leading=16,
        spaceBefore=8,
        spaceAfter=5,
    )
    code_style = ParagraphStyle(
        "ToolOJCode",
        parent=body,
        fontName=regular_font,
        fontSize=8.5,
        leading=11,
        leftIndent=8,
        backColor=colors.HexColor("#f3f5f7"),
        borderPadding=6,
    )
    story = [
        Paragraph(html.escape(str(problem.get("name") or problem.get("code") or "Đề bài")), title_style),
        Paragraph(f"Mã bài: <b>{html.escape(str(problem.get('code') or ''))}</b>", body),
        Spacer(1, 6),
    ]
    marked, images = _image_markers(str(problem.get("statement") or ""))
    in_code = False
    code_lines: list[str] = []
    for raw_line in marked.splitlines():
        line = raw_line.rstrip()
        marker_match = re.fullmatch(r"@@TOOLOJ_IMAGE_(\d+)@@", line.strip())
        if marker_match:
            if code_lines:
                story.append(Preformatted("\n".join(code_lines), code_style))
                code_lines = []
            story.append(_image_flowable(session, images[int(marker_match.group(1))], document.width))
            story.append(Spacer(1, 7))
            continue
        if line.strip().startswith("```"):
            if in_code:
                story.append(Preformatted("\n".join(code_lines), code_style))
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            story.append(Spacer(1, 4))
            continue
        heading_match = re.match(r"^#{1,6}\s+(.+)$", line.strip())
        if heading_match:
            story.append(Paragraph(html.escape(_plain_markdown_text(heading_match.group(1))), heading))
            continue
        bullet_match = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if bullet_match:
            value = html.escape(_plain_markdown_text(bullet_match.group(1)))
            story.append(Paragraph(f"• {value}", body))
            continue
        story.append(Paragraph(html.escape(_plain_markdown_text(line)), body))
    if code_lines:
        story.append(Preformatted("\n".join(code_lines), code_style))
    if not str(problem.get("statement") or "").strip():
        story.append(Paragraph("Đề bài được cung cấp trong file PDF gốc.", body))
    document.build(story)
    return path


def _problem_pdf_path(
    output_dir: Path,
    problem: dict[str, Any],
    session: requests.Session | None,
) -> Path:
    source_path = Path(str(problem.get("pdf_path") or ""))
    if source_path.is_file():
        return source_path
    pdf_url = str(problem.get("pdf_url") or "")
    if pdf_url:
        return _download_pdf(
            session or requests.Session(), pdf_url, str(problem.get("code") or "problem"), output_dir / "sources", 60
        )
    return render_problem_pdf(
        output_dir / "rendered" / f"{problem['code']}.pdf", problem, session
    )


def _combined_pdf(
    path: Path,
    output_dir: Path,
    problems: list[dict[str, Any]],
    session: requests.Session | None,
) -> Path:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for problem in problems:
        if requires_pdf(problem):
            problem_path = _problem_pdf_path(output_dir, problem, session)
        else:
            problem_path = render_problem_pdf(
                output_dir / "rendered" / f"{problem['code']}.pdf", problem, session
            )
        reader = PdfReader(str(problem_path))
        for page in reader.pages:
            writer.add_page(page)
    with path.open("wb") as target:
        writer.write(target)
    return path


def write_export(
    output_dir: Path,
    problems: list[dict[str, Any]],
    mode: str,
    site: str,
    source_label: str,
    session: requests.Session | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if mode == "combined":
        if any(requires_pdf(problem) for problem in problems):
            return _combined_pdf(
                output_dir / f"tong_hop_de_bai_{site}.pdf",
                output_dir,
                problems,
                session,
            )
        path = output_dir / f"tong_hop_de_bai_{site}.md"
        path.write_text(
            combined_markdown(problems, source_label, site), encoding="utf-8-sig"
        )
        return path

    path = output_dir / f"de_bai_{site}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for problem in problems:
            if requires_pdf(problem):
                pdf_path = _problem_pdf_path(output_dir, problem, session)
                archive.write(pdf_path, f"{problem['code']}.pdf")
            else:
                archive.writestr(
                    f"{problem['code']}.md",
                    one_problem_markdown(problem, site).encode("utf-8-sig"),
                )
    return path


def zip_markdown_names(raw: bytes) -> list[str]:
    """Small inspection helper used by tests."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return archive.namelist()
