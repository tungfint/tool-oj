"""Helpers for exporting problem statements from DMOJ-compatible sites."""

from __future__ import annotations

import html
import io
import re
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from services.hncode import public_problem_snapshot_from_html


CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
PROBLEM_LINK_PATTERN = re.compile(
    r"/(?:problem|problems)/([A-Za-z0-9_-]+)(?:[/?#]|$)", re.IGNORECASE
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


def _field_value(soup: BeautifulSoup, name: str) -> str:
    element = soup.select_one(f'[name="{name}"]')
    if not element:
        return ""
    if element.name == "textarea":
        return element.get_text()
    return str(element.get("value", ""))


def _pdf_fallback(page: str, page_url: str) -> str:
    matches = re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', page, re.I)
    if not matches:
        matches = re.findall(r'https?://[^"\'<>\s]+\.pdf(?:\?[^"\'<>\s]+)?', page, re.I)
    if not matches:
        return ""
    return f"Đề bài dạng PDF: [Tải file đề bài]({urljoin(page_url, html.unescape(matches[0]))})"


def fetch_statement(
    session: requests.Session,
    base_url: str,
    code: str,
    timeout: int = 45,
) -> dict[str, str]:
    """Fetch exact editor Markdown, with public HTML/PDF fallbacks."""
    edit_url = urljoin(base_url, f"/problem/{code}/edit")
    edit = session.get(edit_url, timeout=timeout, allow_redirects=True)
    if edit.ok and "/login" not in edit.url:
        soup = BeautifulSoup(edit.text, "html.parser")
        name = _field_value(soup, "name").strip() or code
        statement = _field_value(soup, "description").strip()
        if statement:
            return {
                "code": code,
                "name": name,
                "statement": absolute_asset_urls(statement, base_url),
                "link": urljoin(base_url, f"/problem/{code}"),
            }

    public_url = urljoin(base_url, f"/problem/{code}")
    public = session.get(public_url, timeout=timeout, allow_redirects=True)
    if not public.ok:
        raise RuntimeError(f"Không mở được bài {code}: HTTP {public.status_code}.")
    pdf = _pdf_fallback(public.text, public.url)
    if pdf:
        return {
            "code": code,
            "name": code,
            "statement": pdf,
            "link": public_url,
        }
    snapshot = public_problem_snapshot_from_html(public.text, code, base_url)
    snapshot["statement"] = absolute_asset_urls(snapshot["statement"], base_url)
    return snapshot


def one_problem_markdown(problem: dict[str, str]) -> str:
    title = (problem.get("name") or problem["code"]).strip()
    statement = (problem.get("statement") or "").strip()
    return f"{title} | {problem['code']}\n\n{statement}\n"


def combined_markdown(problems: Iterable[dict[str, str]], source_label: str) -> str:
    rows = list(problems)
    lines = ["# Tổng hợp đề bài", "", f"Nguồn: **{source_label}**", ""]
    for index, problem in enumerate(rows, 1):
        title = (problem.get("name") or problem["code"]).strip()
        lines.extend(
            [
                f"## {index}. {title} (`{problem['code']}`)",
                "",
                (problem.get("statement") or "").strip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_export(
    output_dir: Path,
    problems: list[dict[str, str]],
    mode: str,
    site: str,
    source_label: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if mode == "combined":
        path = output_dir / f"tong_hop_de_bai_{site}.md"
        path.write_text(combined_markdown(problems, source_label), encoding="utf-8-sig")
        return path

    path = output_dir / f"de_bai_{site}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for problem in problems:
            archive.writestr(
                f"{problem['code']}.md",
                one_problem_markdown(problem).encode("utf-8-sig"),
            )
    return path


def zip_markdown_names(raw: bytes) -> list[str]:
    """Small inspection helper used by tests."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return archive.namelist()
