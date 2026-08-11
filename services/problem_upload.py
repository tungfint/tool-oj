"""Shared HNCode/HNOJ problem upload helpers."""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import urljoin

from transfer_tinhoctre_to_hncode import destination_problem_exists
from upload_hncode_batch import test_cases_from_files
from upload_tinhoctre_batch import GeneratedTests, ProblemBundle, clean_statement, csrf_token, form_errors, read_text_smart, statement_body_text


def language_ids_for_target(target_info: dict, names: list[str]) -> list[str]:
    mapping = target_info["languages"]
    return [mapping[name] for name in names if mapping.get(name)]


def memory_limit_to_kb(value: object) -> str:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return "1048576"
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(kb|k|mb|m|gb|g)?", text)
    if not match:
        return str(value)
    amount = float(match.group(1))
    unit = match.group(2) or "kb"
    if unit in {"gb", "g"}:
        amount *= 1024 * 1024
    elif unit in {"mb", "m"}:
        amount *= 1024
    return str(int(round(amount)))


def normalize_problem_code_for_target(code: str, target: str) -> str:
    code = (code or "").strip().lower()
    if target == "hncode":
        code = re.sub(r"[^a-z0-9_]+", "", code)
    return code


def validate_problem_code_for_target(code: str, target: str) -> None:
    if target == "hncode" and not re.fullmatch(r"[a-z0-9_]+", code or ""):
        normalized = normalize_problem_code_for_target(code, target)
        hint = f" Gợi ý mã hợp lệ: {normalized}" if normalized else ""
        raise RuntimeError(f"HNCode cho phép mã bài gồm chữ thường, số và dấu gạch dưới (^[a-z0-9_]+$).{hint}")


def problem_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}")


def test_data_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}/test_data")


def statement_for_target(target: str, statement: str, *, skip_title_line: bool = False) -> str:
    text = statement_body_text(statement, skip_title_line=skip_title_line) if skip_title_line else clean_statement(statement)
    if target == "hncode":
        return text.replace("~", "$")
    return text.replace("$", "~")


def problem_exists_for_target(session, target: str, base_url: str, code: str) -> bool:
    for path in (f"/problem/{code}/edit", f"/problem/{code}/test_data"):
        try:
            page = session.get(urljoin(base_url, path), timeout=30, allow_redirects=True)
        except Exception:
            continue
        if page.status_code == 200 and "/accounts/login" not in page.url and "/admin/login" not in page.url:
            return True
    return destination_problem_exists(session, base_url, code)


def resolve_problem_code_for_upload(session, target: str, base_url: str, raw_code: str) -> tuple[str, str]:
    code = (raw_code or "").strip().lower()
    if target != "hncode":
        return code, ""
    normalized = normalize_problem_code_for_target(code, target)
    if code and code != normalized and problem_exists_for_target(session, target, base_url, code):
        return code, ""
    validate_problem_code_for_target(normalized, target)
    if code != normalized:
        return normalized, f"{code}: mã HNCode dùng để tạo mới được đổi thành {normalized}"
    return code, ""


def upload_tests_for_target(session, target: str, base_url: str, code: str, tests: GeneratedTests, upload_hncode_tests, upload_hnoj_tests) -> None:
    if target == "hnoj":
        upload_hnoj_tests(session, base_url, code, tests)
        return
    upload_hncode_tests(session, base_url, code, tests.zip_path, test_cases_from_files(tests.input_files, tests.output_files))


def language_id_from_submit_page(page: str, preferred_languages: list[str]) -> str:
    select_match = re.search(r"<select\b[^>]*name=[\"']language[\"'][^>]*>(.*?)</select>", page, re.S | re.I)
    haystack = select_match.group(1) if select_match else page
    options: list[tuple[str, str]] = []
    for match in re.finditer(r"<option\b([^>]*)>(.*?)</option>", haystack, re.S | re.I):
        attrs, label_html = match.groups()
        value_match = re.search(r"value=[\"']([^\"']+)", attrs)
        if not value_match:
            continue
        label = html.unescape(re.sub(r"<.*?>", " ", label_html)).strip()
        options.append((html.unescape(value_match.group(1)), label))
    for preferred in preferred_languages:
        wanted = normalize_language_label(preferred)
        for value, label in options:
            if wanted and wanted in normalize_language_label(label):
                return value
    return ""


def normalize_language_label(label: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", "", label.lower())


def submit_solution_file(session, base_url: str, code: str, source_path: Path, preferred_languages: list[str], compact_form_red_errors) -> str:
    submit_url = urljoin(base_url, f"/problem/{code}/submit")
    page = session.get(submit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Submit page failed: HTTP {page.status_code}")
    language_id = language_id_from_submit_page(page.text, preferred_languages)
    if not language_id:
        raise RuntimeError("không tìm thấy ngôn ngữ phù hợp trên trang submit")
    result = session.post(
        submit_url,
        data={
            "csrfmiddlewaretoken": csrf_token(page.text),
            "source": source_path.read_text(encoding="utf-8", errors="replace"),
            "language": language_id,
            "judge": "",
        },
        headers={"Referer": submit_url},
        allow_redirects=True,
        timeout=30,
    )
    if not result.ok:
        raise RuntimeError(f"Submit failed: HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Submit form báo lỗi: " + "; ".join(errors))
    if "/submission/" not in result.url:
        raise RuntimeError(f"Submit chưa tạo submission; URL sau POST: {result.url}")
    return result.url


def submit_if_requested(session, base_url: str, bundle: ProblemBundle, settings: dict, log_lines: list[str], compact_form_red_errors, fallback_submit_solution=None) -> None:
    if settings.get("no_submit"):
        log_lines.append(f"{bundle.code}: không nộp bài chấm thử theo lựa chọn.")
        return
    if settings.get("submit_cpp"):
        if bundle.solution_cpp:
            try:
                submission = submit_solution_file(session, base_url, bundle.code, bundle.solution_cpp, ["C++17", "GNU C++17", "C++20", "GNU C++20", "C++"], compact_form_red_errors)
                log_lines.append(f"{bundle.code}: đã nộp thử C++ {submission}.")
            except Exception as exc:
                log_lines.append(f"{bundle.code}: không nộp thử C++ được: {exc}")
        else:
            log_lines.append(f"{bundle.code}: không có sol C++, bỏ qua nộp thử C++.")
    if settings.get("submit_python"):
        if bundle.solution:
            try:
                submission = submit_solution_file(session, base_url, bundle.code, bundle.solution, ["PyPy 3", "Pypy 3", "Python 3", "Python3", "Python"], compact_form_red_errors)
                log_lines.append(f"{bundle.code}: đã nộp thử Python {submission}.")
            except Exception as first_exc:
                if fallback_submit_solution is None:
                    log_lines.append(f"{bundle.code}: không nộp thử Python được: {first_exc}")
                else:
                    try:
                        submission = fallback_submit_solution(session, base_url, bundle, language_id="17", poll_seconds=0)
                        log_lines.append(f"{bundle.code}: đã nộp thử Python {submission}.")
                    except Exception as exc:
                        log_lines.append(f"{bundle.code}: không nộp thử Python được: {first_exc}; fallback cũng lỗi: {exc}")
        else:
            log_lines.append(f"{bundle.code}: không có sol Python, bỏ qua nộp thử Python.")
