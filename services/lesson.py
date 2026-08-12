"""Lesson helper functions shared by Flask routes and tests."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

from . import hncode


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


def parse_lesson_problem_rows(page: str, lesson_id: str) -> list[dict]:
    prefix = f"problems_{lesson_id}"
    total = int(hncode.input_value(page, f"{prefix}-TOTAL_FORMS", "0") or "0")
    rows: list[dict] = []
    for index in range(total):
        problem_id = hncode.selected_option_value(page, f"{prefix}-{index}-problem", "") or hncode.input_value(page, f"{prefix}-{index}-problem", "")
        if not problem_id:
            continue
        rows.append(
            {
                "id": hncode.input_value(page, f"{prefix}-{index}-id", ""),
                "lesson": hncode.input_value(page, f"{prefix}-{index}-lesson", ""),
                "problem": problem_id,
                "score": hncode.input_value(page, f"{prefix}-{index}-score", "100"),
                "order": hncode.input_value(page, f"{prefix}-{index}-order", str(index)),
                "delete": hncode.input_checked(page, f"{prefix}-{index}-DELETE"),
            }
        )
    return rows


def append_lesson_problem_formset(data: list[tuple[str, str]], lesson_id: str, rows: list[dict], initial_forms: int) -> list[tuple[str, str]]:
    prefix = f"problems_{lesson_id}"
    out = list(data)
    out.extend(
        [
            (f"{prefix}-TOTAL_FORMS", str(len(rows))),
            (f"{prefix}-INITIAL_FORMS", str(initial_forms)),
            (f"{prefix}-MIN_NUM_FORMS", "0"),
            (f"{prefix}-MAX_NUM_FORMS", "1000"),
        ]
    )
    for index, row in enumerate(rows):
        out.extend(
            [
                (f"{prefix}-{index}-order", str(row.get("order", index))),
                (f"{prefix}-{index}-lesson", str(row.get("lesson", ""))),
                (f"{prefix}-{index}-id", str(row.get("id", ""))),
                (f"{prefix}-{index}-problem", str(row.get("problem", ""))),
                (f"{prefix}-{index}-score", str(row.get("score", "100") or "100")),
            ]
        )
        if row.get("delete"):
            out.append((f"{prefix}-{index}-DELETE", "on"))
    return out


def remove_lesson_item_fields(data: list[tuple[str, str]], lesson_id: str) -> list[tuple[str, str]]:
    prefixes = (f"problems_{lesson_id}-", f"quizzes_{lesson_id}-")
    return [(name, value) for name, value in data if not any(name.startswith(prefix) for prefix in prefixes)]


def build_contest_to_lesson_rows(
    contest_rows: list[dict],
    *,
    source: str,
    existing_problem_ids: set[str],
    normalize_problem_code,
    admin_problem_id,
) -> list[dict]:
    rows: list[dict] = []
    for item in contest_rows:
        source_code = item["code"]
        dest_code = normalize_problem_code(source_code, "hncode")
        problem_id = admin_problem_id(dest_code)
        if not problem_id:
            status_text = "Thiếu trên HNCode, sẽ chuyển khi xác nhận" if source == "hnoj" else "✗ Không tìm thấy bài trong admin HNCode"
            selected = source == "hnoj"
        elif problem_id in existing_problem_ids:
            status_text = "Đã có trong lesson"
            selected = False
        else:
            status_text = "✓ Sẵn sàng"
            selected = True
        rows.append(
            {
                "index": item.get("order") or len(rows) + 1,
                "source_code": source_code,
                "code": dest_code,
                "title": item.get("title") or source_code,
                "score": item.get("points") or "100",
                "problem_id": problem_id or "",
                "selected": selected,
                "status": status_text,
            }
        )
    return rows


def merge_requested_lesson_copy_rows(saved_rows: list[dict], requested_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    rows_by_code = {row["code"]: row for row in saved_rows}
    result_rows: list[dict] = []
    selected_refs: list[dict] = []
    for requested in requested_rows:
        code = requested.get("code", "")
        base = dict(rows_by_code.get(code, requested))
        base["selected"] = bool(requested.get("selected"))
        base["score"] = str(requested.get("score") or base.get("score") or "100")
        if not base["selected"]:
            base["status"] = "Bỏ qua"
        elif "Đã có" in str(rows_by_code.get(code, {}).get("status", "")):
            base["status"] = "Đã có trong lesson"
        elif base.get("problem_id"):
            base["status"] = "Đang thêm..."
            selected_refs.append(base)
        else:
            base["status"] = "Cần chuyển/tìm problem_id"
        result_rows.append(base)
    return result_rows, selected_refs
