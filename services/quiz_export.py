"""Export a Quiz and its questions from DMOJ-compatible admin pages."""

from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from services import problem_export


QUIZ_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
TYPE_LABELS = {
    "MC": "Trắc nghiệm 1 đáp án",
    "MA": "Trắc nghiệm nhiều đáp án",
    "SA": "Trả lời ngắn",
    "FB": "Điền vào chỗ trống",
    "TF": "Đúng / Sai",
}


def quiz_code(value: str) -> str:
    text = html.unescape(str(value or "")).strip()
    match = re.search(r"/quiz/([^/?#\s]+)", text, re.I)
    code = (match.group(1) if match else text).strip().strip("/")
    if not QUIZ_CODE_PATTERN.fullmatch(code):
        raise ValueError("Không đọc được mã Quiz từ dữ liệu nhập.")
    return code


def _input_value(page: str, name: str, default: str = "") -> str:
    match = re.search(
        r"<input\b[^>]*\bname=[\"']" + re.escape(name) + r"[\"'][^>]*>",
        page,
        re.I | re.S,
    )
    if not match:
        return default
    value = re.search(r"\bvalue=[\"']([^\"']*)[\"']", match.group(0), re.I | re.S)
    return html.unescape(value.group(1)) if value else default


def _textarea_value(page: str, name: str, default: str = "") -> str:
    match = re.search(
        r"<textarea\b[^>]*\bname=[\"']"
        + re.escape(name)
        + r"[\"'][^>]*>(.*?)</textarea>",
        page,
        re.I | re.S,
    )
    return html.unescape(match.group(1)).strip() if match else default


def _selected_value(page: str, name: str, default: str = "") -> str:
    match = re.search(
        r"<select\b[^>]*\bname=[\"']"
        + re.escape(name)
        + r"[\"'][^>]*>(.*?)</select>",
        page,
        re.I | re.S,
    )
    if not match:
        return default
    for option in re.finditer(r"<option\b([^>]*)>(.*?)</option>", match.group(1), re.I | re.S):
        if re.search(r"\bselected(?:\s*=|\s|$)", option.group(1), re.I):
            value = re.search(r"\bvalue=[\"']([^\"']*)[\"']", option.group(1), re.I | re.S)
            return html.unescape(value.group(1)) if value else default
    return default


def _checked(page: str, name: str) -> bool:
    match = re.search(
        r"<input\b[^>]*\bname=[\"']" + re.escape(name) + r"[\"'][^>]*>",
        page,
        re.I | re.S,
    )
    return bool(match and re.search(r"\bchecked\b", match.group(0), re.I))


def _json_value(raw: str, field: str, *, allow_empty: bool = False) -> Any:
    text = (raw or "").strip()
    if not text and allow_empty:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON trường {field} không hợp lệ: {exc.msg}.") from exc


def find_quiz_admin_url(
    session: requests.Session, base_url: str, code: str, timeout: int = 45
) -> str:
    list_url = urljoin(base_url, "/admin/judge/quiz/")
    response = session.get(list_url, params={"q": code}, timeout=timeout, allow_redirects=True)
    if not response.ok:
        raise RuntimeError(f"Không mở được danh sách Quiz: HTTP {response.status_code}.")
    if "/login" in response.url:
        raise RuntimeError("Phiên đăng nhập đã hết hạn hoặc tài khoản không có quyền đọc Quiz.")
    candidates: list[str] = []
    for match in re.finditer(
        r"href=[\"']([^\"']*/admin/judge/quiz/\d+/change/[^\"']*)[\"']",
        response.text,
        re.I,
    ):
        url = urljoin(response.url, html.unescape(match.group(1)))
        if url not in candidates:
            candidates.append(url)
    for url in candidates:
        page = session.get(url, timeout=timeout, allow_redirects=True)
        if page.ok and _input_value(page.text, "code") == code:
            return url
    raise RuntimeError(f"Không tìm thấy Quiz có mã {code} trong trang quản trị.")


