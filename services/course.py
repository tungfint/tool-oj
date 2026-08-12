"""Course helper functions shared by Flask routes and tests."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin


def extract_course_slug(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise RuntimeError("Chưa nhập URL hoặc mã course HNCode.")
    match = re.search(r"/course/([^/?#\s]+)", value)
    if match:
        return html.unescape(match.group(1)).strip("/")
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return value
    raise RuntimeError("Không đọc được mã course. Hãy nhập URL dạng https://hncode.edu.vn/course/<ma_course>.")


def course_page_url(base_url: str, course_slug: str, path: str = "") -> str:
    return urljoin(base_url, f"/course/{course_slug}{path}")


def default_clone_contest_key(source_key: str, dest_slug: str, suffix: str = "") -> str:
    suffix = (suffix or "").strip()
    if not suffix:
        suffix = "_" + dest_slug
    if not suffix.startswith("_") and not suffix.startswith("-"):
        suffix = "_" + suffix
    raw = f"{source_key}{suffix}".lower()
    raw = re.sub(r"[^a-z0-9_-]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_-")
    return raw or source_key
