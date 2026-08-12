"""Lesson helper functions shared by Flask routes and tests."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin


def extract_lesson_ref(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    match = re.search(r"/course/([^/?#\s]+)/lesson/(\d+)", value)
    if not match:
        match = re.search(r"/course/([^/?#\s]+)/edit_lessons_new/(\d+)", value)
    if not match:
        raise RuntimeError("Không đọc được lesson. Hãy nhập URL dạng https://hncode.edu.vn/course/<course>/lesson/<id>.")
    return html.unescape(match.group(1)), match.group(2)


def lesson_url(base_url: str, course_slug: str, lesson_id: str) -> str:
    return urljoin(base_url, f"/course/{course_slug}/lesson/{lesson_id}")


def lesson_edit_url(base_url: str, course_slug: str, lesson_id: str) -> str:
    return urljoin(base_url, f"/course/{course_slug}/edit_lessons_new/{lesson_id}")