def parse_quiz_admin_form(page: str, base_url: str, code: str = "") -> dict[str, Any]:
    actual_code = _input_value(page, "code", code).strip() or code
    total_raw = _input_value(page, "quiz_questions-TOTAL_FORMS", "0")
    try:
        total = int(total_raw)
    except ValueError:
        total = 0
    assignments: list[dict[str, Any]] = []
    for form_index in range(total):
        prefix = f"quiz_questions-{form_index}"
        question_id = _selected_value(page, f"{prefix}-question").strip()
        if not question_id.isdigit() or _checked(page, f"{prefix}-DELETE"):
            continue
        order_raw = _input_value(page, f"{prefix}-order", str(form_index))
        try:
            order: int | str = int(order_raw)
        except ValueError:
            order = order_raw
        assignments.append(
            {
                "question_id": int(question_id),
                "points": _input_value(page, f"{prefix}-points", ""),
                "order": order,
                "form_index": form_index,
            }
        )
    assignments.sort(
        key=lambda row: (
            row["order"] if isinstance(row["order"], int) else 10**9,
            row["form_index"],
        )
    )
    return {
        "code": actual_code,
        "title": _input_value(page, "title", actual_code).strip() or actual_code,
        "description": problem_export.absolute_asset_urls(
            _textarea_value(page, "description", ""), base_url
        ),
        "time_limit": _input_value(page, "time_limit", ""),
        "is_public": _checked(page, "is_public"),
        "shuffle_questions": _checked(page, "shuffle_questions"),
        "assignments": assignments,
    }


