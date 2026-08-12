"""TinHocTre-specific helpers.

This module intentionally keeps only deterministic helpers and thin cookie
utilities. Live browser/session orchestration remains in ``web_app.py`` so the
current UI/API behavior does not change.
"""

from __future__ import annotations

import html
import re
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urljoin

from upload_tinhoctre_batch import clean_statement, statement_body_text


BASE_URL = "https://tinhoctre.vn"
ADMIN_PROBLEM_ADD_PATH = "/admin/judge/problem/add/"


def admin_problem_add_url(base_url: str = BASE_URL) -> str:
    return urljoin(base_url, ADMIN_PROBLEM_ADD_PATH)


def problem_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}")


def problem_edit_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}/edit")


def test_data_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}/test_data")


def statement_for_tinhoctre(statement: str, *, skip_title_line: bool = False) -> str:
    text = statement_body_text(statement, skip_title_line=skip_title_line) if skip_title_line else clean_statement(statement)
    return text.replace("$", "~")


def is_problem_add_form(page: str) -> bool:
    return bool(
        re.search(r"<input\b[^>]*name=[\"']code[\"']", page, re.S)
        and re.search(r"<textarea\b[^>]*name=[\"']description[\"']", page, re.S)
    )


def is_waf_challenge_response(response) -> bool:
    status_code = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {}) or {}
    text = getattr(response, "text", "") or ""
    if status_code == 202:
        return True
    if headers.get("x-amzn-waf-action") or headers.get("X-Amzn-Waf-Action"):
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in ("aws-waf-token", "cf_clearance", "cloudflare", "challenge"))


def is_login_redirect(response) -> bool:
    url = getattr(response, "url", "") or ""
    text = getattr(response, "text", "") or ""
    return "/accounts/login" in url or "/admin/login" in url or "/accounts/login" in text or "/admin/login" in text


def admin_cookie_error(final_url: str = "") -> str:
    suffix = f" URL hiện tại: {final_url}" if final_url else ""
    return (
        "Cookie TinHocTre chưa vào được form admin tạo bài. "
        "Có thể bạn copy cookie khi chưa đăng nhập admin, cookie đã hết hạn, hoặc tài khoản không có quyền staff/admin. "
        "Hãy mở https://tinhoctre.vn/admin/judge/problem/add/ trên cùng trình duyệt, đảm bảo thấy form tạo bài, "
        "rồi copy lại Request Header Cookie và dán vào tab Tài khoản."
        + suffix
    )


def cookie_file(runtime_root: Path) -> Path:
    return runtime_root / "tinhoctre_cookie.txt"


def save_cookie(runtime_root: Path, cookie_header: str) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    cookie_file(runtime_root).write_text(cookie_header, encoding="utf-8")


def load_cookie(runtime_root: Path) -> str:
    path = cookie_file(runtime_root)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def apply_cookie_header(session, cookie_header: str):
    parsed = SimpleCookie()
    parsed.load(cookie_header)
    for key, morsel in parsed.items():
        session.cookies.set(key, morsel.value, domain=".tinhoctre.vn")
        session.cookies.set(key, morsel.value, domain="tinhoctre.vn")
    return session


def strip_html_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<.*?>", " ", value, flags=re.S))).strip()


def parse_form_errors(page: str) -> list[str]:
    errors: list[str] = []
    patterns = [
        r"<ul\b[^>]*class=[\"'][^\"']*\berrorlist\b[^\"']*[\"'][^>]*>(.*?)</ul>",
        r"<p\b[^>]*class=[\"'][^\"']*\berrornote\b[^\"']*[\"'][^>]*>(.*?)</p>",
        r"<div\b[^>]*class=[\"'][^\"']*\b(?:error|errors|alert-danger|alert-error)\b[^\"']*[\"'][^>]*>(.*?)</div>",
    ]
    for pattern in patterns:
        for block in re.findall(pattern, page, re.S | re.I):
            text = strip_html_text(block)
            if text and text not in errors:
                errors.append(text)
    return errors
