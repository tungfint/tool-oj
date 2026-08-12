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


def strip_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_course_lessons_from_html(page: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    pattern = r'<li\b[^>]*class=["\'][^"\']*\bsortable-item\b[^"\']*["\'][^>]*data-id=["\']?(\d+)["\']?[^>]*>(.*?)</li>'
    for lesson_id, block in re.findall(pattern, page or "", re.S | re.I):
        if lesson_id in seen:
            continue
        seen.add(lesson_id)
        title_match = re.search(
            r'<a\b[^>]*href=["\']/course/[^"\']+/lesson/' + re.escape(lesson_id) + r'["\'][^>]*>(.*?)</a>',
            block,
            re.S | re.I,
        )
        order_match = re.search(
            r'<span\b[^>]*class=["\'][^"\']*\bitem-order\b[^"\']*["\'][^>]*>(.*?)</span>',
            block,
            re.S | re.I,
        )
        points_match = re.search(
            r'<span\b[^>]*class=["\'][^"\']*\bitem-points\b[^"\']*["\'][^>]*>(.*?)</span>',
            block,
            re.S | re.I,
        )
        rows.append(
            {
                "kind": "lesson",
                "key": lesson_id,
                "title": strip_html_text(title_match.group(1)) if title_match else f"Lesson {lesson_id}",
                "order": strip_html_text(order_match.group(1)).rstrip(".") if order_match else str(len(rows) + 1),
                "points": strip_html_text(points_match.group(1)) if points_match else "",
            }
        )
    return rows


def parse_course_contests_from_html(page: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    pattern = r'<li\b[^>]*class=["\'][^"\']*\bsortable-item\b[^"\']*["\'][^>]*>(.*?)</li>'
    for block in re.findall(pattern, page or "", re.S | re.I):
        link_match = re.search(r'<a\b[^>]*href=["\']/contest/([A-Za-z0-9_-]+)["\'][^>]*>(.*?)</a>', block, re.S | re.I)
        if not link_match:
            continue
        key = html.unescape(link_match.group(1)).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        order_match = re.search(
            r'<span\b[^>]*class=["\'][^"\']*\bitem-order\b[^"\']*["\'][^>]*>(.*?)</span>',
            block,
            re.S | re.I,
        )
        points_match = re.search(
            r'<input\b[^>]*class=["\'][^"\']*\binline-points-edit\b[^"\']*["\'][^>]*value=["\']?([^"\'> ]*)',
            block,
            re.S | re.I,
        )
        rows.append(
            {
                "kind": "contest",
                "key": key,
                "title": strip_html_text(link_match.group(2)) or key,
                "order": strip_html_text(order_match.group(1)).rstrip(".") if order_match else str(len(rows) + 1),
                "points": html.unescape(points_match.group(1)) if points_match else "",
            }
        )
    return rows


def build_course_clone_rows(
    source_lessons: list[dict],
    source_contests: list[dict],
    dest_lessons: list[dict],
    dest_contests: list[dict],
    dest_slug: str,
    contest_suffix: str = "",
    contest_exists=None,
) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    log_lines: list[str] = []
    dest_lesson_titles = {row.get("title", "").strip().casefold() for row in dest_lessons}
    dest_contest_keys = {row.get("key", "") for row in dest_contests}

    for item in source_lessons:
        exists = item.get("title", "").strip().casefold() in dest_lesson_titles
        status = "Đã có lesson cùng tên ở đích" if exists else "✓ Sẵn sàng"
        row = {
            **item,
            "selected": not exists,
            "can_clone": not exists,
            "status": status,
            "new_key": "",
        }
        rows.append(row)
        log_lines.append(f"Lesson {item.get('order', '')}. {item.get('title', '')}: {status}")

    for item in source_contests:
        new_key = default_clone_contest_key(item.get("key", ""), dest_slug, contest_suffix)
        in_dest = new_key in dest_contest_keys
        global_exists = False
        if not in_dest and contest_exists is not None:
            try:
                global_exists = bool(contest_exists(new_key))
            except Exception:
                global_exists = False
        if in_dest:
            status = "Đã có contest đích trong course"
        elif global_exists:
            status = "Mã contest đích đã tồn tại trên HNCode"
        else:
            status = "✓ Sẵn sàng"
        can_clone = status.startswith("✓")
        row = {
            **item,
            "selected": can_clone,
            "can_clone": can_clone,
            "status": status,
            "new_key": new_key,
        }
        rows.append(row)
        log_lines.append(f"Contest {item.get('key', '')} → {new_key}: {status}")
    return rows, log_lines


def merge_requested_course_clone_rows(saved_rows: list[dict], requested_rows: list[dict]) -> list[dict]:
    rows_by_id = {(row.get("kind", ""), row.get("key", "")): row for row in saved_rows}
    merged: list[dict] = []
    for requested in requested_rows:
        key = requested.get("key", "")
        kind = requested.get("kind", "")
        base = dict(rows_by_id.get((kind, key), requested))
        base["selected"] = bool(requested.get("selected"))
        if kind == "contest":
            base["new_key"] = (requested.get("new_key") or base.get("new_key") or "").strip()
        merged.append(base)
    return merged