def parse_question_admin_form(
    page: str,
    question_id: int,
    base_url: str,
    assignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    question_type = _selected_value(page, "question_type").strip().upper()
    if question_type not in TYPE_LABELS:
        raise RuntimeError(f"Câu {question_id}: loại câu hỏi không được hỗ trợ: {question_type!r}.")
    content = _textarea_value(page, "content", "")
    if not content.strip():
        raise RuntimeError(f"Câu {question_id}: thiếu nội dung.")
    choices = _json_value(_textarea_value(page, "choices", ""), "choices", allow_empty=True)
    correct_answers = _json_value(
        _textarea_value(page, "correct_answers", ""), "correct_answers", allow_empty=True
    )
    result = {
        "question_id": question_id,
        "type": question_type,
        "title": _input_value(page, "title", f"Câu hỏi {question_id}").strip()
        or f"Câu hỏi {question_id}",
        "content": problem_export.absolute_asset_urls(content, base_url),
        "choices": choices,
        "correct_answers": correct_answers,
        "explanation": problem_export.absolute_asset_urls(
            _textarea_value(page, "explanation", ""), base_url
        ),
        "grading_strategy": _selected_value(page, "grading_strategy", "all_or_nothing"),
        "shuffle_choices": _checked(page, "shuffle_choices"),
        "tags": _input_value(page, "tags", ""),
        "is_public": _checked(page, "is_public"),
        "link": urljoin(base_url, f"/quiz/questions/{question_id}/"),
    }
    if assignment:
        result.update(
            {
                "points": assignment.get("points", ""),
                "order": assignment.get("order", ""),
            }
        )
    if question_type in {"MC", "MA", "TF"}:
        if not isinstance(choices, list) or len(choices) < 2:
            raise RuntimeError(f"Câu {question_id}: loại {question_type} thiếu lựa chọn hợp lệ.")
        if not isinstance(correct_answers, dict) or correct_answers.get("answers") is None or correct_answers.get("answers") == "":
            raise RuntimeError(f"Câu {question_id}: thiếu đáp án đúng.")
    elif question_type == "SA":
        if not isinstance(correct_answers, dict) or not correct_answers.get("answers"):
            raise RuntimeError(f"Câu {question_id}: thiếu đáp án trả lời ngắn.")
    elif question_type == "FB":
        if not isinstance(correct_answers, dict) or not correct_answers.get("blanks"):
            raise RuntimeError(f"Câu {question_id}: thiếu cấu trúc đáp án chỗ trống.")
    return result


def _clone_session(session: requests.Session) -> requests.Session:
    clone = requests.Session()
    clone.headers.update(session.headers)
    clone.cookies.update(session.cookies)
    return clone


def fetch_quiz(
    session: requests.Session,
    base_url: str,
    source: str,
    *,
    timeout: int = 45,
    workers: int = 6,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    code = quiz_code(source)
    admin_url = find_quiz_admin_url(session, base_url, code, timeout)
    page = session.get(admin_url, timeout=timeout, allow_redirects=True)
    if not page.ok:
        raise RuntimeError(f"Không mở được form Quiz {code}: HTTP {page.status_code}.")
    quiz = parse_quiz_admin_form(page.text, base_url, code)
    quiz.update(
        {
            "admin_url": admin_url,
            "link": urljoin(base_url, f"/quiz/{code}/"),
        }
    )
    assignments = list(quiz["assignments"])
    if not assignments:
        raise RuntimeError(f"Quiz {code} chưa có câu hỏi nào.")

    def read_question(assignment: dict[str, Any]) -> dict[str, Any]:
        question_id = int(assignment["question_id"])
        question_url = urljoin(
            base_url, f"/admin/judge/quizquestion/{question_id}/change/"
        )
        last_error: Exception | None = None
        local_session = _clone_session(session)
        for attempt in range(3):
            try:
                response = local_session.get(
                    question_url, timeout=timeout + attempt * 15, allow_redirects=True
                )
                if not response.ok:
                    raise RuntimeError(f"HTTP {response.status_code}")
                if "/login" in response.url:
                    raise RuntimeError("phiên đăng nhập đã hết hạn")
                return parse_question_admin_form(
                    response.text, question_id, base_url, assignment
                )
            except Exception as exc:  # pragma: no cover - retries depend on network
                last_error = exc
        raise RuntimeError(f"Câu {question_id}: không đọc được form ({last_error}).")

    questions_by_id: dict[int, dict[str, Any]] = {}
    errors_by_id: dict[int, str] = {}
    max_workers = max(1, min(int(workers or 1), 8, len(assignments)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(read_question, assignment): int(assignment["question_id"])
            for assignment in assignments
        }
        for future in as_completed(future_map):
            question_id = future_map[future]
            try:
                questions_by_id[question_id] = future.result()
            except Exception as exc:
                errors_by_id[question_id] = str(exc)

    rows: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for index, assignment in enumerate(assignments, 1):
        question_id = int(assignment["question_id"])
        question = questions_by_id.get(question_id)
        if question:
            question["index"] = index
            questions.append(question)
            rows.append(
                {
                    "index": index,
                    "question_id": question_id,
                    "title": question["title"],
                    "type": question["type"],
                    "points": question.get("points", ""),
                    "status": "✓ Đã đọc",
                    "link": question["link"],
                    "error": "",
                }
            )
        else:
            rows.append(
                {
                    "index": index,
                    "question_id": question_id,
                    "title": f"Câu hỏi {question_id}",
                    "type": "",
                    "points": assignment.get("points", ""),
                    "status": "✗ Lỗi",
                    "link": urljoin(base_url, f"/quiz/questions/{question_id}/"),
                    "error": errors_by_id.get(question_id, "Không đọc được câu hỏi."),
                }
            )
    if not questions:
        raise RuntimeError("Không đọc được câu hỏi nào trong Quiz.")
    quiz["questions"] = questions
    return quiz, rows


def _answer_lines(question: dict[str, Any]) -> list[str]:
    qtype = question["type"]
    correct = question.get("correct_answers")
    if not isinstance(correct, dict):
        return []
    if qtype == "FB":
        lines: list[str] = []
        for index, blank in enumerate(correct.get("blanks") or [], 1):
            if not isinstance(blank, dict):
                continue
            label = str(blank.get("label") or f"Ô {index}").strip().rstrip(":")
            values = blank.get("answers") or []
            if not isinstance(values, list):
                values = [values]
            lines.append(f"- {label}: " + " | ".join(str(value) for value in values))
        return lines
    answers = correct.get("answers", correct.get("answer", []))
    if not isinstance(answers, list):
        answers = [answers]
    values = [str(value).strip() for value in answers if str(value).strip()]
    if qtype in {"MC", "MA", "TF"}:
        return [", ".join(values)] if values else []
    return [f"- {value}" for value in values]


def question_markdown(question: dict[str, Any]) -> str:
    lines = [
        f"Loại: {question['type']}",
        f"Tiêu đề: {question['title']}",
        "Nội dung:",
        problem_export.canonical_markdown_math(str(question.get("content") or "")).strip(),
    ]
    choices = question.get("choices")
    if isinstance(choices, list) and choices:
        lines.append("Lựa chọn:")
        for index, choice in enumerate(choices, 1):
            if isinstance(choice, dict):
                choice_id = str(choice.get("id", choice.get("value", index)))
                choice_text = str(choice.get("text", choice.get("label", "")))
            else:
                choice_id, choice_text = str(index), str(choice)
            lines.append(f"- {choice_id}. {choice_text}")
    lines.append("Đáp án:")
    lines.extend(_answer_lines(question))
    explanation = problem_export.canonical_markdown_math(
        str(question.get("explanation") or "")
    ).strip()
    if explanation:
        lines.extend(["Giải thích:", explanation])
    return "\n".join(lines).rstrip()


def quiz_markdown(quiz: dict[str, Any]) -> str:
    return "\n---\n".join(question_markdown(item) for item in quiz["questions"]) + "\n"


def _readable_answer(question: dict[str, Any]) -> str:
    lines = _answer_lines(question)
    value = "; ".join(line.removeprefix("- ") for line in lines)
    choices = question.get("choices")
    if question.get("type") in {"MC", "MA", "TF"} and isinstance(choices, list):
        mapping = {
            str(choice.get("id", choice.get("value", index))): str(
                choice.get("text", choice.get("label", ""))
            )
            for index, choice in enumerate(choices, 1)
            if isinstance(choice, dict)
        }
        ids = [part.strip() for part in value.split(",") if part.strip()]
        expanded = [f"{item}. {mapping[item]}" if item in mapping else item for item in ids]
        return "; ".join(expanded)
    return value


def quiz_pdf_markdown(quiz: dict[str, Any], include_answers: bool = True) -> str:
    def pdf_math(value: str) -> str:
        text = problem_export.canonical_markdown_math(value)
        text = re.sub(r"\$\$(.+?)\$\$", r"\1", text, flags=re.S)
        text = re.sub(r"(?<!\\)\$([^$\r\n]+)(?<!\\)\$", r"\1", text)
        replacements = {
            r"\times": "×",
            r"\cdot": "·",
            r"\leq": "≤",
            r"\le": "≤",
            r"\geq": "≥",
            r"\ge": "≥",
            r"\neq": "≠",
            r"\ldots": "…",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        text = re.sub(r"\\(?:text|mathrm|mathbf)\{([^{}]*)\}", r"\1", text)
        return text

    lines: list[str] = []
    description = pdf_math(str(quiz.get("description") or "")).strip()
    plain_description = re.sub(r"\s+", " ", re.sub(r"[*_`#]", "", description)).strip()
    plain_title = re.sub(r"\s+", " ", str(quiz.get("title") or "")).strip()
    if description and plain_description != plain_title:
        lines.extend([description, ""])
    for index, question in enumerate(quiz["questions"], 1):
        points = str(question.get("points") or "").strip()
        suffix = f" ({points} điểm)" if points else ""
        lines.extend(
            [
                f"## Câu {index}. {question['title']}{suffix}",
                "",
                pdf_math(str(question.get("content") or "")).strip(),
            ]
        )
        choices = question.get("choices")
        if isinstance(choices, list):
            for choice_index, choice in enumerate(choices, 1):
                if isinstance(choice, dict):
                    choice_id = str(choice.get("id", choice.get("value", choice_index)))
                    text = str(choice.get("text", choice.get("label", "")))
                else:
                    choice_id, text = str(choice_index), str(choice)
                lines.append(f"- {choice_id}. {text}")
        lines.append("")
    if include_answers:
        lines.extend(["# Đáp án và giải thích", ""])
        for index, question in enumerate(quiz["questions"], 1):
            answer = _readable_answer(question) or "(Chưa có đáp án)"
            lines.extend([f"## Câu {index}", "", f"**Đáp án:** {answer}"])
            explanation = pdf_math(str(question.get("explanation") or "")).strip()
            if explanation:
                lines.extend(["", "**Giải thích:**", explanation])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_quiz_export(
    output_dir: Path,
    quiz: dict[str, Any],
    output_format: str,
    session: requests.Session | None = None,
    *,
    include_answers: bool = True,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    code = quiz_code(str(quiz.get("code") or "quiz"))
    if output_format == "markdown":
        path = output_dir / f"{code}_quiz.md"
        path.write_text(quiz_markdown(quiz), encoding="utf-8-sig")
        return path
    if output_format != "pdf":
        raise ValueError("Định dạng xuất Quiz không hợp lệ.")
    path = output_dir / f"{code}_quiz.pdf"
    problem_export.render_problem_pdf(
        path,
        {
            "code": code,
            "code_label": "Mã Quiz",
            "name": str(quiz.get("title") or code),
            "statement": quiz_pdf_markdown(quiz, include_answers),
        },
        session,
    )
    return path
