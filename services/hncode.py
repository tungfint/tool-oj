"""HNCode parsing and lookup helpers.

Keep HNCode-specific HTML parsing here so UI routes and other features do not
duplicate regexes across the app.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin

import requests


def without_scripts(page: str) -> str:
    page = re.sub(r"<script\b.*?</script>", " ", page, flags=re.S | re.I)
    return re.sub(r"<style\b.*?</style>", " ", page, flags=re.S | re.I)


def strip_html_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<.*?>", " ", value, flags=re.S))).strip()


def input_value(page: str, name: str, default: str = "") -> str:
    match = re.search(
        r'<input\b[^>]*name=["\']' + re.escape(name) + r'["\'][^>]*>',
        page,
        re.S | re.I,
    )
    if not match:
        return default
    value = re.search(r'value=["\']([^"\']*)', match.group(0), re.S | re.I)
    return html.unescape(value.group(1)) if value else default


def selected_option_value(page: str, name: str, default: str = "") -> str:
    match = re.search(r"<select\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>(.*?)</select>", page, re.S)
    if not match:
        return default
    options = list(re.finditer(r"<option\b([^>]*)>(.*?)</option>", match.group(1), re.S))
    for option in options:
        attrs = option.group(1)
        if "selected" in attrs:
            value = re.search(r"value=[\"']([^\"']*)", attrs)
            return html.unescape(value.group(1)) if value else strip_html_text(option.group(2))
    return default


def input_checked(page: str, name: str) -> bool:
    match = re.search(
        r'<input\b[^>]*name=["\']' + re.escape(name) + r'["\'][^>]*>',
        page,
        re.S | re.I,
    )
    return bool(match and re.search(r"\bchecked\b", match.group(0), re.I))


def contest_lesson_score(value: str, default: str = "100") -> str:
    text = strip_html_text(value)
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        return default
    parsed = match.group(0).replace(",", ".")
    try:
        if float(parsed) > 1000:
            return default
    except ValueError:
        return default
    return parsed


def extract_contest_problem_rows_from_html(page: str, contest_key: str = "", default_points: str = "100") -> list[dict]:
    page = without_scripts(page)
    rows: list[dict] = []
    seen: set[str] = set()

    # Ranking pages expose the full contest problem list in table headers. Parse
    # these before normal rows so submission links in the body do not look like
    # a one-problem contest.
    for th_match in re.finditer(r"<th\b([^>]*)\bproblem-score-col\b([^>]*)>(.*?)</th>", page, re.S | re.I):
        th_attrs = th_match.group(1) + " " + th_match.group(2)
        th_html = th_match.group(3)
        code_match = re.search(r'<div\b[^>]*class=["\']problem-code["\'][^>]*>(.*?)</div>', th_html, re.S | re.I)
        href_match = re.search(r'href=["\']/problem/([A-Za-z0-9_-]+)["\']', th_html, re.I)
        code = strip_html_text(code_match.group(1)) if code_match else (html.unescape(href_match.group(1)).strip() if href_match else "")
        if not code or code in seen:
            continue
        seen.add(code)
        title_match = re.search(r'title=["\']([^"\']+)["\']', th_attrs, re.S | re.I)
        title = html.unescape(title_match.group(1)).strip() if title_match else code
        max_match = re.search(r'<div\b[^>]*class=["\']point-denominator["\'][^>]*>(.*?)</div>', th_html, re.S | re.I)
        points = contest_lesson_score(max_match.group(1), default_points) if max_match else default_points
        rows.append({"code": code, "title": title, "points": points, "order": len(rows) + 1})

    if rows:
        return rows

    if contest_key:
        href_re = r'(?:/problem/|/contest/' + re.escape(contest_key) + r'/problems/)([A-Za-z0-9_-]+)'
    else:
        href_re = r'/problem/([A-Za-z0-9_-]+)'

    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", page, re.S | re.I):
        link_match = re.search(r'<a\b[^>]*href=["\']' + href_re + r'(?:/[^"\']*)?["\'][^>]*>(.*?)</a>', row_html, re.S | re.I)
        if not link_match:
            continue
        code = html.unescape(link_match.group(1)).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        title = strip_html_text(link_match.group(2)) or code
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, re.S | re.I)
        points = contest_lesson_score(cells[-1], default_points) if cells else default_points
        rows.append({"code": code, "title": title, "points": points, "order": len(rows) + 1})
    return rows


def extract_problem_link_rows_from_html(page: str, default_points: str = "") -> list[dict]:
    page = without_scripts(page)
    rows: list[dict] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a\b[^>]*href=["\']/problem/([A-Za-z0-9_-]+)(?:/[^"\']*)?["\'][^>]*>(.*?)</a>', page, re.S | re.I):
        code = html.unescape(match.group(1)).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        title = strip_html_text(match.group(2)) or code
        rows.append({"code": code, "title": title, "points": default_points, "order": len(rows) + 1})
    return rows


def list_contest_problems(
    session: requests.Session,
    base_url: str,
    contest_key: str,
    default_points: str = "100",
    timeout: int = 30,
) -> list[dict]:
    best_rows: list[dict] = []
    for path in (
        f"/contest/{contest_key}/ranking/",
        f"/contest/{contest_key}/problems",
        f"/contest/{contest_key}",
    ):
        page = session.get(urljoin(base_url, path), timeout=timeout)
        if not page.ok:
            continue
        rows = extract_contest_problem_rows_from_html(page.text, contest_key, default_points)
        if len(rows) > len(best_rows):
            best_rows = rows
    return best_rows


def find_problem_admin_id(session: requests.Session, base_url: str, code: str, timeout: int = 30) -> str | None:
    page = session.get(urljoin(base_url, "/admin/judge/problem/"), params={"q": code}, timeout=timeout)
    if not page.ok:
        return None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page.text, re.S):
        code_match = re.search(r'<th class="field-code">\s*<a href="/admin/judge/problem/(\d+)/change/[^"]*">\s*([^<]+)\s*</a>', row)
        if code_match and html.unescape(code_match.group(2)).strip() == code:
            return code_match.group(1)
    return None


def find_problem_code_name_by_id(session: requests.Session, base_url: str, problem_id: str, timeout: int = 30) -> tuple[str, str]:
    page = session.get(urljoin(base_url, f"/admin/judge/problem/{problem_id}/change/"), timeout=timeout)
    if not page.ok:
        return "", ""
    return input_value(page.text, "code", ""), input_value(page.text, "name", "")


def lesson_problem_rows_from_page(page: str, lesson_id: str) -> list[dict]:
    prefix = f"problems_{lesson_id}"
    total = int(input_value(page, f"{prefix}-TOTAL_FORMS", "0") or "0")
    rows: list[dict] = []
    for index in range(total):
        problem_id = selected_option_value(page, f"{prefix}-{index}-problem", "") or input_value(page, f"{prefix}-{index}-problem", "")
        if not problem_id:
            continue
        rows.append(
            {
                "id": input_value(page, f"{prefix}-{index}-id", ""),
                "lesson": input_value(page, f"{prefix}-{index}-lesson", ""),
                "problem": problem_id,
                "score": input_value(page, f"{prefix}-{index}-score", "100"),
                "order": input_value(page, f"{prefix}-{index}-order", str(index)),
                "delete": input_checked(page, f"{prefix}-{index}-DELETE"),
            }
        )
    return rows


def list_lesson_problems(
    session: requests.Session,
    base_url: str,
    course_slug: str,
    lesson_id: str,
    timeout: int = 30,
) -> list[dict]:
    lesson_url = urljoin(base_url, f"/course/{course_slug}/lesson/{lesson_id}")
    page = session.get(lesson_url, timeout=timeout)
    if page.ok:
        rows = extract_problem_link_rows_from_html(page.text, "")
        if rows:
            return rows

    edit_url = urljoin(base_url, f"/course/{course_slug}/edit_lessons_new/{lesson_id}")
    edit_page = session.get(edit_url, timeout=timeout)
    if not edit_page.ok:
        return []
    rows: list[dict] = []
    for item in lesson_problem_rows_from_page(edit_page.text, lesson_id):
        problem_id = str(item.get("problem") or "")
        if not problem_id:
            continue
        code, name = find_problem_code_name_by_id(session, base_url, problem_id, timeout=timeout)
        if not code:
            continue
        rows.append(
            {
                "code": code,
                "title": name or code,
                "points": item.get("score") or "",
                "order": len(rows) + 1,
            }
        )
    return rows
