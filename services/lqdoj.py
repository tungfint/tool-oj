"""LQDOJ-specific authentication, validation, and URL helpers."""

from __future__ import annotations

import html
import re
from http.cookies import SimpleCookie
from urllib.parse import urljoin, urlparse

import requests


BASE_URL = "https://lqdoj.edu.vn"
PROBLEM_CODE_RE = re.compile(r"^[a-z0-9]+$")
CONTEST_KEY_RE = re.compile(r"^[a-z0-9]+$")
COURSE_SLUG_RE = re.compile(r"^[-a-zA-Z0-9]+$")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)


def is_waf_challenge(status_code: int, headers: dict | None = None, text: str = "") -> bool:
    headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    body = (text or "").lower()
    return bool(
        status_code in {202, 403, 429, 503}
        and (
            headers.get("cf-mitigated") == "challenge"
            or "cf-ray" in headers
            or "just a moment" in body
            or "challenge-platform" in body
            or "challenges.cloudflare.com" in body
        )
    )


def waf_error(action: str = "truy cập LQDOJ") -> RuntimeError:
    return RuntimeError(
        f"Cloudflare đang chặn tool khi {action}. Hãy mở LQDOJ bằng Edge trong tab Tài khoản, "
        "đăng nhập admin, bấm Lấy cookie LQDOJ từ Edge rồi thử lại."
    )


def normalize_problem_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())[:30]


def validate_problem_code(value: str) -> None:
    if len(value or "") > 30 or not PROBLEM_CODE_RE.fullmatch(value or ""):
        suggestion = normalize_problem_code(value)
        hint = f" Gợi ý: {suggestion}." if suggestion else ""
        raise RuntimeError(f"LQDOJ yêu cầu mã bài theo ^[a-z0-9]+$, tối đa 30 ký tự.{hint}")


def normalize_contest_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())[:20]


def validate_contest_key(value: str) -> None:
    if len(value or "") > 20 or not CONTEST_KEY_RE.fullmatch(value or ""):
        suggestion = normalize_contest_key(value)
        hint = f" Gợi ý: {suggestion}." if suggestion else ""
        raise RuntimeError(f"LQDOJ yêu cầu mã contest theo ^[a-z0-9]+$.{hint}")


def normalize_course_slug(value: str) -> str:
    text = (value or "").strip().replace("_", "-")
    text = re.sub(r"[^a-zA-Z0-9-]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")[:128]


def validate_course_slug(value: str) -> None:
    if not COURSE_SLUG_RE.fullmatch(value or ""):
        suggestion = normalize_course_slug(value)
        hint = f" Gợi ý: {suggestion}." if suggestion else ""
        raise RuntimeError(f"LQDOJ chỉ cho phép chữ, số và dấu gạch ngang trong mã course.{hint}")


def session_from_cookie(cookie_header: str, *, user_agent: str = "") -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent.strip() or USER_AGENT})
    parsed = SimpleCookie()
    parsed.load(cookie_header or "")
    host = urlparse(BASE_URL).hostname or "lqdoj.edu.vn"
    for key, morsel in parsed.items():
        session.cookies.set(key, morsel.value, domain=host)
        session.cookies.set(key, morsel.value, domain="." + host)
    return session


def _csrf_token(page: str) -> str:
    patterns = (
        r'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)',
        r'value=["\']([^"\']+)["\'][^>]*name=["\']csrfmiddlewaretoken["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.I)
        if match:
            return html.unescape(match.group(1))
    raise RuntimeError("LQDOJ không trả CSRF token đăng nhập.")


def _admin_session_is_valid(session: requests.Session) -> bool:
    response = session.get(urljoin(BASE_URL, "/admin/judge/problem/add/"), timeout=30, allow_redirects=True)
    if is_waf_challenge(response.status_code, response.headers, response.text):
        raise waf_error("kiểm tra phiên admin")
    return bool(
        response.ok
        and "/admin/login/" not in response.url
        and re.search(r'\bname=["\']code["\']', response.text)
    )


def login_admin(username: str, password: str, *, cookie: str = "", user_agent: str = "") -> requests.Session:
    if cookie.strip():
        session = session_from_cookie(cookie, user_agent=user_agent)
        if _admin_session_is_valid(session):
            return session

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent.strip() or USER_AGENT})
    login_url = urljoin(BASE_URL, "/admin/login/?next=/admin/")
    page = session.get(login_url, timeout=30, allow_redirects=True)
    if is_waf_challenge(page.status_code, page.headers, page.text):
        raise waf_error("mở form đăng nhập")
    if not page.ok:
        raise RuntimeError(f"LQDOJ login page lỗi HTTP {page.status_code}.")
    result = session.post(
        login_url,
        data={
            "csrfmiddlewaretoken": _csrf_token(page.text),
            "username": username or "",
            "password": password or "",
            "next": "/admin/",
        },
        headers={"Referer": login_url},
        timeout=30,
        allow_redirects=True,
    )
    if is_waf_challenge(result.status_code, result.headers, result.text):
        raise waf_error("gửi form đăng nhập")
    if not result.ok or "/admin/login/" in result.url or "sessionid" not in session.cookies.get_dict():
        raise RuntimeError("LQDOJ đăng nhập không tạo được phiên admin. Hãy kiểm tra tài khoản hoặc dùng cookie Edge.")
    if not _admin_session_is_valid(session):
        raise RuntimeError("LQDOJ đăng nhập xong nhưng tài khoản không mở được form admin tạo bài.")
    return session


def problem_url(code: str) -> str:
    return urljoin(BASE_URL, f"/problem/{code}")


def contest_url(key: str) -> str:
    return urljoin(BASE_URL, f"/contest/{key}")


def course_url(slug: str) -> str:
    return urljoin(BASE_URL, f"/course/{slug}")
