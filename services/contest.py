"""Contest helper functions shared by Flask routes and tests."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin


def extract_contest_key(value: str, label: str = "contest") -> str:
    value = (value or "").strip()
    if not value:
        raise RuntimeError(f"Chưa nhập URL hoặc mã {label}.")
    match = re.search(r"/contest/([^/?#\s]+)", value)
    if match:
        return html.unescape(match.group(1)).strip("/")
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return value
    raise RuntimeError(f"Không đọc được mã {label}. Hãy nhập URL dạng https://hncode.edu.vn/contest/<ma_contest>.")


def source_from_contest_url(source: str, contest_url_value: str) -> str:
    text = (contest_url_value or "").strip().lower()
    if "hnoj.edu.vn" in text:
        return "hnoj"
    if "hncode.edu.vn" in text or "oj.hncode.edu.vn" in text:
        return "hncode"
    return source if source in {"hncode", "hnoj"} else "hncode"


def contest_url(base_url: str, key: str) -> str:
    return urljoin(base_url, f"/contest/{key}")


def contest_admin_search_url(base_url: str) -> str:
    return urljoin(base_url, "/admin/judge/contest/")


def selected_count(rows: list[dict]) -> int:
    return len([row for row in rows if row.get("selected")])

