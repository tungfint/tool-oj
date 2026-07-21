#!/usr/bin/env python3
"""Local web UI for preparing, uploading, and transferring OJ problems."""

from __future__ import annotations

import html
import json
import math
import os
import re
import shutil
import subprocess
import time
import uuid
import zipfile
from collections import Counter, defaultdict
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import urlopen
from http.cookies import SimpleCookie

from flask import Flask, Response, jsonify, render_template_string, request, send_file

from transfer_tinhoctre_to_hncode import (
    ProblemInfo,
    checkbox_checked,
    create_hncode_problem,
    destination_problem_exists,
    fetch_source_problem,
    input_value,
    login_hncode,
    selected_option,
    textarea_value,
    upload_hncode_tests,
)
from upload_tinhoctre_batch import (
    GeneratedTests,
    ProblemBundle,
    clean_statement,
    csrf_token,
    discover_bundles,
    extract_zip,
    form_errors,
    generate_tests,
    login as login_tinhoctre_public,
    problem_exists as tinhoctre_problem_exists,
    session as tinhoctre_session,
    statement_body_text,
    submit_solution,
    upload_tests as upload_tinhoctre_tests,
)


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
DEFAULT_ZIP = r"E:\Google Drive\Google Drive\1-School\4-KiThi\THT\2026\5Tinh\04-06\tht26_5_bai_files.zip"
QUIZ_BASE_URL = "https://oj.hncode.edu.vn"

TARGETS = {
    "hnoj": {
        "label": "HNOJ",
        "base_url": "https://hnoj.edu.vn",
        "type_id": "1",
        "group_id": "1",
        "languages": {"C++17": "4", "Pascal": "7", "Python 3": "9", "Scratch": "12"},
        "default_user": "hncode",
        "test_backend": "dmoj",
    },
    "hncode": {
        "label": "HNCode",
        "base_url": "https://hncode.edu.vn",
        "type_id": "387",
        "group_id": "105",
        "languages": {"C++17": "12", "C++20": "14", "Pascal": "10", "Python 3": "8", "PyPy 3": "16"},
        "default_user": "hncode",
        "test_backend": "dmoj",
    },
    "tinhoctre": {
        "label": "TinHocTre",
        "base_url": "https://tinhoctre.vn",
        "type_id": "1",
        "group_id": "1",
        "languages": {
            "C++17": "4",
            "C++20": "14",
            "Pascal": "7",
            "Python 3": "9",
            "PyPy 3": "17",
            "Scratch": "12",
        },
        "default_user": "admin",
        "test_backend": "vnoj",
    },
}

CONTEST_TARGETS = {
    "contest_hnoj": {
        "label": "HNOJ Contest",
        "base_url": "https://contest.hnoj.edu.vn",
        "default_user": "admin",
        "problem_target": "hnoj",
    },
    **TARGETS,
}

PROMPT_GUIDE = """Với mỗi bài trong danh sách dưới đây, hãy tạo đủ 4 file:

1. File sinh test:
   - Tên file: gentest_<ma_bai>.py
   - Ví dụ: gentest_tht26_tongbi.py

2. File lời giải Python:
   - Tên file: sol_<ma_bai>.py
   - Ví dụ: sol_tht26_tongbi.py

3. File lời giải C++:
   - Tên file: sol_<ma_bai>.cpp
   - Ví dụ: sol_tht26_tongbi.cpp

4. File đề bài Markdown:
   - Tên file: <ma_bai>.md
   - Ví dụ: tht26_tongbi.md
   - Dòng đầu tiên của file phải có đúng cấu trúc:
     Tên bài | Mã bài
   - Ví dụ:
     Tổng bi | tht26_tongbi
   - Sau dòng đầu tiên là toàn bộ nội dung đề bài.

Yêu cầu đối với file sinh test:

- File sinh test là file Python.
- Trong file sinh test phải nhúng lời giải chuẩn bằng C++ để sinh output.
- Khi chạy file sinh test, chương trình tự tạo thư mục test cho bài tương ứng.
- Tên thư mục test nên là mã bài, ví dụ:
  tht26_tongbi/
- Các file test trong thư mục có dạng:
  01.inp, 01.out
  02.inp, 02.out
  ...
- Sau khi sinh test, file sinh test tự nén thư mục test thành:
  tht26_tongbi.zip

Yêu cầu đối với bộ test:

- Bộ test phải đủ mạnh, phủ đủ các trường hợp đặc biệt và trường hợp biên.
- Dữ liệu phải đúng giới hạn của đề bài.
- Nếu đề có subtask, số lượng test phải phân bố đúng theo tỉ lệ subtask.
- Nếu bài đơn giản, chỉ cần khoảng 10 test.
- Nếu bài cần nhiều trường hợp để kiểm tra chặt chẽ hơn, có thể sinh khoảng 20 test hoặc nhiều hơn.
- Cần có 01 test ví dụ, các test nhỏ, test biên, test ngẫu nhiên có kiểm soát, test đủ các trường hợp và test lớn.

Sau khi tạo xong, hãy nén toàn bộ các file đã tạo thành một file zip duy nhất và gửi lại cho tôi.

Ví dụ với bài:

Tổng bi | tht26_tongbi

Cần tạo 4 file:

- gentest_tht26_tongbi.py
- sol_tht26_tongbi.py
- sol_tht26_tongbi.cpp
- tht26_tongbi.md

Hãy thực hiện cho toàn bộ các bài được cung cấp bên dưới."""

QUIZ_FORMAT_GUIDE = """# Format soạn danh sách quiz

Mỗi câu hỏi tách nhau bằng một dòng chỉ gồm `---`.

Các loại hợp lệ:
- `MC` hoặc `Trắc nghiệm 1 đáp án`
- `MA` hoặc `Trắc nghiệm nhiều đáp án`
- `SA` hoặc `Trả lời ngắn`
- `TF` hoặc `Đúng / Sai`

Mẫu:

Loại: MC
Tiêu đề: Câu hỏi ví dụ 1
Nội dung:
Trong Python, hàm nào dùng để in ra màn hình?
Lựa chọn:
- A. input()
- B. print()
- C. len()
- D. range()
Đáp án: B
Giải thích:
`print()` dùng để in dữ liệu ra màn hình.
---
Loại: MA
Tiêu đề: Số nguyên tố
Nội dung:
Những số nào sau đây là số nguyên tố?
Lựa chọn:
- A. 2
- B. 3
- C. 4
- D. 9
Đáp án: A, B
---
Loại: SA
Tiêu đề: Kết quả phép tính
Nội dung:
Tính 6 * 7.
Đáp án:
- 42
- bốn mươi hai
---
Loại: TF
Tiêu đề: Đúng sai
Nội dung:
Python là một ngôn ngữ lập trình.
Đáp án: Đúng

Ghi chú:
- Nhãn quiz để trống.
- `Xáo trộn lựa chọn` và `Công khai` chọn trên giao diện tool.
- Với câu `TF`, tool tự tạo hai lựa chọn `Đúng` và `Sai`.
"""

app = Flask(__name__)
PROGRESS_DIR = RUNTIME / "progress"
prepared_uploads: dict[str, dict] = {}
prepared_transfers: dict[str, dict] = {}
prepared_contest_transfers: dict[str, dict] = {}


class ProblemAlreadyExists(RuntimeError):
    pass


class ContestAlreadyExists(RuntimeError):
    pass


QUESTION_TYPE_ALIASES = {
    "mc": "MC",
    "trac nghiem 1 dap an": "MC",
    "trac nghiem mot dap an": "MC",
    "trắc nghiệm 1 đáp án": "MC",
    "trắc nghiệm một đáp án": "MC",
    "ma": "MA",
    "trac nghiem nhieu dap an": "MA",
    "trắc nghiệm nhiều đáp án": "MA",
    "sa": "SA",
    "tra loi ngan": "SA",
    "trả lời ngắn": "SA",
    "tf": "TF",
    "dung sai": "TF",
    "dung / sai": "TF",
    "đúng sai": "TF",
    "đúng / sai": "TF",
}

QUIZ_FIELD_ALIASES = {
    "loại": "type",
    "loai": "type",
    "type": "type",
    "tiêu đề": "title",
    "tieu de": "title",
    "title": "title",
    "nội dung": "content",
    "noi dung": "content",
    "content": "content",
    "lựa chọn": "choices",
    "lua chon": "choices",
    "choices": "choices",
    "đáp án": "answer",
    "dap an": "answer",
    "answer": "answer",
    "answers": "answer",
    "giải thích": "explanation",
    "giai thich": "explanation",
    "explanation": "explanation",
}


def normalize_key_text(value: str) -> str:
    value = value.strip().lower()
    replacements = {
        "áàảãạăắằẳẵặâấầẩẫậ": "a",
        "éèẻẽẹêếềểễệ": "e",
        "íìỉĩị": "i",
        "óòỏõọôốồổỗộơớờởỡợ": "o",
        "úùủũụưứừửữự": "u",
        "ýỳỷỹỵ": "y",
        "đ": "d",
    }
    for chars, repl in replacements.items():
        for ch in chars:
            value = value.replace(ch, repl)
    value = re.sub(r"\s+", " ", value)
    return value


def quiz_field_from_line(line: str) -> tuple[str, str] | None:
    match = re.match(r"^\s*([^:：]{1,40})\s*[:：]\s*(.*)$", line)
    if not match:
        return None
    raw_key = match.group(1).strip()
    key = QUIZ_FIELD_ALIASES.get(raw_key.lower()) or QUIZ_FIELD_ALIASES.get(normalize_key_text(raw_key))
    if not key:
        return None
    return key, match.group(2).strip()


def split_quiz_blocks(text: str) -> list[str]:
    blocks: list[list[str]] = [[]]
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip() == "---":
            if blocks[-1]:
                blocks.append([])
            continue
        blocks[-1].append(line)
    return ["\n".join(block).strip() for block in blocks if "\n".join(block).strip()]


def parse_choice_lines(text: str) -> list[dict]:
    choices = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(?:[-*]\s*)?([A-Za-z0-9]+)\s*[\.\):：-]\s*(.+)$", line)
        if not match:
            raise RuntimeError(f"Lựa chọn không đúng dạng `- A. Nội dung`: {line}")
        choices.append({"id": match.group(1).strip(), "text": match.group(2).strip()})
    return choices


def split_answers(text: str) -> list[str]:
    parts: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"^\s*[-*]\s*", "", line).strip()
        if not line:
            continue
        if "," in line or ";" in line or "|" in line:
            parts.extend(item.strip() for item in re.split(r"[,;|]", line) if item.strip())
        else:
            parts.append(line)
    return parts


def parse_quiz_markdown(text: str) -> list[dict]:
    items = []
    for index, block in enumerate(split_quiz_blocks(text), 1):
        fields = {"type": "", "title": "", "content": "", "choices": "", "answer": "", "explanation": ""}
        current: str | None = None
        for line in block.splitlines():
            parsed = quiz_field_from_line(line)
            if parsed:
                current, value = parsed
                fields[current] = value
                continue
            if current:
                fields[current] = (fields[current] + "\n" + line).strip("\n")
        qtype = QUESTION_TYPE_ALIASES.get(fields["type"].strip().lower()) or QUESTION_TYPE_ALIASES.get(normalize_key_text(fields["type"]))
        if not qtype:
            raise RuntimeError(f"Câu {index}: Loại câu hỏi không hợp lệ: {fields['type']!r}")
        content = fields["content"].strip()
        if not content:
            raise RuntimeError(f"Câu {index}: thiếu Nội dung.")
        title = fields["title"].strip() or re.sub(r"\s+", " ", content)[:80] or f"Câu hỏi {index}"
        choices = parse_choice_lines(fields["choices"]) if fields["choices"].strip() else []
        answers = split_answers(fields["answer"])
        if qtype in {"MC", "MA"}:
            if not choices:
                raise RuntimeError(f"Câu {index}: câu trắc nghiệm cần có Lựa chọn.")
            if not answers:
                raise RuntimeError(f"Câu {index}: câu trắc nghiệm cần có Đáp án.")
            valid_ids = {choice["id"] for choice in choices}
            missing = [answer for answer in answers if answer not in valid_ids]
            if missing:
                raise RuntimeError(f"Câu {index}: đáp án {', '.join(missing)} không có trong lựa chọn.")
            correct = {"answers": answers if qtype == "MA" else (answers[0] if answers else "")}
        elif qtype == "SA":
            if not answers:
                raise RuntimeError(f"Câu {index}: câu trả lời ngắn cần có ít nhất một Đáp án.")
            choices = []
            correct = {"type": "exact", "answers": answers, "case_sensitive": False}
        else:
            if not choices:
                choices = [{"id": "T", "text": "Đúng"}, {"id": "F", "text": "Sai"}]
            if not answers:
                raise RuntimeError(f"Câu {index}: câu Đúng/Sai cần có Đáp án.")
            raw = normalize_key_text(answers[0] if answers else "")
            correct_id = "T" if raw in {"dung", "true", "t", "1", "yes"} else "F" if raw in {"sai", "false", "f", "0", "no"} else answers[0] if answers else ""
            if correct_id not in {choice["id"] for choice in choices}:
                raise RuntimeError(f"Câu {index}: đáp án Đúng/Sai phải là Đúng hoặc Sai.")
            correct = {"answers": correct_id}
        items.append(
            {
                "index": index,
                "type": qtype,
                "title": title,
                "content": content,
                "choices": choices,
                "correct_answers": correct,
                "explanation": fields["explanation"].strip(),
            }
        )
    if not items:
        raise RuntimeError("Chưa có câu hỏi nào trong nội dung quiz.")
    return items


def create_quiz_question(session, question: dict, *, shuffle_choices: bool, is_public: bool) -> str:
    create_url = urljoin(QUIZ_BASE_URL, "/quiz/questions/create/")
    page = session.get(create_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form tạo quiz: HTTP {page.status_code}")
    data = {
        "csrfmiddlewaretoken": csrf_token(page.text),
        "title": question["title"],
        "question_type": question["type"],
        "content": question["content"],
        "choices": json.dumps(question["choices"], ensure_ascii=False),
        "correct_answers": json.dumps(question["correct_answers"], ensure_ascii=False),
        "grading_strategy": "all_or_nothing",
        "tags": "",
        "explanation": question.get("explanation", ""),
    }
    if shuffle_choices:
        data["shuffle_choices"] = "on"
    if is_public:
        data["is_public"] = "on"
    result = session.post(create_url, data=data, headers={"Referer": create_url}, allow_redirects=True, timeout=30)
    if not result.ok:
        raise RuntimeError(f"Tạo quiz lỗi HTTP {result.status_code}")
    errors = form_errors(result.text)
    if errors:
        raise RuntimeError("Form tạo quiz báo lỗi: " + "; ".join(errors))
    match = re.search(r"/quiz/questions/(\d+)/", result.url)
    if not match:
        raise RuntimeError(f"Tạo quiz chưa trả về trang câu hỏi: {result.url}")
    return urljoin(QUIZ_BASE_URL, f"/quiz/questions/{match.group(1)}/")


def valid_progress_id(progress_id: str | None) -> str | None:
    if progress_id and re.fullmatch(r"[0-9a-f]{32}", progress_id):
        return progress_id
    return None


def progress_path(progress_id: str) -> Path:
    return PROGRESS_DIR / f"{progress_id}.json"


def progress_update(progress_id: str | None, **payload) -> None:
    progress_id = valid_progress_id(progress_id)
    if not progress_id:
        return
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    path = progress_path(progress_id)
    current = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current.update(payload)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def progress_finish(progress_id: str | None, ok: bool, message: str = "") -> None:
    progress_update(progress_id, finished=True, ok=ok, message=message)


def safe_extract_zip(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if dest_resolved not in target.parents and target != dest_resolved:
                raise RuntimeError(f"File zip có đường dẫn không an toàn: {member.filename}")
        zf.extractall(dest)


def scratch_submission_score(student_dir: Path) -> int:
    history = student_dir / "$History"
    score = 0
    if history.is_dir():
        score += sum(1 for item in history.iterdir() if item.is_file() and item.suffix.lower() == ".sb3") * 2
    score += sum(1 for item in student_dir.iterdir() if item.is_file() and item.suffix.lower() == ".sb3")
    return score


def find_scratch_data_root(extract_root: Path) -> Path:
    candidates = [extract_root]
    candidates.extend(item for item in extract_root.iterdir() if item.is_dir())
    best = extract_root
    best_score = -1
    for candidate in candidates:
        score = sum(1 for child in candidate.iterdir() if child.is_dir() and scratch_submission_score(child) > 0)
        if score > best_score:
            best = candidate
            best_score = score
    return best


def history_version(path: Path) -> int:
    match = re.search(r"_(\d+)\.sb3$", path.name, re.IGNORECASE)
    return int(match.group(1)) if match else -1


def get_last_scratch_submission(student_dir: Path) -> Path | None:
    history = student_dir / "$History"
    if history.is_dir():
        history_files = [item for item in history.iterdir() if item.is_file() and item.suffix.lower() == ".sb3"]
        if history_files:
            return max(history_files, key=history_version)
    root_files = [item for item in student_dir.iterdir() if item.is_file() and item.suffix.lower() == ".sb3"]
    if root_files:
        return sorted(root_files, key=lambda item: item.name.lower())[0]
    return None


def collect_last_scratch_submissions(data_root: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for student_dir in sorted((item for item in data_root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
        last_file = get_last_scratch_submission(student_dir)
        row = {"student_id": student_dir.name, "source": "", "output": "", "status": "missing"}
        if last_file:
            output_name = f"{student_dir.name}.sb3"
            output_path = output_dir / output_name
            shutil.copy2(last_file, output_path)
            row.update({"source": last_file.relative_to(data_root).as_posix(), "output": output_name, "status": "ok"})
        rows.append(row)
    report_lines = [
        "student_id\tstatus\toutput_file\tsource_file",
        *[f"{row['student_id']}\t{row['status']}\t{row['output']}\t{row['source']}" for row in rows],
    ]
    (output_dir / "report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    found = sum(1 for row in rows if row["status"] == "ok")
    return {"rows": rows, "total": len(rows), "found": found, "missing": len(rows) - found}


CODE_EXTENSIONS = {".py", ".cpp", ".cc", ".cxx", ".c", ".pas", ".java"}
AI_SOURCE_DEFAULT = r"E:\Google Drive\Google Drive\1-School\4-KiThi\THT\2026\TW\KV\Data"


def normalize_contest_name(zip_path: Path) -> str:
    name = zip_path.stem
    return re.sub(r"[-_]?data$", "", name, flags=re.IGNORECASE)


def code_problem_from_name(name: str) -> str:
    stem = Path(name).stem
    return re.sub(r"_\d+$", "", stem)


def history_version_from_name(name: str) -> int:
    match = re.search(r"_(\d+)(?:\.[^.]+)$", name)
    return int(match.group(1)) if match else 10**18


def read_zip_text(zf: zipfile.ZipFile, member: str) -> str:
    raw = zf.read(member)
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def strip_code_comments(text: str, ext: str) -> str:
    if ext == ".py":
        text = re.sub(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', " ", text)
        return re.sub(r"#.*", " ", text)
    if ext in {".cpp", ".cc", ".cxx", ".c", ".java"}:
        text = re.sub(r"/\*[\s\S]*?\*/", " ", text)
        return re.sub(r"//.*", " ", text)
    if ext == ".pas":
        text = re.sub(r"\{[\s\S]*?\}", " ", text)
        text = re.sub(r"\(\*[\s\S]*?\*\)", " ", text)
        return re.sub(r"//.*", " ", text)
    return text


def comment_line_count(text: str, ext: str) -> int:
    lines = text.splitlines()
    count = sum(1 for line in lines if line.strip().startswith(("#", "//", "{", "(*")))
    if ext in {".cpp", ".cc", ".cxx", ".c", ".java"}:
        count += len(re.findall(r"/\*[\s\S]*?\*/", text))
    if ext == ".py":
        count += len(re.findall(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', text))
    return count


def code_identifiers(cleaned: str, ext: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned)
    keywords = {
        "include", "using", "namespace", "std", "int", "long", "double", "float", "char", "bool", "return", "for",
        "while", "if", "else", "elif", "def", "class", "import", "from", "as", "in", "and", "or", "not", "True",
        "False", "None", "void", "const", "auto", "vector", "map", "set", "dict", "list", "str", "range", "cin",
        "cout", "begin", "end", "var", "procedure", "function", "then", "do",
    }
    return [word for word in words if word not in keywords and not word.isupper()]


def compact_style_bucket(features: dict) -> str:
    if features["ext"] == ".py":
        if features["line_count"] <= 8:
            size = "py-compact"
        elif features["function_count"] >= 2 or features["import_count"] >= 3:
            size = "py-structured"
        else:
            size = "py-simple"
        io = "fastio" if features["fast_io"] else "plainio"
    elif features["ext"] in {".cpp", ".cc", ".cxx", ".c"}:
        if features["macro_count"] >= 4 or features["using_alias_count"] >= 3:
            size = "cpp-template"
        elif features["line_count"] <= 35:
            size = "cpp-short"
        else:
            size = "cpp-plain"
        io = "bits" if features["include_bits"] else "nobits"
    else:
        size = features["ext"].lstrip(".")
        io = "plain"
    return f"{size}/{io}/c{min(features['comment_ratio_bucket'], 4)}/id{min(features['identifier_bucket'], 4)}"


def analyze_code_text(text: str, ext: str) -> dict:
    lines = text.splitlines()
    nonempty = [line for line in lines if line.strip()]
    cleaned = strip_code_comments(text, ext)
    identifiers = code_identifiers(cleaned, ext)
    long_ids = [item for item in identifiers if len(item) >= 10]
    comment_count = comment_line_count(text, ext)
    line_count = max(len(lines), 1)
    comment_ratio = comment_count / line_count
    avg_line_len = sum(len(line) for line in nonempty) / max(len(nonempty), 1)
    ai_phrases = [
        "complexity", "approach", "edge case", "edge cases", "initialize", "iterate", "we need", "we can",
        "let's", "this function", "read input", "print result", "return answer", "time complexity",
        "space complexity", "base case", "recursive", "dynamic programming", "greedy approach",
    ]
    lower = text.lower()
    phrase_hits = [phrase for phrase in ai_phrases if phrase in lower]
    function_count = len(re.findall(r"\bdef\s+\w+\s*\(", text)) + len(re.findall(r"\b[a-zA-Z_][\w:<>,\s*&]*\s+\w+\s*\([^;{}]*\)\s*\{", text))
    features = {
        "ext": ext,
        "line_count": len(lines),
        "char_count": len(text),
        "avg_line_len": round(avg_line_len, 1),
        "comment_ratio": round(comment_ratio, 3),
        "comment_ratio_bucket": int(min(comment_ratio * 12, 9)),
        "blank_ratio": round((line_count - len(nonempty)) / line_count, 3),
        "macro_count": len(re.findall(r"^\s*#\s*define\b", text, re.MULTILINE)),
        "include_count": len(re.findall(r"^\s*#\s*include\b", text, re.MULTILINE)),
        "include_bits": bool(re.search(r"#\s*include\s*<bits/stdc\+\+\.h>", text)),
        "using_alias_count": len(re.findall(r"\b(using|typedef)\b", text)),
        "import_count": len(re.findall(r"^\s*(import|from)\s+", text, re.MULTILINE)),
        "function_count": function_count,
        "class_count": len(re.findall(r"\bclass\s+\w+", text)),
        "fast_io": bool(re.search(r"ios::sync_with_stdio|cin\.tie|sys\.stdin|stdin\.read|readline", text)),
        "long_identifier_ratio": round(len(long_ids) / max(len(identifiers), 1), 3),
        "identifier_bucket": int(min((len(long_ids) / max(len(identifiers), 1)) * 10, 9)),
        "avg_identifier_len": round(sum(len(item) for item in identifiers) / max(len(identifiers), 1), 2),
        "ai_phrase_hits": phrase_hits,
    }
    reasons = []
    score = 0
    if phrase_hits:
        score += min(24, 8 + 4 * len(phrase_hits))
        reasons.append("Có chú thích/cụm từ giải thích kiểu AI: " + ", ".join(phrase_hits[:4]))
    if comment_ratio >= 0.18 and len(lines) >= 25:
        score += 12
        reasons.append("Tỉ lệ chú thích cao bất thường")
    if features["long_identifier_ratio"] >= 0.22 and len(identifiers) >= 20:
        score += 10
        reasons.append("Nhiều tên biến/hàm dài, mô tả rất chuẩn")
    if ext == ".py" and features["function_count"] >= 2 and features["import_count"] >= 3 and len(lines) >= 35:
        score += 10
        reasons.append("Python có cấu trúc/import khá công nghiệp")
    if ext in {".cpp", ".cc", ".cxx", ".c"} and features["macro_count"] >= 6 and features["using_alias_count"] >= 4:
        score += 8
        reasons.append("C++ dùng template/macro dày")
    if features["class_count"] >= 1 and len(lines) >= 45:
        score += 6
        reasons.append("Có class/cấu trúc lớn so với bài thi lập trình phổ thông")
    features["code_ai_score"] = min(score, 45)
    features["code_reasons"] = reasons
    features["style_bucket"] = compact_style_bucket(features)
    return features


def vector_distance(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    dist = 0.0
    if a["ext"] != b["ext"]:
        dist += 35
    if a["style_bucket"] != b["style_bucket"]:
        dist += 18
    numeric = [
        ("line_count", 80, 10),
        ("comment_ratio", 0.25, 10),
        ("macro_count", 8, 7),
        ("import_count", 6, 7),
        ("function_count", 6, 7),
        ("avg_identifier_len", 8, 6),
        ("long_identifier_ratio", 0.35, 8),
    ]
    for key, scale, weight in numeric:
        dist += min(abs(float(a.get(key, 0)) - float(b.get(key, 0))) / scale, 1.0) * weight
    return round(min(dist, 100), 1)


def normalized_code_tokens(text: str, ext: str) -> list[str]:
    cleaned = strip_code_comments(text, ext).lower()
    cleaned = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " STR ", cleaned)
    raw_tokens = re.findall(r"[a-z_][a-z0-9_]*|\d+(?:\.\d+)?|==|!=|<=|>=|\+\+|--|&&|\|\||[+\-*/%<>=(){}\[\],.;:]", cleaned)
    keywords = {
        "if", "else", "elif", "for", "while", "do", "return", "break", "continue", "switch", "case", "default",
        "def", "class", "import", "from", "as", "in", "and", "or", "not", "true", "false", "none",
        "int", "long", "double", "float", "char", "bool", "void", "const", "auto", "string", "vector", "map", "set",
        "cin", "cout", "scanf", "printf", "readln", "writeln", "begin", "end", "var", "procedure", "function",
    }
    normalized = []
    for token in raw_tokens:
        if re.fullmatch(r"\d+(?:\.\d+)?", token):
            normalized.append("NUM")
        elif token == "str":
            normalized.append("STR")
        elif re.fullmatch(r"[a-z_][a-z0-9_]*", token) and token not in keywords:
            normalized.append("ID")
        else:
            normalized.append(token)
    return normalized


def token_fingerprints(tokens: list[str], size: int = 7) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


def code_similarity_percent(a: dict, b: dict) -> float:
    if a["ext"] != b["ext"]:
        return 0.0
    fa = a.get("fingerprints") or set()
    fb = b.get("fingerprints") or set()
    if not fa or not fb:
        return 0.0
    jaccard = len(fa & fb) / max(len(fa | fb), 1)
    containment = max(len(fa & fb) / max(len(fa), 1), len(fa & fb) / max(len(fb), 1))
    return round(max(jaccard * 100, containment * 92), 1)


def classify_copy_similarity(percent: float) -> str:
    if percent >= 88:
        return "Rất giống"
    if percent >= 75:
        return "Giống nhiều"
    if percent >= 62:
        return "Cần xem lại"
    return "Thấp"


def detect_code_copy_pairs(finals: list[dict]) -> tuple[list[dict], list[dict]]:
    by_problem = defaultdict(list)
    for item in finals:
        tokens = normalized_code_tokens(item.get("text", ""), item["ext"])
        item["norm_token_count"] = len(tokens)
        item["fingerprints"] = token_fingerprints(tokens)
        if len(tokens) >= 25 and len(item["fingerprints"]) >= 5:
            by_problem[(item["contest"], item["problem"], item["ext"])].append(item)

    detail_pairs = []
    for (contest, problem, ext), items in by_problem.items():
        items = sorted(items, key=lambda row: row["student_id"])
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a["student_id"] == b["student_id"]:
                    continue
                percent = code_similarity_percent(a, b)
                if percent < 62:
                    continue
                shared = len(a["fingerprints"] & b["fingerprints"])
                detail_pairs.append(
                    {
                        "contest": contest,
                        "problem": problem,
                        "language": ext.lstrip("."),
                        "student_a": a["student_id"],
                        "student_b": b["student_id"],
                        "percent": percent,
                        "level": classify_copy_similarity(percent),
                        "shared_fingerprints": shared,
                        "tokens_a": a["norm_token_count"],
                        "tokens_b": b["norm_token_count"],
                        "file_a": a["path"],
                        "file_b": b["path"],
                        "local_a": a.get("local_path", ""),
                        "local_b": b.get("local_path", ""),
                    }
                )

    pair_summary = {}
    for row in detail_pairs:
        key = tuple(sorted([row["student_a"], row["student_b"]]))
        current = pair_summary.setdefault(
            key,
            {
                "student_a": key[0],
                "student_b": key[1],
                "pair_count": 0,
                "max_percent": 0.0,
                "avg_percent": 0.0,
                "contests": set(),
                "problems": [],
                "levels": Counter(),
            },
        )
        current["pair_count"] += 1
        current["max_percent"] = max(current["max_percent"], row["percent"])
        current["avg_percent"] += row["percent"]
        current["contests"].add(row["contest"])
        current["problems"].append(f"{row['contest']}/{row['problem']}:{row['percent']}%")
        current["levels"][row["level"]] += 1

    summaries = []
    for row in pair_summary.values():
        row["avg_percent"] = round(row["avg_percent"] / max(row["pair_count"], 1), 1)
        row["contests"] = ", ".join(sorted(row["contests"]))
        row["problems"] = "; ".join(row["problems"][:12])
        if row["levels"].get("Rất giống"):
            row["level"] = "Rất giống"
        elif row["levels"].get("Giống nhiều"):
            row["level"] = "Giống nhiều"
        else:
            row["level"] = "Cần xem lại"
        summaries.append(row)
    return summaries, detail_pairs


def classify_ai_score(score: float) -> str:
    if score >= 60:
        return "Khả năng cao"
    if score >= 45:
        return "Khả năng trung bình"
    return "Khả năng thấp"


def safe_output_part(part: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", part).strip()
    return cleaned or "_"


def extract_code_member(zf: zipfile.ZipFile, member: str, output_root: Path, contest: str) -> Path:
    parts = [safe_output_part(part) for part in Path(member).parts if part not in ("", ".", "..")]
    target = output_root / safe_output_part(contest)
    for part in parts:
        target = target / part
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zf.read(member))
    return target


def collect_code_records_from_zip(zip_path: Path, extract_root: Path | None = None) -> list[dict]:
    contest = normalize_contest_name(zip_path)
    records = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            ext = Path(name).suffix.lower()
            if ext not in CODE_EXTENSIONS:
                continue
            parts = Path(name).parts
            if len(parts) < 2:
                continue
            student_id = parts[0]
            is_history = "$History" in parts
            problem = code_problem_from_name(parts[-1])
            try:
                text = read_zip_text(zf, name)
            except Exception:
                continue
            if not text.strip():
                continue
            local_path = ""
            if extract_root is not None:
                local_path = str(extract_code_member(zf, name, extract_root, contest))
            features = analyze_code_text(text, ext)
            records.append(
                {
                    "contest": contest,
                    "student_id": student_id,
                    "problem": problem,
                    "path": name,
                    "filename": parts[-1],
                    "is_history": is_history,
                    "version": history_version_from_name(parts[-1]) if is_history else 10**18,
                    "ext": ext,
                    "text": text,
                    "local_path": local_path,
                    "features": features,
                }
            )
    return records


def final_code_records(records: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for record in records:
        grouped[(record["contest"], record["student_id"], record["problem"])].append(record)
    finals = []
    for items in grouped.values():
        root_items = [item for item in items if not item["is_history"]]
        if root_items:
            finals.append(sorted(root_items, key=lambda item: item["path"])[0])
        else:
            finals.append(max(items, key=lambda item: item["version"]))
    return finals


def analyze_ai_code_records(records: list[dict]) -> dict:
    finals = final_code_records(records)
    copy_summaries, copy_details = detect_code_copy_pairs(finals)
    finals_by_student = defaultdict(list)
    all_by_student_problem = defaultdict(list)
    for record in records:
        all_by_student_problem[(record["contest"], record["student_id"], record["problem"])].append(record)
    for record in finals:
        finals_by_student[record["student_id"]].append(record)

    shifts = []
    shift_by_student = defaultdict(list)
    for key, items in all_by_student_problem.items():
        if len(items) < 2:
            continue
        ordered = sorted(items, key=lambda item: (item["version"], item["path"]))
        first, last = ordered[0], ordered[-1]
        dist = vector_distance(first["features"], last["features"])
        if dist >= 35:
            reason = []
            if first["ext"] != last["ext"]:
                reason.append(f"Đổi ngôn ngữ {first['ext']} -> {last['ext']}")
            if first["features"]["style_bucket"] != last["features"]["style_bucket"]:
                reason.append(f"Đổi style {first['features']['style_bucket']} -> {last['features']['style_bucket']}")
            row = {
                "contest": key[0],
                "student_id": key[1],
                "problem": key[2],
                "versions": len(items),
                "distance": dist,
                "first_file": first["path"],
                "last_file": last["path"],
                "first_local": first.get("local_path", ""),
                "last_local": last.get("local_path", ""),
                "reason": "; ".join(reason) or "Độ lệch đặc trưng code lớn",
            }
            shifts.append(row)
            shift_by_student[key[1]].append(row)

    students = []
    for student_id, items in sorted(finals_by_student.items()):
        languages = sorted({item["ext"].lstrip(".") for item in items})
        buckets = Counter(item["features"]["style_bucket"] for item in items)
        code_scores = [item["features"]["code_ai_score"] for item in items]
        pair_distances = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                pair_distances.append(vector_distance(items[i]["features"], items[j]["features"]))
        max_pair = max(pair_distances) if pair_distances else 0
        avg_pair = sum(pair_distances) / len(pair_distances) if pair_distances else 0
        inconsistency = 0
        reasons = []
        if len(languages) >= 2 and len(items) >= 3:
            inconsistency += min(18, 7 * (len(languages) - 1))
            reasons.append("Dùng nhiều ngôn ngữ trong các bài: " + ", ".join(languages))
        if len(buckets) >= 3 and len(items) >= 3:
            inconsistency += min(20, 6 * (len(buckets) - 2))
            reasons.append("Template/phong cách giữa các bài khác nhau")
        if max_pair >= 60:
            inconsistency += 16
            reasons.append("Có cặp bài cùng thí sinh lệch phong cách rất mạnh")
        elif avg_pair >= 42:
            inconsistency += 10
            reasons.append("Độ lệch phong cách trung bình cao")
        if shift_by_student.get(student_id):
            inconsistency += min(24, 10 + 4 * len(shift_by_student[student_id]))
            reasons.append("Có lần nộp cùng bài đổi phong cách/template rõ")
        top_code = max(code_scores) if code_scores else 0
        avg_code = sum(code_scores) / len(code_scores) if code_scores else 0
        score = min(100, round(top_code * 0.8 + avg_code * 0.35 + inconsistency, 1))
        code_reason_hits = []
        for item in sorted(items, key=lambda row: row["features"]["code_ai_score"], reverse=True)[:3]:
            code_reason_hits.extend(item["features"]["code_reasons"][:2])
        all_reasons = reasons + code_reason_hits
        students.append(
            {
                "student_id": student_id,
                "level": classify_ai_score(score),
                "score": score,
                "final_count": len(items),
                "history_shift_count": len(shift_by_student.get(student_id, [])),
                "languages": ", ".join(languages),
                "style_count": len(buckets),
                "max_pair_distance": round(max_pair, 1),
                "avg_pair_distance": round(avg_pair, 1),
                "reasons": "; ".join(dict.fromkeys(all_reasons)) or "Ít dấu hiệu bất thường",
                "sample_files": "; ".join(item["path"] for item in sorted(items, key=lambda row: row["features"]["code_ai_score"], reverse=True)[:3]),
            }
        )
    details = []
    for item in sorted(records, key=lambda row: (row["contest"], row["student_id"], row["problem"], row["is_history"], row["path"])):
        f = item["features"]
        details.append(
            {
                "contest": item["contest"],
                "student_id": item["student_id"],
                "problem": item["problem"],
                "kind": "history" if item["is_history"] else "final/root",
                "file": item["path"],
                "local_path": item.get("local_path", ""),
                "ext": item["ext"].lstrip("."),
                "code_ai_score": f["code_ai_score"],
                "style_bucket": f["style_bucket"],
                "line_count": f["line_count"],
                "comment_ratio": f["comment_ratio"],
                "macro_count": f["macro_count"],
                "import_count": f["import_count"],
                "function_count": f["function_count"],
                "avg_identifier_len": f["avg_identifier_len"],
                "long_identifier_ratio": f["long_identifier_ratio"],
                "reasons": "; ".join(f["code_reasons"]),
            }
        )
    return {
        "students": students,
        "details": details,
        "shifts": shifts,
        "finals": finals,
        "copy_summaries": copy_summaries,
        "copy_details": copy_details,
    }


def autosize_worksheet(ws) -> None:
    for column in ws.columns:
        max_length = 0
        letter = column[0].column_letter
        for cell in column:
            value = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, min(len(value), 80))
        ws.column_dimensions[letter].width = max(10, min(max_length + 2, 55))


def write_ai_warning_excel(analysis: dict, output_path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()

    def style_header(sheet) -> None:
        for cell in sheet[1]:
            cell.font = Font(bold=True)

    def set_hyperlink(cell, target: str, label: str | None = None) -> None:
        if label is not None:
            cell.value = label
        if not target:
            return
        try:
            if target.startswith("#"):
                cell.hyperlink = target
            else:
                cell.hyperlink = Path(target).resolve().as_uri()
            cell.style = "Hyperlink"
        except Exception:
            pass

    def add_sheet_link(sheet, row: int, label: str, sheet_name: str, note: str) -> None:
        sheet.cell(row=row, column=1, value=label)
        set_hyperlink(sheet.cell(row=row, column=2), f"#'{sheet_name}'!A1", "Mở sheet")
        sheet.cell(row=row, column=3, value=note)

    ws = wb.active
    ws.title = "Tong quan"
    high = sum(1 for row in analysis["students"] if row["level"] == "Khả năng cao")
    medium = sum(1 for row in analysis["students"] if row["level"] == "Khả năng trung bình")
    low = sum(1 for row in analysis["students"] if row["level"] == "Khả năng thấp")
    copy_very = sum(1 for row in analysis["copy_summaries"] if row["level"] == "Rất giống")
    copy_many = sum(1 for row in analysis["copy_summaries"] if row["level"] == "Giống nhiều")
    ws["A1"] = "Tổng quan báo cáo cảnh báo AI code và chép code"
    ws["A1"].font = Font(bold=True, size=14)
    overview_rows = [
        ("Số thí sinh", len(analysis["students"])),
        ("Khả năng AI cao", high),
        ("Khả năng AI trung bình", medium),
        ("Khả năng AI thấp", low),
        ("Số file code phân tích", len(analysis["details"])),
        ("Số trường hợp đổi style cùng bài", len(analysis["shifts"])),
        ("Số cặp nghi chép code", len(analysis["copy_summaries"])),
        ("Cặp rất giống", copy_very),
        ("Cặp giống nhiều", copy_many),
    ]
    row_idx = 3
    for label, value in overview_rows:
        ws.cell(row=row_idx, column=1, value=label)
        ws.cell(row=row_idx, column=2, value=value)
        row_idx += 1
    row_idx += 1
    ws.cell(row=row_idx, column=1, value="Các sheet chi tiết").font = Font(bold=True)
    row_idx += 1
    add_sheet_link(ws, row_idx, "Cảnh báo AI theo thí sinh", "Canh bao AI", "Mức cao/trung bình/thấp và lý do")
    row_idx += 1
    add_sheet_link(ws, row_idx, "Chép code tổng hợp", "Chep code tong hop", "Mỗi cặp thí sinh chỉ liệt kê một lần")
    row_idx += 1
    add_sheet_link(ws, row_idx, "Chép code chi tiết", "Chep code chi tiet", "Chi tiết theo contest/bài, có % giống nhau")
    row_idx += 1
    add_sheet_link(ws, row_idx, "Chi tiết file code", "Chi tiet file code", "Có link mở file code đã giải nén")
    row_idx += 1
    add_sheet_link(ws, row_idx, "Đổi style cùng bài", "Doi style cung bai", "Các lần nộp cùng bài đổi template/phong cách")
    row_idx += 2
    ws.cell(row=row_idx, column=1, value="Top cảnh báo AI").font = Font(bold=True)
    row_idx += 1
    ws.append(["Mã thí sinh", "Mức cảnh báo", "Điểm", "Lý do"])
    for item in sorted(analysis["students"], key=lambda r: (-r["score"], r["student_id"]))[:15]:
        ws.append([item["student_id"], item["level"], item["score"], item["reasons"]])
    row_idx = ws.max_row + 2
    ws.cell(row=row_idx, column=1, value="Top cặp nghi chép code").font = Font(bold=True)
    row_idx += 1
    ws.append(["Thí sinh A", "Thí sinh B", "Mức", "% cao nhất", "Số bài/cặp", "Bài liên quan"])
    for item in sorted(analysis["copy_summaries"], key=lambda r: (-r["max_percent"], -r["pair_count"], r["student_a"], r["student_b"]))[:15]:
        ws.append([item["student_a"], item["student_b"], item["level"], item["max_percent"], item["pair_count"], item["problems"]])
    autosize_worksheet(ws)

    ws = wb.create_sheet("Canh bao AI")
    headers = [
        "Mã thí sinh", "Mức cảnh báo", "Điểm nghi vấn", "Số bài final", "Số đổi style trong history",
        "Ngôn ngữ", "Số nhóm style", "Lệch lớn nhất", "Lệch trung bình", "Lý do", "File mẫu cần xem",
    ]
    ws.append(headers)
    fills = {
        "Khả năng cao": PatternFill("solid", fgColor="FCA5A5"),
        "Khả năng trung bình": PatternFill("solid", fgColor="FDE68A"),
        "Khả năng thấp": PatternFill("solid", fgColor="BBF7D0"),
    }
    for row in sorted(analysis["students"], key=lambda item: (-item["score"], item["student_id"])):
        ws.append([
            row["student_id"], row["level"], row["score"], row["final_count"], row["history_shift_count"],
            row["languages"], row["style_count"], row["max_pair_distance"], row["avg_pair_distance"],
            row["reasons"], row["sample_files"],
        ])
        ws.cell(ws.max_row, 2).fill = fills.get(row["level"], PatternFill())
    style_header(ws)
    ws.freeze_panes = "A2"
    autosize_worksheet(ws)

    ws = wb.create_sheet("Chep code tong hop")
    ws.append(["Thí sinh A", "Thí sinh B", "Mức giống", "% cao nhất", "% trung bình", "Số bài/cặp giống", "Contest", "Bài liên quan"])
    for row in sorted(analysis["copy_summaries"], key=lambda item: (-item["max_percent"], -item["pair_count"], item["student_a"], item["student_b"])):
        ws.append([
            row["student_a"], row["student_b"], row["level"], row["max_percent"], row["avg_percent"],
            row["pair_count"], row["contests"], row["problems"],
        ])
    style_header(ws)
    ws.freeze_panes = "A2"
    autosize_worksheet(ws)

    ws = wb.create_sheet("Chep code chi tiet")
    ws.append([
        "Contest", "Mã bài", "Ngôn ngữ", "Thí sinh A", "Thí sinh B", "% giống", "Mức",
        "Fingerprint chung", "Token A", "Token B", "File A", "Mở file A", "File B", "Mở file B",
    ])
    for row in sorted(analysis["copy_details"], key=lambda item: (-item["percent"], item["contest"], item["problem"], item["student_a"], item["student_b"])):
        ws.append([
            row["contest"], row["problem"], row["language"], row["student_a"], row["student_b"],
            row["percent"], row["level"], row["shared_fingerprints"], row["tokens_a"], row["tokens_b"],
            row["file_a"], "Mở file", row["file_b"], "Mở file",
        ])
        set_hyperlink(ws.cell(ws.max_row, 12), row.get("local_a", ""), "Mở file")
        set_hyperlink(ws.cell(ws.max_row, 14), row.get("local_b", ""), "Mở file")
    style_header(ws)
    ws.freeze_panes = "A2"
    autosize_worksheet(ws)

    ws = wb.create_sheet("Chi tiet file code")
    detail_headers = [
        "Contest", "Mã thí sinh", "Mã bài", "Loại", "File", "Mở file", "Ngôn ngữ", "Điểm dấu hiệu AI",
        "Nhóm style", "Số dòng", "Tỉ lệ comment", "Macro", "Import", "Hàm", "Độ dài tên TB",
        "Tỉ lệ tên dài", "Lý do",
    ]
    ws.append(detail_headers)
    for row in analysis["details"]:
        ws.append([
            row["contest"], row["student_id"], row["problem"], row["kind"], row["file"], "Mở file", row["ext"],
            row["code_ai_score"], row["style_bucket"], row["line_count"], row["comment_ratio"],
            row["macro_count"], row["import_count"], row["function_count"], row["avg_identifier_len"],
            row["long_identifier_ratio"], row["reasons"],
        ])
        set_hyperlink(ws.cell(ws.max_row, 6), row.get("local_path", ""), "Mở file")
    style_header(ws)
    ws.freeze_panes = "A2"
    autosize_worksheet(ws)

    ws = wb.create_sheet("Doi style cung bai")
    shift_headers = ["Contest", "Mã thí sinh", "Mã bài", "Số phiên bản", "Độ lệch", "File đầu", "Mở file đầu", "File cuối", "Mở file cuối", "Lý do"]
    ws.append(shift_headers)
    for row in sorted(analysis["shifts"], key=lambda item: (-item["distance"], item["student_id"])):
        ws.append([
            row["contest"], row["student_id"], row["problem"], row["versions"], row["distance"],
            row["first_file"], "Mở file", row["last_file"], "Mở file", row["reason"],
        ])
        set_hyperlink(ws.cell(ws.max_row, 7), row.get("first_local", ""), "Mở file")
        set_hyperlink(ws.cell(ws.max_row, 9), row.get("last_local", ""), "Mở file")
    style_header(ws)
    ws.freeze_panes = "A2"
    autosize_worksheet(ws)

    ws = wb.create_sheet("Giai thich")
    notes = [
        ["Lưu ý", "Đây là báo cáo cảnh báo/nghi vấn, không phải kết luận chắc chắn thí sinh dùng AI."],
        ["Nguồn điểm", "Điểm kết hợp dấu hiệu trong từng file code, độ lệch phong cách giữa các bài, và đổi phong cách trong history cùng bài."],
        ["Khả năng cao", "Điểm nghi vấn từ 60 trở lên."],
        ["Khả năng trung bình", "Điểm nghi vấn từ 45 đến dưới 60."],
        ["Khả năng thấp", "Điểm nghi vấn dưới 45."],
        ["Nên xem lại", "Ưu tiên mở các file trong cột File mẫu cần xem và sheet Đổi style cùng bài."],
        ["Chép code", "So khớp các cặp final/root cùng contest và cùng bài. File quá ngắn không được chấm để tránh nhiễu."],
        ["% giống", "Dựa trên token code đã bỏ comment, chuẩn hóa tên biến/hằng số và so fingerprint k-gram."],
        ["Link file", "Báo cáo có link tới thư mục code đã giải nén trong .runtime/misc của tool local."],
        ["Không phân tích", "File Scratch .sb3 là nhị phân nên không được chấm bằng heuristic code văn bản."],
    ]
    for row in notes:
        ws.append(row)
    style_header(ws)
    autosize_worksheet(ws)
    wb.save(output_path)


def build_ai_warning_report(source_zips: list[Path], output_path: Path) -> dict:
    records = []
    extract_root = output_path.parent / "extracted_code"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)
    for zip_path in source_zips:
        records.extend(collect_code_records_from_zip(zip_path, extract_root))
    if not records:
        raise RuntimeError("Không tìm thấy file code văn bản (.py/.cpp/.pas/.c/.java) trong dữ liệu.")
    analysis = analyze_ai_code_records(records)
    write_ai_warning_excel(analysis, output_path)
    high = sum(1 for row in analysis["students"] if row["level"] == "Khả năng cao")
    medium = sum(1 for row in analysis["students"] if row["level"] == "Khả năng trung bình")
    low = sum(1 for row in analysis["students"] if row["level"] == "Khả năng thấp")
    return {
        "zip_count": len(source_zips),
        "code_file_count": len(records),
        "student_count": len(analysis["students"]),
        "high": high,
        "medium": medium,
        "low": low,
        "shift_count": len(analysis["shifts"]),
        "copy_pair_count": len(analysis["copy_summaries"]),
        "copy_detail_count": len(analysis["copy_details"]),
        "copy_very_similar": sum(1 for row in analysis["copy_summaries"] if row["level"] == "Rất giống"),
        "copy_many": sum(1 for row in analysis["copy_summaries"] if row["level"] == "Giống nhiều"),
        "extracted_folder": str(extract_root),
        "filename": output_path.name,
    }


@app.before_request
def require_basic_auth():
    auth_user = os.getenv("TOOL_OJ_AUTH_USER")
    auth_pass = os.getenv("TOOL_OJ_AUTH_PASS")
    if not auth_user and not auth_pass:
        return None
    auth = request.authorization
    if auth and auth.username == auth_user and auth.password == auth_pass:
        return None
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Tool HNCode"'},
    )


PAGE = r"""
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tool HNCode</title>
  <link rel="icon" type="image/svg+xml" href="/static/favicon-HNCode.svg">
  <style>
    :root { --bg:#f5f7fb; --panel:#fff; --ink:#172033; --muted:#667085; --line:#d8dee9; --soft:#eef2f6; --accent:#0f766e; --ok:#087443; --bad:#b42318; --warn:#b54708; --code:#101828; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:"Segoe UI", Arial, sans-serif; font-size:14px; }
    header { background:var(--panel); border-bottom:1px solid var(--line); padding:16px 22px; display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; }
    h1 { margin:0; font-size:22px; letter-spacing:0; }
    h2 { margin:0 0 8px; font-size:18px; }
    h3 { margin:16px 0 8px; font-size:15px; }
    p { color:var(--muted); line-height:1.45; margin:0 0 12px; }
    .nav { display:flex; gap:8px; flex-wrap:wrap; }
    .nav button, button.action { border:1px solid #b8c2d3; border-radius:6px; padding:10px 14px; background:#fff; color:var(--ink); font:inherit; font-weight:700; cursor:pointer; box-shadow:0 1px 2px rgba(16,24,40,.08); }
    .nav button:hover, button.action:hover { border-color:#8fa1b8; background:#f8fafc; }
    .nav button.active, button.primary { background:var(--accent); border-color:var(--accent); color:#fff; box-shadow:0 2px 6px rgba(15,118,110,.24); }
    button.primary:hover { background:#0b665f; border-color:#0b665f; }
    button:disabled { opacity:.5; cursor:not-allowed; }
    main { max-width:1320px; margin:0 auto; padding:20px; display:grid; grid-template-columns:minmax(520px, 1.1fr) minmax(360px, .9fr); gap:18px; }
    section { background:var(--panel); border:1px solid var(--line); border-radius:8px; }
    .panel { display:none; padding:18px; }
    .panel.active { display:block; }
    label { display:block; margin:12px 0 6px; color:#344054; font-weight:650; }
    input[type=text], input[type=password], select, textarea { width:100%; border:1px solid var(--line); border-radius:6px; padding:9px 10px; font:inherit; background:#fff; color:var(--ink); }
    textarea { min-height:78px; resize:vertical; line-height:1.45; }
    .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .grid-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; }
    .row { display:flex; gap:10px; align-items:end; flex-wrap:wrap; }
    .row > .grow { flex:1 1 340px; }
    .actions { display:flex; gap:10px; margin-top:16px; flex-wrap:wrap; }
    #toggleGuide { margin-top:6px; }
    .table-tools { display:flex; gap:8px; margin-top:14px; flex-wrap:wrap; }
    .note, .guide { border:1px solid #b8d8d3; background:#f0fdfa; color:#134e48; border-radius:8px; padding:12px; line-height:1.48; margin:12px 0; }
    .guide { border-color:var(--line); background:#fafbfc; color:var(--ink); }
    .tool-card { border:1px solid #cbd5e1; background:#fff; border-radius:8px; padding:16px; margin-top:16px; box-shadow:0 1px 3px rgba(16,24,40,.08); }
    .tool-card + .tool-card { margin-top:18px; }
    .tool-title { display:flex; align-items:center; gap:10px; margin:0 0 8px; font-size:18px; color:#0f172a; }
    .tool-title::before { content:""; width:6px; height:24px; border-radius:999px; background:var(--accent); display:inline-block; }
    .tool-subtitle { margin-bottom:14px; }
    .sample, pre#log { background:var(--code); color:#f2f4f7; border-radius:6px; padding:12px; white-space:pre-wrap; overflow:auto; font-family:Consolas, "Cascadia Mono", monospace; font-size:12px; line-height:1.45; }
    .log-panel { display:grid; grid-template-rows:auto minmax(560px, 1fr); min-height:700px; }
    .log-head { padding:14px 16px; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:12px; align-items:center; }
    pre#log { margin:0; border-radius:0 0 8px 8px; }
    .status { border-radius:999px; padding:4px 10px; background:var(--soft); color:var(--muted); font-weight:650; font-size:12px; }
    .status.ok { background:#dcfae6; color:var(--ok); }
    .status.err { background:#fee4e2; color:var(--bad); }
    .status.warn { background:#fef0c7; color:var(--warn); }
    .row-status.ok { color:var(--ok); font-weight:700; }
    .row-status.err { color:var(--bad); font-weight:700; }
    .row-status.warn { color:var(--warn); font-weight:700; }
    .log-ok { color:#86efac; font-weight:700; }
    .log-err { color:#fca5a5; font-weight:700; }
    .log-warn { color:#fde68a; font-weight:700; }
    .log-progress { color:#bfdbfe; font-weight:700; }
    .login-badge { display:inline-flex; align-items:center; min-height:24px; border-radius:999px; padding:3px 9px; background:var(--soft); color:var(--muted); font-size:12px; font-weight:700; margin-top:6px; }
    .login-badge.ok { background:#dcfae6; color:var(--ok); }
    .login-badge.err { background:#fee4e2; color:var(--bad); }
    table { width:100%; border-collapse:collapse; margin-top:14px; font-size:13px; }
    th, td { border-bottom:1px solid var(--line); padding:8px; vertical-align:top; text-align:left; }
    th { background:#f8fafc; font-weight:700; }
    .inner-table { margin-top:0; font-size:12px; }
    .inner-table th, .inner-table td { padding:5px 6px; }
    td input[type=text] { padding:6px 7px; }
    a.problem-link { color:var(--accent); font-weight:700; text-decoration:none; }
    .test-meta { color:var(--muted); font-size:12px; line-height:1.4; }
    .lang-list { display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:8px; margin-top:8px; }
    .check { display:flex; align-items:center; gap:7px; }
    .hidden { display:none; }
    @media (max-width:980px) { main { grid-template-columns:1fr; padding:14px; } .grid-2,.grid-3,.lang-list { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Tool HNCode</h1>
    <div class="nav">
      <button type="button" class="active" data-panel="accounts">Tài khoản & Hướng dẫn</button>
      <button type="button" data-panel="upload">Up bài</button>
      <button type="button" data-panel="transfer">Chuyển bài</button>
      <button type="button" data-panel="contest-transfer">Chuyển contest</button>
      <button type="button" data-panel="contest-create">Tạo contest</button>
      <button type="button" data-panel="quiz-upload">Up Quiz</button>
      <button type="button" data-panel="misc-tools">Tool lẻ</button>
    </div>
  </header>

  <main>
    <section>
      <div class="panel active" id="panel-accounts">
        <h2>Tài khoản & Hướng dẫn</h2>
        <p>Lưu tạm tài khoản trên trình duyệt máy này. Khi chạy tác vụ, form sẽ tự điền các thông tin đã lưu.</p>
        <div class="grid-3">
          <div><label>HNOJ user</label><input id="acct_hnoj_user" type="text" value="hncode"><span id="login_hnoj" class="login-badge">Chưa kiểm tra</span></div>
          <div><label>HNCode user</label><input id="acct_hncode_user" type="text" value="hncode"><span id="login_hncode" class="login-badge">Chưa kiểm tra</span></div>
          <div><label>TinHocTre user</label><input id="acct_tinhoctre_user" type="text" value="admin"><span id="login_tinhoctre" class="login-badge">Chưa kiểm tra</span></div>
        </div>
        <div class="grid-3">
          <div><label>HNOJ password</label><input id="acct_hnoj_pass" type="password"></div>
          <div><label>HNCode password</label><input id="acct_hncode_pass" type="password"></div>
          <div><label>TinHocTre password</label><input id="acct_tinhoctre_pass" type="password"></div>
        </div>
        <label>Cookie TinHocTre nếu bị WAF/challenge</label>
        <textarea id="acct_tinhoctre_cookie" placeholder="Dán nguyên dòng Cookie của tinhoctre.vn sau khi đăng nhập, ví dụ: sessionid=...; csrftoken=...; ..."></textarea>
        <p>Nếu TinHocTre chặn đăng nhập tự động, hãy đăng nhập TinHocTre trên trình duyệt, mở DevTools → Network, chọn một request tới tinhoctre.vn rồi copy Request Header `Cookie` dán vào ô này.</p>
        <div class="actions">
          <button class="action" type="button" id="openTinHocTreBrowser">Mở Edge đăng nhập TinHocTre</button>
          <button class="action" type="button" id="pullTinHocTreCookie">Lấy cookie từ Edge</button>
          <button class="action primary" type="button" id="quickTinHocTreCookie">Lấy cookie nhanh từ Edge</button>
        </div>
        <div class="grid-2">
          <div><label>HNOJ Contest user</label><input id="acct_contest_hnoj_user" type="text" value="admin"><span id="login_contest_hnoj" class="login-badge">Chưa kiểm tra</span></div>
          <div><label>HNOJ Contest password</label><input id="acct_contest_hnoj_pass" type="password"></div>
        </div>
        <div class="actions">
          <button class="action primary" type="button" id="saveAccounts">Lưu tạm</button>
          <button class="action" type="button" id="checkAccounts">Kiểm tra đăng nhập</button>
          <button class="action" type="button" id="clearAccounts">Xóa thông tin đã lưu</button>
        </div>
        <button class="action" type="button" id="toggleGuide">Ẩn / Hiện hướng dẫn prompt</button>
        <div class="guide hidden" id="promptGuide"><div class="sample">{{ prompt_guide }}</div></div>
      </div>

      <div class="panel" id="panel-upload">
        <h2>Up bài</h2>
        <p>Chọn web đích, chọn zip bộ bài, bấm Chuẩn bị dữ liệu để xem bảng bài trước khi up thật.</p>
        <div class="grid-2">
          <div>
            <label>Web đích</label>
            <select id="uploadTarget">
              <option value="hnoj">HNOJ</option>
              <option value="hncode">HNCode</option>
              <option value="tinhoctre">TinHocTre</option>
            </select><span id="uploadTargetLogin" class="login-badge">Chưa kiểm tra</span>
          </div>
          <div>
            <label>File zip bộ bài hoặc file Markdown tổng hợp</label>
            <div class="row">
              <div class="grow"><input id="uploadZip" type="text" value="{{ default_zip }}"></div>
              <button class="action" type="button" id="chooseZip">Chọn file</button>
              <input id="zipFileInput" class="hidden" type="file" accept=".zip,.md,application/zip,text/markdown,text/plain">
            </div>
          </div>
        </div>
        <div class="grid-2">
          <div><label>Giới hạn thời gian</label><input id="timeLimit" type="text" value="1.0"></div>
          <div><label>Giới hạn bộ nhớ</label><input id="memoryLimit" type="text" value="1048576"></div>
        </div>
        <h3>Ngôn ngữ cho phép</h3>
        <div id="languages" class="lang-list"></div>

        <div class="actions">
          <button class="action" type="button" id="toggleAdvanced">Mở rộng thông tin khác</button>
        </div>
        <div id="advancedUpload" class="hidden">
          <div class="grid-3">
            <div><label>Người tạo (Creators)</label><input id="creator" type="text" value="mrtee"></div>
            <div><label>Dạng đề (Problem types)</label><input id="typeLabel" type="text" value="Chưa phân loại" disabled></div>
            <div><label>Nhóm bài (Problem group)</label><input id="groupLabel" type="text" value="Chưa phân loại" disabled></div>
          </div>
        </div>

        <div class="grid-3" style="margin-top:12px">
          <label class="check"><input type="checkbox" id="submitCpp"> Nộp bài chấm thử C++</label>
          <label class="check"><input type="checkbox" id="submitPython" checked> Nộp bài chấm thử Python</label>
          <label class="check"><input type="checkbox" id="noSubmit"> Không nộp bài chấm thử</label>
        </div>
        <label class="check" style="margin-top:12px"><input type="checkbox" id="skipStatementTitle" checked> Bỏ dòng đầu tiên trong file đề bài</label>
        <div class="actions">
          <button class="action primary" type="button" id="prepareUpload">Chuẩn bị dữ liệu</button>
          <button class="action primary" type="button" id="confirmUpload" disabled>Xác nhận Up bài</button>
        </div>
        <div id="uploadTable"></div>
      </div>

      <div class="panel" id="panel-transfer">
        <h2>Chuyển bài</h2>
        <p>Chọn nguồn, đích và danh sách mã bài. Tool sẽ lấy đề/test từ nguồn rồi tạo bài và upload test ở đích.</p>
        <div class="grid-2">
          <div><label>Nguồn</label><select id="transferSource"><option value="tinhoctre">TinHocTre</option><option value="hnoj">HNOJ</option><option value="hncode">HNCode</option></select><span id="transferSourceLogin" class="login-badge">Chưa kiểm tra</span></div>
          <div><label>Đích</label><select id="transferDest"><option value="hncode">HNCode</option><option value="hnoj">HNOJ</option><option value="tinhoctre">TinHocTre</option></select><span id="transferDestLogin" class="login-badge">Chưa kiểm tra</span></div>
        </div>
        <div class="grid-2">
          <div><label>Giới hạn thời gian mặc định</label><input id="transferTimeLimit" type="text" value="1.0"></div>
          <div><label>Giới hạn bộ nhớ mặc định</label><input id="transferMemoryLimit" type="text" value="1048576"></div>
        </div>
        <div class="actions">
          <button class="action" type="button" id="applyTransferLimits">Áp dụng cho tất cả các bài</button>
          <button class="action" type="button" id="resetTransferLimits">Mặc định</button>
        </div>
        <h3>Ngôn ngữ cho phép ở đích</h3>
        <div id="transferLanguages" class="lang-list"></div>
        <div class="actions">
          <button class="action" type="button" id="toggleTransferAdvanced">Mở rộng thông tin khác</button>
        </div>
        <div id="advancedTransfer" class="hidden">
          <div class="grid-3">
            <div><label>Người tạo (Creators)</label><input id="transferCreator" type="text" value="mrtee"></div>
            <div><label>Dạng đề (Problem types)</label><input id="transferTypeLabel" type="text" value="Chưa phân loại" disabled></div>
            <div><label>Nhóm bài (Problem group)</label><input id="transferGroupLabel" type="text" value="Chưa phân loại" disabled></div>
          </div>
        </div>
        <label>Danh sách mã bài cần chuyển</label>
        <textarea id="transferCodes" placeholder="tht26_tongbi&#10;tht26_quatang"></textarea>
        <div class="actions">
          <button class="action primary" type="button" id="prepareTransfer">Chuẩn bị dữ liệu</button>
          <button class="action primary" type="button" id="confirmTransfer" disabled>Xác nhận chuyển bài</button>
        </div>
        <div id="transferTable"></div>
      </div>

      <div class="panel" id="panel-contest-transfer">
        <h2>Chuyển contest</h2>
        <p>Chuyển contest gồm thông tin cơ bản, danh sách bài, điểm và bộ test của từng bài. Không chuyển bài nộp của học sinh.</p>
        <div class="grid-2">
          <div>
            <label>Nguồn</label>
            <select id="contestSource">
              <option value="contest_hnoj">HNOJ Contest</option>
              <option value="hnoj">HNOJ</option>
              <option value="hncode">HNCode</option>
              <option value="tinhoctre">TinHocTre</option>
            </select><span id="contestSourceLogin" class="login-badge">Chưa kiểm tra</span>
          </div>
          <div>
            <label>Đích</label>
            <select id="contestDest">
              <option value="hnoj">HNOJ</option>
              <option value="hncode">HNCode</option>
              <option value="tinhoctre">TinHocTre</option>
            </select><span id="contestDestLogin" class="login-badge">Chưa kiểm tra</span>
          </div>
        </div>
        <label>Danh sách mã contest cần chuyển</label>
        <textarea id="contestCodes" placeholder="tht2026_hn_ck_a&#10;tht2026_hn_ck_b&#10;tht2026_hn_ck_c"></textarea>
        <div class="grid-2">
          <div><label>Time mặc định cho bài thiếu thông tin</label><input id="contestProblemTime" type="text" value="1.0"></div>
          <div><label>Memory mặc định cho bài thiếu thông tin</label><input id="contestProblemMemory" type="text" value="1048576"></div>
        </div>
        <label class="check" style="margin-top:12px"><input type="checkbox" id="contestReuseExistingProblems" checked> Nếu bài đã có ở đích thì dùng lại bài đó</label>
        <label class="check" style="margin-top:8px"><input type="checkbox" id="contestCreateMissingProblems" checked> Tự chuyển bài/test còn thiếu trước khi tạo contest</label>
        <div class="actions">
          <button class="action primary" type="button" id="prepareContestTransfer">Chuẩn bị dữ liệu</button>
          <button class="action primary" type="button" id="confirmContestTransfer" disabled>Xác nhận chuyển contest</button>
        </div>
        <div id="contestTransferTable"></div>
      </div>

      <div class="panel" id="panel-contest-create">
        <h2>Tạo contest từ mã bài</h2>
        <p>Tạo contest cơ bản và gắn các mã bài đã có trên web đích. Các thiết lập chi tiết có thể chỉnh lại trong admin sau.</p>
        <div class="grid-2">
          <div><label>Web đích</label><select id="createContestTarget"><option value="hnoj">HNOJ</option><option value="hncode">HNCode</option><option value="tinhoctre">TinHocTre</option></select><span id="createContestLogin" class="login-badge">Chưa kiểm tra</span></div>
          <div><label>Mã contest</label><input id="createContestKey" type="text" placeholder="tht2026_hn_ck_a"></div>
        </div>
        <label>Tên contest</label><input id="createContestName" type="text" placeholder="TIN HỌC TRẺ 2026 - HÀ NỘI - CHUNG KẾT - BẢNG A">
        <div class="grid-2">
          <div><label>Bắt đầu</label><input id="createContestStart" type="datetime-local"></div>
          <div><label>Kết thúc</label><input id="createContestEnd" type="datetime-local"></div>
        </div>
        <div class="actions">
          <button class="action" type="button" id="contestTimeToday">Hôm nay 8:00-11:00</button>
          <button class="action" type="button" id="contestTimeTomorrow">Ngày mai 8:00-11:00</button>
          <button class="action" type="button" id="contestTime90">Kết thúc sau 90 phút</button>
        </div>
        <label>Danh sách mã bài</label>
        <textarea id="createContestProblems" placeholder="tht26hn_cka_thieunhi&#10;tht26hn_cka_tongdayso"></textarea>
        <div class="actions">
          <button class="action primary" type="button" id="createContestButton">Tạo contest</button>
        </div>
      </div>

      <div class="panel" id="panel-quiz-upload">
        <h2>Up Quiz</h2>
        <p>Up danh sách câu hỏi lên HNCode Quiz tại <code>https://oj.hncode.edu.vn/quiz/questions/create/</code>. Nhãn để trống.</p>
        <div class="grid-2">
          <div><label>HNCode user</label><input id="quizUserMirror" type="text" value="hncode" readonly><span id="quizLogin" class="login-badge">Chưa kiểm tra</span></div>
          <div><label>File quiz Markdown/TXT</label><div class="row"><div class="grow"><input id="quizFileName" type="text" placeholder="Có thể bỏ trống và dán trực tiếp nội dung bên dưới" readonly></div><button class="action" type="button" id="chooseQuizFile">Chọn file</button><input id="quizFileInput" class="hidden" type="file" accept=".md,.txt,text/markdown,text/plain"></div></div>
        </div>
        <div class="grid-2" style="margin-top:12px">
          <label class="check"><input type="checkbox" id="quizShuffleChoices" checked> Xáo trộn lựa chọn</label>
          <label class="check"><input type="checkbox" id="quizPublic"> Công khai</label>
        </div>
        <label>Nội dung danh sách quiz</label>
        <textarea id="quizMarkdown" style="min-height:340px" placeholder="Dán danh sách quiz theo format, hoặc bấm Chèn mẫu format."></textarea>
        <div class="actions">
          <button class="action" type="button" id="fillQuizSample">Chèn mẫu format</button>
          <button class="action primary" type="button" id="uploadQuizButton">Up list quiz</button>
        </div>
        <div id="quizUploadSummary"></div>
      </div>

      <div class="panel" id="panel-misc-tools">
        <h2>Tool lẻ</h2>
        <p>Các chức năng phụ chạy ổn định trên local, không cần đăng nhập web OJ.</p>
        <div class="tool-card">
          <h3 class="tool-title">Lấy last submissions Scratch</h3>
          <p class="tool-subtitle">Upload file zip data. Tool sẽ lấy mỗi thí sinh 1 file `.sb3`: ưu tiên file trong thư mục `$History` có số cuối lớn nhất, nếu không có thì lấy file `.sb3` ở thư mục gốc của thí sinh.</p>
          <label>File zip data</label>
          <div class="row">
            <div class="grow"><input id="lastSubZipName" type="text" placeholder="Chưa chọn file zip" readonly></div>
            <button class="action" type="button" id="chooseLastSubZip">Chọn file</button>
            <input id="lastSubZipFile" class="hidden" type="file" accept=".zip,application/zip">
          </div>
          <div class="actions">
            <button class="action primary" type="button" id="runLastSubmissions">Tạo zip last submissions</button>
          </div>
          <div id="lastSubmissionsSummary"></div>
        </div>

        <div class="tool-card">
          <h3 class="tool-title">Cảnh báo sử dụng AI để code</h3>
          <p class="tool-subtitle">Nhận vào một folder chứa nhiều file zip contest hoặc chọn một file zip data contest. Tool phân tích dấu hiệu AI code, đổi phong cách code và nghi vấn chép code nhau, rồi xuất Excel có link mở file code.</p>
          <label>Folder chứa các zip contest</label>
          <input id="aiWarningFolder" type="text" value="{{ ai_source_default }}">
          <label>Hoặc chọn 1 file zip data contest</label>
          <div class="row">
            <div class="grow"><input id="aiWarningZipName" type="text" placeholder="Không chọn thì dùng folder ở trên" readonly></div>
            <button class="action" type="button" id="chooseAiWarningZip">Chọn file zip</button>
            <input id="aiWarningZipFile" class="hidden" type="file" accept=".zip,application/zip">
          </div>
          <p>Đây là báo cáo cảnh báo/nghi vấn, không phải kết luận chắc chắn. Nên mở các file mẫu trong Excel để kiểm tra lại.</p>
          <div class="actions">
            <button class="action primary" type="button" id="runAiWarning">Tạo báo cáo Excel</button>
          </div>
          <div id="aiWarningSummary"></div>
        </div>
      </div>
    </section>

    <section class="log-panel">
      <div class="log-head"><h2>Thông tin trả về</h2><span id="jobStatus" class="status">idle</span></div>
      <pre id="log">Sẵn sàng.</pre>
    </section>
  </main>

<script>
const TARGETS = {{ targets_json | safe }};
let preparedUpload = null;
let preparedTransfer = null;
let preparedContestTransfer = null;
let selectedZipFile = null;
const QUIZ_FORMAT_GUIDE = {{ quiz_format_guide_json | safe }};

const logEl = document.getElementById("log");
const statusEl = document.getElementById("jobStatus");
let logText = "Sẵn sàng.";
const progressTimers = new Map();
function colorizeLog(text) {
  return String(text).split("\n").map(line => {
    const trimmed = line.trim();
    let cls = "";
    if (trimmed.startsWith("✓") || trimmed.includes("Thành công") || trimmed.includes("Đã tạo") || trimmed.includes("Đã upload")) cls = "log-ok";
    else if (trimmed.startsWith("✗") || trimmed.startsWith("Error:") || trimmed.includes("Lỗi")) cls = "log-err";
    else if (trimmed.includes("đã tồn tại") || trimmed.includes("Đã tồn tại") || trimmed.includes("Bài đã tồn tại") || trimmed.includes("Contest đã tồn tại")) cls = "log-warn";
    else if (trimmed.startsWith("Tiến độ:") || trimmed.startsWith("Đang ")) cls = "log-progress";
    const safe = escapeHtml(line);
    return cls ? `<span class="${cls}">${safe}</span>` : safe;
  }).join("\n");
}
function renderLog() { logEl.innerHTML = colorizeLog(logText); logEl.scrollTop = logEl.scrollHeight; }
function log(text) { logText = String(text); renderLog(); }
function append(text) { logText += "\n" + String(text); renderLog(); }
function status(text, cls="") { statusEl.textContent = text; statusEl.className = "status " + cls; }

for (const button of document.querySelectorAll(".nav button")) {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav button").forEach(item => item.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(item => item.classList.remove("active"));
    button.classList.add("active");
    document.getElementById("panel-" + button.dataset.panel).classList.add("active");
  });
}

const accountFields = {
  hnoj_user: document.getElementById("acct_hnoj_user"),
  hnoj_pass: document.getElementById("acct_hnoj_pass"),
  hncode_user: document.getElementById("acct_hncode_user"),
  hncode_pass: document.getElementById("acct_hncode_pass"),
  tinhoctre_user: document.getElementById("acct_tinhoctre_user"),
  tinhoctre_pass: document.getElementById("acct_tinhoctre_pass"),
  tinhoctre_cookie: document.getElementById("acct_tinhoctre_cookie"),
  contest_hnoj_user: document.getElementById("acct_contest_hnoj_user"),
  contest_hnoj_pass: document.getElementById("acct_contest_hnoj_pass"),
};
function loadAccounts() {
  for (const [key, input] of Object.entries(accountFields)) {
    const value = localStorage.getItem("chuyenbai." + key);
    if (value !== null) input.value = value;
  }
}
function saveAccounts() {
  for (const [key, input] of Object.entries(accountFields)) localStorage.setItem("chuyenbai." + key, input.value);
}
loadAccounts();
document.getElementById("saveAccounts").onclick = () => { saveAccounts(); append("Đã lưu tạm tài khoản."); };
document.getElementById("checkAccounts").onclick = () => { log("Đang kiểm tra đăng nhập các trang..."); checkAllAccounts(); };
document.getElementById("openTinHocTreBrowser").onclick = async () => {
  try {
    status("running");
    const data = await postJson("/api/tinhoctre-browser/start", {});
    append(data.message || "Đã mở Edge đăng nhập TinHocTre.");
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("pullTinHocTreCookie").onclick = async () => {
  try {
    status("running");
    const data = await postJson("/api/tinhoctre-browser/cookie", {});
    accountFields.tinhoctre_cookie.value = data.cookie || "";
    saveAccounts();
    append(data.message || "Đã lấy và lưu Cookie TinHocTre.");
    await checkLogin("tinhoctre", "login_tinhoctre", firstToken(document.getElementById("transferCodes").value));
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("quickTinHocTreCookie").onclick = async () => {
  try {
    status("running");
    append("Đang đóng/mở lại Edge để lấy cookie TinHocTre...");
    const data = await postJson("/api/tinhoctre-browser/quick-cookie", {});
    accountFields.tinhoctre_cookie.value = data.cookie || "";
    saveAccounts();
    append(data.message || "Đã lấy và lưu Cookie TinHocTre từ Edge.");
    await checkLogin("tinhoctre", "login_tinhoctre", firstToken(document.getElementById("transferCodes").value));
    status("ready", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};
document.getElementById("clearAccounts").onclick = () => {
  for (const key of Object.keys(accountFields)) localStorage.removeItem("chuyenbai." + key);
  for (const [key, input] of Object.entries(accountFields)) if (key.endsWith("_pass") || key.endsWith("_cookie")) input.value = "";
  append("Đã xóa thông tin đã lưu.");
};
document.getElementById("toggleGuide").onclick = () => document.getElementById("promptGuide").classList.toggle("hidden");
document.getElementById("toggleAdvanced").onclick = () => {
  const box = document.getElementById("advancedUpload");
  box.classList.toggle("hidden");
  document.getElementById("toggleAdvanced").textContent = box.classList.contains("hidden") ? "Mở rộng thông tin khác" : "Thu gọn thông tin khác";
};
document.getElementById("toggleTransferAdvanced").onclick = () => {
  const box = document.getElementById("advancedTransfer");
  box.classList.toggle("hidden");
  document.getElementById("toggleTransferAdvanced").textContent = box.classList.contains("hidden") ? "Mở rộng thông tin khác" : "Thu gọn thông tin khác";
};
document.getElementById("applyTransferLimits").onclick = () => {
  const timeLimit = document.getElementById("transferTimeLimit").value;
  const memoryLimit = document.getElementById("transferMemoryLimit").value;
  for (const tr of document.querySelectorAll("#transferTable tbody tr")) {
    const timeInput = tr.querySelector(".row-time");
    const memoryInput = tr.querySelector(".row-memory");
    if (timeInput) timeInput.value = timeLimit;
    if (memoryInput) memoryInput.value = memoryLimit;
  }
  append("Đã áp dụng time/memory mặc định cho tất cả bài trong bảng chuyển.");
};
document.getElementById("resetTransferLimits").onclick = () => {
  for (const tr of document.querySelectorAll("#transferTable tbody tr")) {
    const timeInput = tr.querySelector(".row-time");
    const memoryInput = tr.querySelector(".row-memory");
    if (timeInput) timeInput.value = tr.dataset.sourceTime || "1.0";
    if (memoryInput) memoryInput.value = tr.dataset.sourceMemory || "1048576";
  }
  append("Đã trả time/memory về thông số lấy từ nguồn.");
};
function localDateTimeValue(date) {
  const pad = value => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function backendDateTimeValue(value) {
  if (!value) return "";
  return value.length === 16 ? value.replace("T", " ") + ":00" : value.replace("T", " ");
}
function setContestTime(dayOffset=0, startHour=8, startMinute=0, durationMinutes=180) {
  const start = new Date();
  start.setDate(start.getDate() + dayOffset);
  start.setHours(startHour, startMinute, 0, 0);
  const end = new Date(start.getTime() + durationMinutes * 60000);
  document.getElementById("createContestStart").value = localDateTimeValue(start);
  document.getElementById("createContestEnd").value = localDateTimeValue(end);
}
document.getElementById("contestTimeToday").onclick = () => setContestTime(0, 8, 0, 180);
document.getElementById("contestTimeTomorrow").onclick = () => setContestTime(1, 8, 0, 180);
document.getElementById("contestTime90").onclick = () => {
  const startInput = document.getElementById("createContestStart");
  const start = startInput.value ? new Date(startInput.value) : new Date();
  document.getElementById("createContestStart").value = localDateTimeValue(start);
  document.getElementById("createContestEnd").value = localDateTimeValue(new Date(start.getTime() + 90 * 60000));
};
document.getElementById("chooseZip").onclick = () => document.getElementById("zipFileInput").click();
document.getElementById("zipFileInput").onchange = event => {
  selectedZipFile = event.target.files[0] || null;
  if (selectedZipFile) document.getElementById("uploadZip").value = selectedZipFile.name;
};

function renderLanguages() {
  const target = document.getElementById("uploadTarget").value;
  const langs = TARGETS[target].languages;
  document.getElementById("languages").innerHTML = Object.keys(langs).map(name =>
    `<label class="check"><input type="checkbox" value="${name}" checked> ${name}</label>`
  ).join("");
}
function renderTransferLanguages() {
  const target = document.getElementById("transferDest").value;
  const langs = TARGETS[target].languages;
  document.getElementById("transferLanguages").innerHTML = Object.keys(langs).map(name =>
    `<label class="check"><input type="checkbox" value="${name}" checked> ${name}</label>`
  ).join("");
}
document.getElementById("uploadTarget").addEventListener("change", renderLanguages);
document.getElementById("transferDest").addEventListener("change", renderTransferLanguages);
document.getElementById("uploadTarget").addEventListener("change", checkUploadLogin);
document.getElementById("transferSource").addEventListener("change", checkTransferLogins);
document.getElementById("transferDest").addEventListener("change", checkTransferLogins);
document.getElementById("transferCodes").addEventListener("blur", checkTransferLogins);
document.getElementById("contestSource").addEventListener("change", checkContestLogins);
document.getElementById("contestDest").addEventListener("change", checkContestLogins);
document.getElementById("contestCodes").addEventListener("blur", checkContestLogins);
document.getElementById("createContestTarget").addEventListener("change", checkCreateContestLogin);
renderLanguages();
renderTransferLanguages();
setTimeout(() => { checkUploadLogin(); checkTransferLogins(); checkContestLogins(); checkCreateContestLogin(); checkQuizLogin(); }, 300);

function selectedLanguages() {
  return [...document.querySelectorAll("#languages input:checked")].map(item => item.value);
}
function selectedTransferLanguages() {
  return [...document.querySelectorAll("#transferLanguages input:checked")].map(item => item.value);
}
function accountPayload(target) {
  const payload = {
    username: accountFields[target + "_user"].value,
    password: accountFields[target + "_pass"].value,
  };
  if (target === "tinhoctre") payload.cookie = accountFields.tinhoctre_cookie.value;
  return payload;
}
function firstToken(value) {
  return (value || "").split(/[\s,]+/).filter(Boolean)[0] || "";
}
function setLoginBadge(id, state, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = "login-badge " + (state || "");
}
async function checkLogin(target, badgeId, probeCode="") {
  setLoginBadge(badgeId, "", "Đang kiểm tra...");
  try {
    const data = await postJson("/api/check-login", {target, account: accountPayload(target), probe_code: probeCode});
    setLoginBadge(badgeId, data.ok ? "ok" : "err", data.ok ? "✓ Đăng nhập OK" : "✗ " + (data.message || "Lỗi"));
    return data.ok;
  } catch (err) {
    setLoginBadge(badgeId, "err", "✗ " + String(err).replace(/^Error:\s*/, ""));
    return false;
  }
}
async function checkAllAccounts() {
  saveAccounts();
  await Promise.all([
    checkLogin("hnoj", "login_hnoj"),
    checkLogin("hncode", "login_hncode"),
    checkLogin("tinhoctre", "login_tinhoctre", firstToken(document.getElementById("transferCodes").value)),
    checkLogin("contest_hnoj", "login_contest_hnoj"),
  ]);
}
function checkUploadLogin() {
  checkLogin(document.getElementById("uploadTarget").value, "uploadTargetLogin");
}
function checkTransferLogins() {
  const probe = firstToken(document.getElementById("transferCodes").value);
  checkLogin(document.getElementById("transferSource").value, "transferSourceLogin", probe);
  checkLogin(document.getElementById("transferDest").value, "transferDestLogin");
}
function checkContestLogins() {
  checkLogin(document.getElementById("contestSource").value, "contestSourceLogin");
  checkLogin(document.getElementById("contestDest").value, "contestDestLogin");
}
function checkCreateContestLogin() {
  checkLogin(document.getElementById("createContestTarget").value, "createContestLogin");
}
function checkQuizLogin() {
  document.getElementById("quizUserMirror").value = accountFields.hncode_user.value || "hncode";
  checkLogin("hncode", "quizLogin");
}
function uploadSettings() {
  const target = document.getElementById("uploadTarget").value;
  return {
    target,
    zip_path: selectedZipFile ? "" : document.getElementById("uploadZip").value,
    creator: document.getElementById("creator").value,
    time_limit: document.getElementById("timeLimit").value,
    memory_limit: document.getElementById("memoryLimit").value,
    languages: selectedLanguages(),
    no_submit: document.getElementById("noSubmit").checked,
    submit_cpp: document.getElementById("submitCpp").checked,
    submit_python: document.getElementById("submitPython").checked,
    skip_statement_title: document.getElementById("skipStatementTitle").checked,
    ...accountPayload(target),
  };
}
function transferSettings() {
  const dest = document.getElementById("transferDest").value;
  return {
    creator: document.getElementById("transferCreator").value,
    time_limit: document.getElementById("transferTimeLimit").value,
    memory_limit: document.getElementById("transferMemoryLimit").value,
    languages: selectedTransferLanguages(),
    ...accountPayload(dest),
  };
}
async function postJson(url, payload) {
  const res = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  const data = await parseJsonResponse(res);
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function parseJsonResponse(res) {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch (err) {
    const preview = text.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 300);
    throw new Error(`Server trả về HTML/text thay vì JSON (HTTP ${res.status}). ${preview || "Không có nội dung lỗi."}`);
  }
}
async function prepareUploadRequest(settings) {
  if (!selectedZipFile) return postJson("/api/prepare-upload", settings);
  const form = new FormData();
  form.append("zip_file", selectedZipFile);
  form.append("payload", JSON.stringify(settings));
  const res = await fetch("/api/prepare-upload", {method:"POST", body:form});
  const data = await parseJsonResponse(res);
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
function newProgressId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID().replaceAll("-", "");
  return Array.from({length: 32}, () => Math.floor(Math.random() * 16).toString(16)).join("");
}
function statusClass(text) {
  const value = String(text || "");
  if (value.startsWith("✓") || value.includes("Thành công") || value.includes("Đã đọc")) return "ok";
  if (value.includes("đã tồn tại") || value.includes("Đã tồn tại") || value.includes("đã có") || value.includes("Đã có")) return "warn";
  if (value.startsWith("✗") || value.includes("Lỗi")) return "err";
  return "";
}
function setStatusCell(cell, text, link="") {
  cell.className = "row-status " + statusClass(text);
  const linkHtml = link ? ` <a class="problem-link" href="${escapeHtml(link)}" target="_blank" rel="noopener">Link</a>` : "";
  cell.innerHTML = `${escapeHtml(text || "")}${linkHtml}`;
}
function progressMessage(data) {
  const total = data.total || 0;
  const done = data.done || 0;
  const prefix = total ? `Tiến độ: ${done}/${total}` : "Tiến độ:";
  return data.message ? `${prefix} - ${data.message}` : prefix;
}
function startProgressPolling(progressId, tableSelector, mode="problem") {
  stopProgressPolling(progressId);
  const timer = setInterval(async () => {
    try {
      const res = await fetch(`/api/progress/${progressId}`, {cache: "no-store"});
      if (!res.ok) return;
      const data = await res.json();
      if (data.rows) {
        if (mode === "contest") applyContestStatuses(data.rows);
        else if (tableSelector) applyStatuses(data.rows, tableSelector);
      }
      if (data.message || data.total) append(progressMessage(data));
      if (data.finished) stopProgressPolling(progressId);
    } catch (err) {
      stopProgressPolling(progressId);
    }
  }, 1000);
  progressTimers.set(progressId, timer);
  return progressId;
}
function stopProgressPolling(progressId) {
  const timer = progressTimers.get(progressId);
  if (timer) clearInterval(timer);
  progressTimers.delete(progressId);
}

document.getElementById("prepareUpload").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang chuẩn bị dữ liệu...");
    startProgressPolling(progressId, "#uploadTable");
    const settings = uploadSettings();
    settings.progress_id = progressId;
    const data = await prepareUploadRequest(settings);
    stopProgressPolling(progressId);
    preparedUpload = data.prepare_id;
    renderUploadTable(data.rows);
    document.getElementById("confirmUpload").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

function renderUploadTable(rows) {
  document.getElementById("uploadTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#uploadTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#uploadTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Up đề</th><th>Up test</th><th>File test</th><th>Số test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_code)}" data-source-time="${escapeHtml(row.source_time_limit || row.time_limit || "1.0")}" data-source-memory="${escapeHtml(row.source_memory_limit || row.memory_limit || "1048576")}">
      <td><input type="checkbox" class="row-selected" checked></td>
      <td><input type="text" class="row-code" value="${escapeHtml(row.code)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name)}"></td>
      <td><input type="checkbox" class="row-statement" checked></td>
      <td><input type="checkbox" class="row-tests" ${row.upload_tests_default === false ? "" : "checked"}></td>
      <td><div class="test-meta">${escapeHtml(row.test_file)}</div></td>
      <td>${row.test_count}</td>
      <td class="row-status">Chưa up</td>
    </tr>`).join("")}</tbody></table>`;
}
function collectUploadRows() {
  return [...document.querySelectorAll("#uploadTable tbody tr")].map(tr => ({
    original_code: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    code: tr.querySelector(".row-code").value.trim(),
    name: tr.querySelector(".row-name").value.trim(),
    upload_statement: tr.querySelector(".row-statement").checked,
    upload_tests: tr.querySelector(".row-tests").checked,
  }));
}
document.getElementById("confirmUpload").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang up bài...");
    markRowsProcessing("#uploadTable", "Đang up...");
    startProgressPolling(progressId, "#uploadTable");
    const settings = uploadSettings();
    settings.progress_id = progressId;
    const data = await postJson("/api/confirm-upload", {prepare_id: preparedUpload, settings, rows: collectUploadRows(), progress_id: progressId});
    stopProgressPolling(progressId);
    applyStatuses(data.rows, "#uploadTable");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("prepareTransfer").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang đọc dữ liệu bài nguồn...");
    const source = document.getElementById("transferSource").value;
    const dest = document.getElementById("transferDest").value;
    const codes = document.getElementById("transferCodes").value.split(/[\s,]+/).filter(Boolean);
    startProgressPolling(progressId, "#transferTable");
    const data = await postJson("/api/prepare-transfer", {
      source, dest, codes,
      source_account: accountPayload(source),
      settings: transferSettings(),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    preparedTransfer = data.prepare_id;
    renderTransferTable(data.rows);
    document.getElementById("confirmTransfer").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};
function renderTransferTable(rows) {
  document.getElementById("transferTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#transferTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#transferTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Mã bài</th><th>Tên bài toán</th><th>Time</th><th>Memory</th><th>Up đề</th><th>Up test</th><th>Bộ test</th><th>Số test</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_code)}">
      <td><input type="checkbox" class="row-selected" checked></td>
      <td><input type="text" class="row-code" value="${escapeHtml(row.code)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name || "")}"></td>
      <td><input type="text" class="row-time" value="${escapeHtml(row.time_limit || "1.0")}"></td>
      <td><input type="text" class="row-memory" value="${escapeHtml(row.memory_limit || "1048576")}"></td>
      <td><input type="checkbox" class="row-statement" checked></td>
      <td><input type="checkbox" class="row-tests" checked></td>
      <td>${row.test_link ? `<a class="problem-link" href="${escapeHtml(row.test_link)}" target="_blank" rel="noopener">Bộ test</a>` : escapeHtml(row.test_file)}</td><td>${row.test_count}</td><td class="row-status">${escapeHtml(row.status)}</td>
    </tr>`).join("")}</tbody></table>`;
}
document.getElementById("confirmTransfer").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang chuyển bài...");
    const source = document.getElementById("transferSource").value;
    const dest = document.getElementById("transferDest").value;
    markRowsProcessing("#transferTable", "Đang chuyển...");
    startProgressPolling(progressId, "#transferTable");
    const data = await postJson("/api/confirm-transfer", {
      prepare_id: preparedTransfer,
      source, dest, rows: collectRows("#transferTable"),
      settings: transferSettings(),
      source_account: accountPayload(source),
      dest_account: accountPayload(dest),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    applyStatuses(data.rows, "#transferTable");
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("prepareContestTransfer").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang đọc dữ liệu contest nguồn...");
    const source = document.getElementById("contestSource").value;
    const dest = document.getElementById("contestDest").value;
    const codes = document.getElementById("contestCodes").value.split(/[\s,]+/).filter(Boolean);
    startProgressPolling(progressId, "#contestTransferTable", "contest");
    const data = await postJson("/api/prepare-contest-transfer", {
      source, dest, codes,
      source_account: accountPayload(source),
      dest_account: accountPayload(dest),
      settings: contestTransferSettings(),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    preparedContestTransfer = data.prepare_id;
    renderContestTransferTable(data.rows);
    document.getElementById("confirmContestTransfer").disabled = false;
    log(data.log);
    status("ready", "ok");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("confirmContestTransfer").onclick = async () => {
  const progressId = newProgressId();
  try {
    status("running");
    log("Đang chuyển contest...");
    const source = document.getElementById("contestSource").value;
    const dest = document.getElementById("contestDest").value;
    markRowsProcessing("#contestTransferTable", "Đang chuyển...");
    startProgressPolling(progressId, "#contestTransferTable", "contest");
    const data = await postJson("/api/confirm-contest-transfer", {
      prepare_id: preparedContestTransfer,
      source, dest, rows: collectContestRows(),
      source_account: accountPayload(source),
      dest_account: accountPayload(dest),
      settings: contestTransferSettings(),
      progress_id: progressId,
    });
    stopProgressPolling(progressId);
    applyContestStatuses(data.rows);
    log(data.log);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    stopProgressPolling(progressId);
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("createContestButton").onclick = async () => {
  try {
    status("running");
    log("Đang tạo contest...");
    const target = document.getElementById("createContestTarget").value;
    const data = await postJson("/api/create-contest", {
      target,
      account: accountPayload(target),
      key: document.getElementById("createContestKey").value.trim(),
      name: document.getElementById("createContestName").value.trim(),
      start_time: backendDateTimeValue(document.getElementById("createContestStart").value.trim()),
      end_time: backendDateTimeValue(document.getElementById("createContestEnd").value.trim()),
      problems: document.getElementById("createContestProblems").value.split(/[\s,]+/).filter(Boolean),
    });
    log(data.log);
    status("done", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("chooseQuizFile").onclick = () => document.getElementById("quizFileInput").click();
document.getElementById("quizFileInput").addEventListener("change", async event => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("quizFileName").value = file ? file.name : "";
  if (file) document.getElementById("quizMarkdown").value = await file.text();
});
document.getElementById("fillQuizSample").onclick = () => {
  document.getElementById("quizMarkdown").value = QUIZ_FORMAT_GUIDE;
};
document.getElementById("uploadQuizButton").onclick = async () => {
  try {
    status("running");
    log("Đang up list quiz lên HNCode...");
    saveAccounts();
    const data = await postJson("/api/upload-quiz", {
      account: accountPayload("hncode"),
      text: document.getElementById("quizMarkdown").value,
      shuffle_choices: document.getElementById("quizShuffleChoices").checked,
      is_public: document.getElementById("quizPublic").checked,
    });
    const rows = (data.rows || []).map(row => `${row.status} ${row.index}. ${row.title}${row.link ? " - " + row.link : ""}`).join("\n");
    document.getElementById("quizUploadSummary").innerHTML = `<div class="note">${escapeHtml(rows || data.log || "").replaceAll("\n", "<br>")}</div>`;
    log(data.log || rows);
    status(data.ok ? "done" : "failed", data.ok ? "ok" : "err");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("chooseLastSubZip").onclick = () => document.getElementById("lastSubZipFile").click();
document.getElementById("lastSubZipFile").addEventListener("change", event => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("lastSubZipName").value = file ? file.name : "";
});
document.getElementById("runLastSubmissions").onclick = async () => {
  try {
    const input = document.getElementById("lastSubZipFile");
    const file = input.files && input.files[0];
    if (!file) throw new Error("Hãy chọn file zip data trước.");
    status("running");
    log("Đang xử lý last submissions...");
    const form = new FormData();
    form.append("zip_file", file);
    const res = await fetch("/api/misc/last-submissions", {method:"POST", body:form});
    if (!res.ok) {
      const data = await parseJsonResponse(res);
      throw new Error(data.error || "Không xử lý được file zip.");
    }
    const summaryRaw = res.headers.get("X-Last-Submissions-Summary") || "";
    const summary = summaryRaw ? JSON.parse(decodeURIComponent(summaryRaw)) : {};
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = summary.filename || "last_submissions.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    const text = `✓ Đã tạo file zip last submissions.\nTìm thấy: ${summary.found || 0}/${summary.total || 0} thí sinh\nThiếu file: ${summary.missing || 0}\nFile tải về: ${summary.filename || "last_submissions.zip"}`;
    document.getElementById("lastSubmissionsSummary").innerHTML = `<div class="note">${escapeHtml(text).replaceAll("\n", "<br>")}</div>`;
    log(text);
    status("done", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

document.getElementById("chooseAiWarningZip").onclick = () => document.getElementById("aiWarningZipFile").click();
document.getElementById("aiWarningZipFile").addEventListener("change", event => {
  const file = event.target.files && event.target.files[0];
  document.getElementById("aiWarningZipName").value = file ? file.name : "";
});
document.getElementById("runAiWarning").onclick = async () => {
  try {
    status("running");
    log("Đang phân tích dấu hiệu sử dụng AI để code...");
    const input = document.getElementById("aiWarningZipFile");
    const file = input.files && input.files[0];
    const folder = document.getElementById("aiWarningFolder").value.trim();
    const form = new FormData();
    if (file) form.append("zip_file", file);
    else form.append("folder_path", folder);
    const res = await fetch("/api/misc/ai-code-warning", {method:"POST", body:form});
    if (!res.ok) {
      const data = await parseJsonResponse(res);
      throw new Error(data.error || "Không tạo được báo cáo.");
    }
    const summaryRaw = res.headers.get("X-AI-Warning-Summary") || "";
    const summary = summaryRaw ? JSON.parse(decodeURIComponent(summaryRaw)) : {};
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = summary.filename || "ai_code_warning_report.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    const text = `✓ Đã tạo báo cáo Excel cảnh báo AI code.\nSố contest zip: ${summary.zip_count || 0}\nSố file code: ${summary.code_file_count || 0}\nSố thí sinh: ${summary.student_count || 0}\nKhả năng cao: ${summary.high || 0}\nKhả năng trung bình: ${summary.medium || 0}\nKhả năng thấp: ${summary.low || 0}\nĐổi style cùng bài: ${summary.shift_count || 0}\nCặp nghi chép code: ${summary.copy_pair_count || 0}\nCặp rất giống: ${summary.copy_very_similar || 0}\nChi tiết cặp theo bài: ${summary.copy_detail_count || 0}\nThư mục code đã giải nén: ${summary.extracted_folder || ""}\nFile tải về: ${summary.filename || "ai_code_warning_report.xlsx"}`;
    document.getElementById("aiWarningSummary").innerHTML = `<div class="note">${escapeHtml(text).replaceAll("\n", "<br>")}</div>`;
    log(text);
    status("done", "ok");
  } catch (err) {
    log(String(err));
    status("failed", "err");
  }
};

function contestTransferSettings() {
  return {
    reuse_existing_problems: document.getElementById("contestReuseExistingProblems").checked,
    create_missing_problems: document.getElementById("contestCreateMissingProblems").checked,
    time_limit: document.getElementById("contestProblemTime").value,
    memory_limit: document.getElementById("contestProblemMemory").value,
  };
}

function renderContestTransferTable(rows) {
  document.getElementById("contestTransferTable").innerHTML = `<div class="table-tools">
    <button class="action" type="button" onclick="setRowSelection('#contestTransferTable', true)">Chọn tất cả</button>
    <button class="action" type="button" onclick="setRowSelection('#contestTransferTable', false)">Bỏ chọn tất cả</button>
  </div><table>
    <thead><tr><th>Chọn</th><th>Mã contest</th><th>Tên contest</th><th>Thời gian</th><th>Bài trong contest</th><th>Trạng thái</th></tr></thead>
    <tbody>${rows.map(row => `<tr data-original="${escapeHtml(row.original_key)}">
      <td><input type="checkbox" class="row-selected" ${row.can_transfer ? "checked" : ""}></td>
      <td><input type="text" class="row-key" value="${escapeHtml(row.key)}"></td>
      <td><input type="text" class="row-name" value="${escapeHtml(row.name || "")}"></td>
      <td><div class="test-meta">${escapeHtml(row.start_time || "")}<br>${escapeHtml(row.end_time || "")}</div></td>
      <td>${renderContestProblemList(row.problems || [])}</td>
      <td class="row-status">${escapeHtml(row.status)}</td>
    </tr>`).join("")}</tbody></table>`;
}

function renderContestProblemList(problems) {
  if (!problems.length) return `<div class="test-meta">Không có bài.</div>`;
  return `<table class="inner-table"><thead><tr><th>Chọn</th><th>Mã bài</th><th>Điểm</th><th>Thứ tự</th><th>Trạng thái</th></tr></thead><tbody>
    ${problems.map(p => `<tr data-problem-code="${escapeHtml(p.code)}">
      <td><input type="checkbox" class="problem-selected" checked></td>
      <td>${escapeHtml(p.code)}</td>
      <td>${escapeHtml(p.points || "100")}</td>
      <td>${escapeHtml(p.order || "")}</td>
      <td>${escapeHtml(p.status || "")}</td>
    </tr>`).join("")}
  </tbody></table>`;
}

function collectContestRows() {
  return [...document.querySelectorAll("#contestTransferTable > table > tbody > tr")].map(tr => ({
    original_key: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    key: tr.querySelector(".row-key").value.trim(),
    name: tr.querySelector(".row-name").value.trim(),
    problems: [...tr.querySelectorAll(".inner-table tbody tr")].map(pr => ({
      code: pr.dataset.problemCode,
      selected: pr.querySelector(".problem-selected").checked,
    })),
  }));
}

function applyContestStatuses(rows) {
  const byOriginal = new Map(rows.map(row => [row.original_key, row]));
  for (const tr of document.querySelectorAll("#contestTransferTable > table > tbody > tr")) {
    const row = byOriginal.get(tr.dataset.original);
    if (!row) continue;
    setStatusCell(tr.querySelector(".row-status"), row.status, row.link || "");
  }
}

function collectRows(selector) {
  return [...document.querySelectorAll(selector + " tbody tr")].map(tr => ({
    original_code: tr.dataset.original,
    selected: tr.querySelector(".row-selected").checked,
    code: tr.querySelector(".row-code").value.trim(),
    name: tr.querySelector(".row-name").value.trim(),
    time_limit: tr.querySelector(".row-time") ? tr.querySelector(".row-time").value.trim() : "",
    memory_limit: tr.querySelector(".row-memory") ? tr.querySelector(".row-memory").value.trim() : "",
    upload_statement: tr.querySelector(".row-statement").checked,
    upload_tests: tr.querySelector(".row-tests").checked,
  }));
}
function setRowSelection(selector, checked) {
  document.querySelectorAll(selector + " .row-selected").forEach(item => { item.checked = checked; });
}
function markRowsProcessing(selector, text="Đang xử lý...") {
  for (const tr of document.querySelectorAll(selector + " tbody tr")) {
    const selected = tr.querySelector(".row-selected");
    const statusCell = tr.querySelector(".row-status");
    if (selected && selected.checked && statusCell) {
      statusCell.className = "row-status";
      statusCell.textContent = text;
    }
  }
}
function applyStatuses(rows, selector) {
  const byOriginal = new Map(rows.map(row => [row.original_code, row]));
  for (const tr of document.querySelectorAll(selector + " tbody tr")) {
    const row = byOriginal.get(tr.dataset.original);
    if (!row) continue;
    setStatusCell(tr.querySelector(".row-status"), row.status, row.link || "");
  }
}
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[ch]));
}
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(
        PAGE,
        default_zip=DEFAULT_ZIP,
        ai_source_default=AI_SOURCE_DEFAULT,
        prompt_guide=PROMPT_GUIDE,
        quiz_format_guide_json=json.dumps(QUIZ_FORMAT_GUIDE, ensure_ascii=False),
        targets_json=json.dumps(TARGETS, ensure_ascii=False),
    )


@app.post("/api/check-login")
def api_check_login():
    payload = request.get_json(force=True)
    target = payload.get("target", "")
    account = payload.get("account", {})
    probe_code = (payload.get("probe_code") or "").strip()
    try:
        if target == "tinhoctre":
            cookie_header = (account.get("cookie") or "").strip() or load_tinhoctre_cookie()
            if cookie_header:
                session = session_from_cookie(cookie_header)
                probe_url = f"/problem/{probe_code}/edit" if probe_code else "/problems/create"
                page = session.get(urljoin(TARGETS[target]["base_url"], probe_url), timeout=30)
                if page.status_code == 202 or page.headers.get("x-amzn-waf-action"):
                    return jsonify({"ok": False, "message": "WAF/challenge"})
                if probe_code and not (f'name="code"' in page.text or "name='code'" in page.text):
                    return jsonify({"ok": False, "message": "Cookie không mở được trang sửa bài"})
                if "/accounts/login" in page.url or "/accounts/login" in page.text:
                    return jsonify({"ok": False, "message": "Cookie hết hạn"})
                return jsonify({"ok": True, "message": "Đăng nhập OK"})
            login_tinhoctre_public(TARGETS[target]["base_url"], account.get("username", ""), account.get("password", ""), "/problems/create")
            return jsonify({"ok": True, "message": "Đăng nhập OK"})
        if target == "contest_hnoj":
            info = CONTEST_TARGETS[target]
        else:
            info = TARGETS[target]
        login_hncode(info["base_url"], account.get("username", ""), account.get("password", ""))
        return jsonify({"ok": True, "message": "Đăng nhập OK"})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)[:180]})


@app.post("/api/upload-quiz")
def api_upload_quiz():
    payload = request.get_json(force=True)
    account = payload.get("account", {})
    try:
        questions = parse_quiz_markdown(payload.get("text", ""))
        session = login_hncode(QUIZ_BASE_URL, account.get("username", ""), account.get("password", ""))
        shuffle_choices = bool(payload.get("shuffle_choices"))
        is_public = bool(payload.get("is_public"))
        rows = []
        ok = True
        log_lines = [
            f"Up Quiz HNCode: {QUIZ_BASE_URL}/quiz/questions/create/",
            f"Số câu hỏi: {len(questions)}",
            f"Xáo trộn lựa chọn: {'Có' if shuffle_choices else 'Không'}",
            f"Công khai: {'Có' if is_public else 'Không'}",
        ]
        for question in questions:
            row = {"index": question["index"], "title": question["title"], "type": question["type"], "status": "", "link": ""}
            try:
                link = create_quiz_question(session, question, shuffle_choices=shuffle_choices, is_public=is_public)
                row["status"] = "✓ Thành công"
                row["link"] = link
                log_lines.append(f"✓ Câu {question['index']}: {question['title']} - {link}")
            except Exception as exc:
                ok = False
                row["status"] = "✗ Lỗi"
                row["error"] = str(exc)
                log_lines.append(f"✗ Câu {question['index']}: {question['title']} - {exc}")
            rows.append(row)
        return jsonify({"ok": ok, "rows": rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.get("/api/progress/<progress_id>")
def api_progress(progress_id: str):
    if not valid_progress_id(progress_id):
        return jsonify({"error": "progress_id không hợp lệ"}), 400
    path = progress_path(progress_id)
    if not path.exists():
        return jsonify({"phase": "waiting", "done": 0, "total": 0, "message": ""})
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.post("/api/misc/last-submissions")
def api_misc_last_submissions():
    uploaded = request.files.get("zip_file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Chưa chọn file zip data."}), 400
    if Path(uploaded.filename).suffix.lower() != ".zip":
        return jsonify({"error": "File data phải là .zip."}), 400
    job_root = RUNTIME / "misc" / uuid.uuid4().hex
    input_zip = job_root / "input.zip"
    extract_root = job_root / "extract"
    output_dir = job_root / "Last_Submissions"
    try:
        job_root.mkdir(parents=True, exist_ok=True)
        uploaded.save(input_zip)
        safe_extract_zip(input_zip, extract_root)
        data_root = find_scratch_data_root(extract_root)
        summary = collect_last_scratch_submissions(data_root, output_dir)
        if summary["total"] == 0:
            return jsonify({"error": "Không tìm thấy thư mục thí sinh nào trong file zip."}), 400
        output_zip = job_root / "last_submissions.zip"
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in sorted(output_dir.iterdir(), key=lambda path: path.name.lower()):
                if item.is_file():
                    zf.write(item, item.name)
        summary_payload = {
            "total": summary["total"],
            "found": summary["found"],
            "missing": summary["missing"],
            "filename": output_zip.name,
        }
        response = send_file(output_zip, as_attachment=True, download_name=output_zip.name, mimetype="application/zip")
        response.headers["X-Last-Submissions-Summary"] = quote(json.dumps(summary_payload, ensure_ascii=False))
        return response
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/misc/ai-code-warning")
def api_misc_ai_code_warning():
    job_root = RUNTIME / "misc" / uuid.uuid4().hex
    try:
        job_root.mkdir(parents=True, exist_ok=True)
        uploaded = request.files.get("zip_file")
        source_zips: list[Path] = []
        if uploaded and uploaded.filename:
            if Path(uploaded.filename).suffix.lower() != ".zip":
                return jsonify({"error": "File data phải là .zip."}), 400
            input_zip = job_root / safe_output_part(Path(uploaded.filename).name)
            uploaded.save(input_zip)
            source_zips = [input_zip]
        else:
            folder_path = (request.form.get("folder_path") or "").strip()
            if not folder_path:
                return jsonify({"error": "Hãy chọn file zip hoặc nhập folder chứa các zip contest."}), 400
            folder = Path(folder_path)
            if not folder.exists() or not folder.is_dir():
                return jsonify({"error": f"Folder không tồn tại: {folder_path}"}), 400
            source_zips = sorted(folder.glob("*.zip"))
            if not source_zips:
                return jsonify({"error": f"Không tìm thấy file .zip nào trong folder: {folder_path}"}), 400
        output_path = job_root / "ai_code_warning_report.xlsx"
        summary = build_ai_warning_report(source_zips, output_path)
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=output_path.name,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response.headers["X-AI-Warning-Summary"] = quote(json.dumps(summary, ensure_ascii=False))
        return response
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/tinhoctre-browser/start")
def api_tinhoctre_browser_start():
    try:
        browser = find_edge_executable()
        port = int(os.getenv("TINHOCTRE_CHROME_DEBUG_PORT", "9223"))
        url = "https://tinhoctre.vn/admin/judge/problem/add/"
        subprocess.Popen(
            [
                str(browser),
                f"--remote-debugging-port={port}",
                "--remote-debugging-address=127.0.0.1",
                "--remote-allow-origins=*",
                "--profile-directory=Default",
                "--new-window",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return jsonify(
            {
                "ok": True,
                "message": "Đã mở Edge bằng profile mặc định. Hãy đăng nhập admin và đảm bảo thấy form tạo bài, rồi bấm Lấy cookie từ Edge. Nếu không lấy được cookie, hãy đóng hết Edge rồi bấm nút này lại.",
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/tinhoctre-browser/cookie")
def api_tinhoctre_browser_cookie():
    try:
        cookie = cookie_from_tinhoctre_debug_browser()
        save_tinhoctre_cookie(cookie)
        s = session_from_cookie(cookie)
        check = s.get("https://tinhoctre.vn/admin/judge/problem/add/", timeout=30)
        if not check.ok or not is_problem_add_form(check.text):
            raise RuntimeError(tinhoctre_admin_cookie_error(check.url))
        return jsonify({"ok": True, "cookie": cookie, "message": "Đã lấy Cookie TinHocTre từ Edge và kiểm tra mở được form admin tạo bài."})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/tinhoctre-browser/quick-cookie")
def api_tinhoctre_browser_quick_cookie():
    try:
        stop_edge_processes()
        time.sleep(1)
        chrome = find_edge_executable()
        port = int(os.getenv("TINHOCTRE_CHROME_DEBUG_PORT", "9223"))
        url = "https://tinhoctre.vn/admin/judge/problem/add/"
        subprocess.Popen(
            [
                str(chrome),
                f"--remote-debugging-port={port}",
                "--remote-debugging-address=127.0.0.1",
                "--remote-allow-origins=*",
                "--profile-directory=Default",
                "--new-window",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(4)
        cookie = cookie_from_tinhoctre_debug_browser()
        save_tinhoctre_cookie(cookie)
        s = session_from_cookie(cookie)
        check = s.get(url, timeout=30)
        if not check.ok or not is_problem_add_form(check.text):
            raise RuntimeError(tinhoctre_admin_cookie_error(check.url))
        return jsonify({"ok": True, "cookie": cookie, "message": "Đã tự đóng/mở Edge, lấy Cookie TinHocTre và kiểm tra mở được form admin tạo bài."})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/prepare-upload")
def api_prepare_upload():
    progress_id = None
    try:
        payload = upload_payload()
        progress_id = payload.get("progress_id")
        prepare_id = uuid.uuid4().hex
        root = RUNTIME / prepare_id
        source_dir = root / "source"
        build_root = root / "generated"
        root.mkdir(parents=True, exist_ok=True)
        build_root.mkdir(parents=True, exist_ok=True)
        source_path = receive_upload_source_file(root, payload)
        if source_path.suffix.lower() == ".md":
            source_dir.mkdir(parents=True, exist_ok=True)
            bundles = split_combined_markdown_bundles(source_path, source_dir)
            tests: dict[str, GeneratedTests | None] = {bundle.code: None for bundle in bundles}
            source_name = source_path.name
            log_lines = [f"Đã đọc {len(bundles)} bài từ file Markdown {source_name}."]
        else:
            extract_zip(source_path, source_dir)
            bundles = discover_bundles(source_dir)
            tests = {}
            source_name = source_path.name
            log_lines = [f"Đã đọc {len(bundles)} bài từ {source_name}."]
        rows = []
        progress_update(progress_id, phase="prepare-upload", done=0, total=len(bundles), rows=rows, message="Bắt đầu chuẩn bị dữ liệu")
        for index, bundle in enumerate(bundles, 1):
            generated = tests.get(bundle.code)
            source = "Markdown tổng hợp"
            if bundle.generator or bundle.test_zip:
                generated = generate_tests(bundle, build_root)
                tests[bundle.code] = generated
                source = "gentest" if bundle.generator else "zip có sẵn"
            rows.append(
                {
                    "original_code": bundle.code,
                    "code": bundle.code,
                    "name": bundle.name,
                    "test_file": generated.zip_path.name if generated else "Không có test",
                    "test_count": len(generated.input_files) if generated else 0,
                    "upload_tests_default": bool(generated),
                }
            )
            test_text = f"{len(generated.input_files)} test" if generated else "không có test"
            log_lines.append(f"- {bundle.code}: {bundle.name}, {test_text}, nguồn {source}.")
            progress_update(progress_id, phase="prepare-upload", done=index, total=len(bundles), rows=rows, message=f"{bundle.code}: đã chuẩn bị {test_text}")
        prepared_uploads[prepare_id] = {"root": root, "bundles": {b.code: b for b in bundles}, "tests": tests}
        progress_finish(progress_id, True, f"Đã chuẩn bị {len(bundles)}/{len(bundles)} bài")
        return jsonify({"prepare_id": prepare_id, "rows": rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return jsonify({"error": str(exc)}), 400


def upload_payload() -> dict:
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        raw = request.form.get("payload", "{}")
        return json.loads(raw)
    return request.get_json(force=True)


def receive_upload_source_file(root: Path, payload: dict) -> Path:
    uploaded = request.files.get("zip_file")
    if uploaded:
        original = Path(uploaded.filename or "uploaded_package.zip")
        suffix = original.suffix.lower() if original.suffix.lower() in {".zip", ".md"} else ".zip"
        upload_path = root / f"uploaded_package{suffix}"
        uploaded.save(upload_path)
        return upload_path
    source_path = Path(payload["zip_path"])
    if not source_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {source_path}")
    if source_path.suffix.lower() not in {".zip", ".md"}:
        raise RuntimeError("Chỉ hỗ trợ file .zip hoặc file Markdown .md.")
    return source_path


def split_combined_markdown_bundles(markdown_path: Path, source_dir: Path) -> list[ProblemBundle]:
    text = markdown_path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^#\s*(?:Bài\s+(\d+)\.\s*)?(.+?)\s*\|\s*([A-Za-z0-9_-]+)\s*$", text))
    if not matches:
        raise RuntimeError("Không tìm thấy bài nào. Mỗi bài cần bắt đầu dạng: # Bài 1. Tên bài | ma_bai")
    bundles: list[ProblemBundle] = []
    seen: set[str] = set()
    for idx, match in enumerate(matches):
        number = int(match.group(1) or idx + 1)
        name = match.group(2).strip()
        code = match.group(3).strip()
        if code in seen:
            raise RuntimeError(f"Mã bài bị trùng trong file Markdown: {code}")
        seen.add(code)
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        statement_path = source_dir / f"{number}_{code}.md"
        statement_path.write_text(f"{name} | {code}\n\n{body}\n", encoding="utf-8")
        bundles.append(ProblemBundle(number, code, name, statement_path, None, None, None, None))
    return bundles


@app.post("/api/confirm-upload")
def api_confirm_upload():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id") or payload.get("settings", {}).get("progress_id")
    try:
        prepare_id = payload.get("prepare_id")
        if not prepare_id or prepare_id not in prepared_uploads:
            return jsonify(
                {
                    "ok": False,
                    "error": "Dữ liệu chuẩn bị đã hết hạn hoặc server vừa khởi động lại. Hãy bấm Chuẩn bị dữ liệu lại rồi mới Xác nhận Up bài.",
                }
            ), 400
        state = prepared_uploads[prepare_id]
        target = payload["settings"]["target"]
        result_rows, log_lines = upload_rows(target, payload["settings"], payload["rows"], state, progress_id)
        ok = all((not row.get("selected")) or row["status"].startswith("✓") for row in result_rows)
        progress_finish(progress_id, ok, "Đã hoàn tất up bài")
        return jsonify({"ok": ok, "rows": result_rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400


def upload_rows(target: str, settings: dict, rows: list[dict], state: dict, progress_id: str | None = None) -> tuple[list[dict], list[str]]:
    target_info = TARGETS[target]
    log_lines = [f"Đích: {target_info['label']}", "Tạo bài qua admin form: /admin/judge/problem/add/"]
    selected_language_ids = language_ids_for_target(target, settings.get("languages", []))
    if not selected_language_ids:
        log_lines.append("Ngôn ngữ cho phép: form/admin hiện tại không có ID tương ứng, backend bỏ qua an toàn.")
    if settings.get("creator"):
        log_lines.append("Creators được hiển thị trên giao diện; backend chỉ set nếu form admin hỗ trợ trực tiếp.")

    session = login_upload_target(target, target_info, settings)
    result_rows = []
    total = len([row for row in rows if row.get("selected")])
    done = 0
    progress_update(progress_id, phase="confirm-upload", done=done, total=total, rows=result_rows, message="Bắt đầu up bài")
    for row in rows:
        row = dict(row)
        if not row.get("selected"):
            row["status"] = "Bỏ qua"
            result_rows.append(row)
            continue
        try:
            bundle = replace(state["bundles"][row["original_code"]], code=row["code"], name=row["name"])
            tests = state["tests"].get(row["original_code"])
            upload_one_problem(session, target, target_info, bundle, tests, row, settings, selected_language_ids, log_lines)
            row["status"] = "✓ Thành công"
            row["link"] = problem_url(target_info["base_url"], bundle.code)
        except ProblemAlreadyExists as exc:
            row["status"] = "✗ Bài đã tồn tại"
            log_lines.append(f"✗ {row.get('code')}: {exc}. Bỏ qua bài này và tiếp tục các bài khác.")
        except Exception as exc:
            row["status"] = "✗ Lỗi"
            log_lines.append(f"✗ {row.get('code')}: {exc}")
        result_rows.append(row)
        done += 1
        progress_update(progress_id, phase="confirm-upload", done=done, total=total, rows=result_rows, message=f"{row.get('code')}: {row.get('status')}")
    return result_rows, log_lines


def login_upload_target(target: str, target_info: dict, settings: dict):
    saved_cookie = (settings.get("cookie") or "").strip() or (load_tinhoctre_cookie() if target == "tinhoctre" else "")
    if target == "tinhoctre" and saved_cookie:
        s = session_from_cookie(saved_cookie)
        check = s.get(urljoin(target_info["base_url"], "/admin/judge/problem/add/"), timeout=30)
        if check.ok and is_problem_add_form(check.text):
            return s
        raise RuntimeError(
            tinhoctre_admin_cookie_error(check.url)
        )
    try:
        return login_hncode(target_info["base_url"], settings.get("username", ""), settings.get("password", ""))
    except Exception as exc:
        label = target_info.get("label", target)
        message = str(exc).replace("HNCode", label)
        if target == "tinhoctre":
            message += (
                ". Nếu TinHocTre đang bật WAF/challenge, hãy dán Cookie TinHocTre ở tab Tài khoản "
                "rồi bấm Lưu tạm trước khi Up bài."
            )
        raise RuntimeError(message)


def is_problem_add_form(page: str) -> bool:
    return bool(
        re.search(r"<input\b[^>]*name=[\"']code[\"']", page, re.S)
        and re.search(r"<textarea\b[^>]*name=[\"']description[\"']", page, re.S)
    )


def tinhoctre_admin_cookie_error(final_url: str = "") -> str:
    suffix = f" URL hiện tại: {final_url}" if final_url else ""
    return (
        "Cookie TinHocTre chưa vào được form admin tạo bài. "
        "Có thể bạn copy cookie khi chưa đăng nhập admin, cookie đã hết hạn, hoặc tài khoản không có quyền staff/admin. "
        "Hãy mở https://tinhoctre.vn/admin/judge/problem/add/ trên cùng trình duyệt, đảm bảo thấy form tạo bài, "
        "rồi copy lại Request Header Cookie và dán vào tab Tài khoản."
        + suffix
    )


def upload_one_problem(
    session,
    target: str,
    target_info: dict,
    bundle: ProblemBundle,
    tests: GeneratedTests | None,
    row: dict,
    settings: dict,
    language_ids: list[str],
    log_lines: list[str],
) -> None:
    base_url = target_info["base_url"]
    exists = problem_exists_for_target(session, target, base_url, bundle.code)
    if exists:
        raise ProblemAlreadyExists(f"Mã bài {bundle.code} đã tồn tại tại {problem_url(base_url, bundle.code)}")
    if row.get("upload_statement"):
        info = ProblemInfo(
            code=bundle.code,
            name=bundle.name,
            description=statement_for_target(
                target,
                bundle.statement.read_text(encoding="utf-8", errors="replace"),
                skip_title_line=bool(settings.get("skip_statement_title", True)),
            ),
            points="100",
            partial=True,
            time_limit=settings.get("time_limit") or "1.0",
            memory_limit=settings.get("memory_limit") or "1048576",
            memory_unit="KB",
        )
        change_url = create_hncode_problem(
            session,
            base_url,
            info,
            dest_code=bundle.code,
            type_id=target_info["type_id"],
            group_id=target_info["group_id"],
            public=False,
            allow_all_languages=False,
            allowed_language_ids=language_ids,
        ) if target != "tinhoctre" else create_tinhoctre_admin_problem(
            session,
            base_url,
            info,
            dest_code=bundle.code,
            type_id=target_info["type_id"],
            group_id=target_info["group_id"],
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{bundle.code}: đã tạo đề qua admin form ({change_url}).")
    else:
        log_lines.append(f"{bundle.code}: không upload đề.")

    if row.get("upload_tests"):
        if tests is None:
            raise RuntimeError("Bài này không có bộ test trong dữ liệu chuẩn bị. Hãy bỏ tích Up test hoặc dùng file zip/gentest.")
        upload_tests_for_target(session, target, base_url, bundle.code, tests)
        log_lines.append(f"{bundle.code}: đã upload {len(tests.input_files)} test.")
    else:
        log_lines.append(f"{bundle.code}: không upload test.")

    submit_if_requested(session, base_url, bundle, settings, log_lines)


def problem_exists_for_target(session, target: str, base_url: str, code: str) -> bool:
    if target == "tinhoctre":
        return tinhoctre_problem_exists(session, base_url, code)
    return destination_problem_exists(session, base_url, code)


def statement_for_target(target: str, statement: str, *, skip_title_line: bool = False) -> str:
    text = statement_body_text(statement, skip_title_line=skip_title_line) if skip_title_line else clean_statement(statement)
    if target == "hncode":
        return text.replace("~", "$")
    return text.replace("$", "~")


def problem_info_for_target(info: ProblemInfo, target: str) -> ProblemInfo:
    return replace(info, description=statement_for_target(target, info.description))


def create_tinhoctre_admin_problem(
    session,
    base_url: str,
    info: ProblemInfo,
    *,
    dest_code: str,
    type_id: str,
    group_id: str,
    allowed_language_ids: list[str],
) -> str:
    add_url = urljoin(base_url, "/admin/judge/problem/add/")
    page = session.get(add_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"TinHocTre add page failed: HTTP {page.status_code}")
    if not is_problem_add_form(page.text):
        raise RuntimeError(tinhoctre_admin_cookie_error(page.url))
    token = csrf_token(page.text)
    language_ids = [value for value in allowed_language_ids if value]
    data: list[tuple[str, str]] = [
        ("csrfmiddlewaretoken", token),
        ("code", dest_code),
        ("name", info.name),
        ("submission_source_visibility_mode", selected_option_value(page.text, "submission_source_visibility_mode", "F")),
        ("testcase_visibility_mode", selected_option_value(page.text, "testcase_visibility_mode", "O")),
        ("testcase_result_visibility_mode", selected_option_value(page.text, "testcase_result_visibility_mode", "A")),
        ("description", info.description),
        ("pdf_url", ""),
        ("source", ""),
        ("license", selected_option_value(page.text, "license", "")),
        ("og_image", ""),
        ("summary", ""),
        ("types", type_id),
        ("group", group_id),
        ("points", info.points),
        ("time_limit", info.time_limit),
        ("memory_limit", info.memory_limit),
        ("change_message", ""),
        ("language_limits-TOTAL_FORMS", input_value_from_page(page.text, "language_limits-TOTAL_FORMS", "3")),
        ("language_limits-INITIAL_FORMS", input_value_from_page(page.text, "language_limits-INITIAL_FORMS", "0")),
        ("language_limits-MIN_NUM_FORMS", input_value_from_page(page.text, "language_limits-MIN_NUM_FORMS", "0")),
        ("language_limits-MAX_NUM_FORMS", input_value_from_page(page.text, "language_limits-MAX_NUM_FORMS", "1000")),
        ("problemclarification_set-TOTAL_FORMS", input_value_from_page(page.text, "problemclarification_set-TOTAL_FORMS", "0")),
        ("problemclarification_set-INITIAL_FORMS", input_value_from_page(page.text, "problemclarification_set-INITIAL_FORMS", "0")),
        ("problemclarification_set-MIN_NUM_FORMS", input_value_from_page(page.text, "problemclarification_set-MIN_NUM_FORMS", "0")),
        ("problemclarification_set-MAX_NUM_FORMS", input_value_from_page(page.text, "problemclarification_set-MAX_NUM_FORMS", "1000")),
        ("solution-TOTAL_FORMS", input_value_from_page(page.text, "solution-TOTAL_FORMS", "0")),
        ("solution-INITIAL_FORMS", input_value_from_page(page.text, "solution-INITIAL_FORMS", "0")),
        ("solution-MIN_NUM_FORMS", input_value_from_page(page.text, "solution-MIN_NUM_FORMS", "0")),
        ("solution-MAX_NUM_FORMS", input_value_from_page(page.text, "solution-MAX_NUM_FORMS", "1")),
        ("translations-TOTAL_FORMS", input_value_from_page(page.text, "translations-TOTAL_FORMS", "0")),
        ("translations-INITIAL_FORMS", input_value_from_page(page.text, "translations-INITIAL_FORMS", "0")),
        ("translations-MIN_NUM_FORMS", input_value_from_page(page.text, "translations-MIN_NUM_FORMS", "0")),
        ("translations-MAX_NUM_FORMS", input_value_from_page(page.text, "translations-MAX_NUM_FORMS", "1000")),
        ("_continue", "Save and continue editing"),
    ]
    if input_checked(page.text, "allow_judging"):
        data.append(("allow_judging", "on"))
    if info.partial:
        data.append(("partial", "on"))
    for value in language_ids:
        data.append(("allowed_languages", value))

    total_language_limits = int(input_value_from_page(page.text, "language_limits-TOTAL_FORMS", "3") or "0")
    for index in range(total_language_limits):
        data.extend(
            [
                (f"language_limits-{index}-id", input_value_from_page(page.text, f"language_limits-{index}-id", "")),
                (f"language_limits-{index}-problem", input_value_from_page(page.text, f"language_limits-{index}-problem", "")),
                (f"language_limits-{index}-language", selected_option_value(page.text, f"language_limits-{index}-language", "")),
                (f"language_limits-{index}-time_limit", input_value_from_page(page.text, f"language_limits-{index}-time_limit", "")),
                (f"language_limits-{index}-memory_limit", input_value_from_page(page.text, f"language_limits-{index}-memory_limit", "")),
            ]
        )

    result = session.post(add_url, data=data, headers={"Referer": add_url}, allow_redirects=True, timeout=30)
    if "/admin/login/" in result.url:
        raise RuntimeError(tinhoctre_admin_cookie_error(result.url))
    if not result.ok:
        errors = form_errors(result.text)
        detail = ("\n" + "\n".join(errors)) if errors else ""
        raise RuntimeError(f"TinHocTre create problem failed: HTTP {result.status_code}{detail}")
    errors = form_errors(result.text)
    if errors:
        raise RuntimeError("TinHocTre create problem form errors:\n" + "\n".join(errors))
    if "/change/" not in result.url and dest_code not in result.text:
        raise RuntimeError(f"TinHocTre did not appear to save {dest_code}; final URL: {result.url}")
    return result.url


def input_value_from_page(page: str, name: str, default: str = "") -> str:
    match = re.search(r"<input\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>", page, re.S)
    if not match:
        return default
    value = re.search(r"value=[\"']([^\"']*)", match.group(0))
    return html.unescape(value.group(1)) if value else default


def input_checked(page: str, name: str) -> bool:
    match = re.search(r"<input\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>", page, re.S)
    return bool(match and re.search(r"\bchecked\b", match.group(0)))


def selected_option_value(page: str, name: str, default: str = "") -> str:
    match = re.search(r"<select\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>(.*?)</select>", page, re.S)
    if not match:
        return default
    options = list(re.finditer(r"<option\b([^>]*)>(.*?)</option>", match.group(1), re.S))
    for option in options:
        attrs = option.group(1)
        if "selected" in attrs:
            value = re.search(r"value=[\"']([^\"']*)", attrs)
            return html.unescape(value.group(1)) if value else default
    if options:
        value = re.search(r"value=[\"']([^\"']*)", options[0].group(1))
        return html.unescape(value.group(1)) if value else default
    return default


def upload_tests_for_target(session, target: str, base_url: str, code: str, tests: GeneratedTests) -> None:
    if TARGETS[target]["test_backend"] == "vnoj":
        upload_tinhoctre_tests(session, base_url, code, tests)
        return
    if target == "hnoj":
        upload_tinhoctre_tests(session, base_url, code, tests)
        return
    from upload_hncode_batch import test_cases_from_files

    upload_hncode_tests(session, base_url, code, tests.zip_path, test_cases_from_files(tests.input_files, tests.output_files))


def submit_if_requested(session, base_url: str, bundle: ProblemBundle, settings: dict, log_lines: list[str]) -> None:
    if settings.get("no_submit"):
        log_lines.append(f"{bundle.code}: không nộp bài chấm thử theo lựa chọn.")
        return
    if settings.get("submit_cpp"):
        if bundle.solution_cpp:
            try:
                submission = submit_solution_file(
                    session,
                    base_url,
                    bundle.code,
                    bundle.solution_cpp,
                    ["C++17", "GNU C++17", "C++20", "GNU C++20", "C++"],
                )
                log_lines.append(f"{bundle.code}: đã nộp thử C++ {submission}.")
            except Exception as exc:
                log_lines.append(f"{bundle.code}: không nộp thử C++ được: {exc}")
        else:
            log_lines.append(f"{bundle.code}: không có sol C++, bỏ qua nộp thử C++.")
    if settings.get("submit_python"):
        if bundle.solution:
            try:
                submission = submit_solution_file(
                    session,
                    base_url,
                    bundle.code,
                    bundle.solution,
                    ["PyPy 3", "Pypy 3", "Python 3", "Python3", "Python"],
                )
                log_lines.append(f"{bundle.code}: đã nộp thử Python {submission}.")
            except Exception:
                try:
                    submission = submit_solution(session, base_url, bundle, language_id="17", poll_seconds=0)
                    log_lines.append(f"{bundle.code}: đã nộp thử Python {submission}.")
                except Exception as exc:
                    log_lines.append(f"{bundle.code}: không nộp thử Python được: {exc}")
        else:
            log_lines.append(f"{bundle.code}: không có sol Python, bỏ qua nộp thử Python.")


def submit_solution_file(session, base_url: str, code: str, source_path: Path, preferred_languages: list[str]) -> str:
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
    return result.url


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


def language_ids_for_target(target: str, names: list[str]) -> list[str]:
    mapping = TARGETS[target]["languages"]
    return [mapping[name] for name in names if mapping.get(name)]


def problem_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}")


def normalize_problem_code_for_target(code: str, target: str) -> str:
    code = (code or "").strip().lower()
    if target == "hncode":
        code = re.sub(r"[^a-z0-9]+", "", code)
    return code


def validate_problem_code_for_target(code: str, target: str) -> None:
    if target == "hncode" and not re.fullmatch(r"[a-z0-9]+", code or ""):
        normalized = normalize_problem_code_for_target(code, target)
        hint = f" Gợi ý mã hợp lệ: {normalized}" if normalized else ""
        raise RuntimeError(f"HNCode chỉ cho phép mã bài gồm chữ thường và số (^[a-z0-9]+$).{hint}")


def test_data_url(base_url: str, code: str) -> str:
    return urljoin(base_url, f"/problem/{code}/test_data")


def session_from_cookie(cookie_header: str):
    s = tinhoctre_session()
    parsed = SimpleCookie()
    parsed.load(cookie_header)
    for key, morsel in parsed.items():
        s.cookies.set(key, morsel.value, domain=".tinhoctre.vn")
        s.cookies.set(key, morsel.value, domain="tinhoctre.vn")
    return s


def tinhoctre_cookie_file() -> Path:
    return RUNTIME / "tinhoctre_cookie.txt"


def save_tinhoctre_cookie(cookie_header: str) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    tinhoctre_cookie_file().write_text(cookie_header, encoding="utf-8")


def load_tinhoctre_cookie() -> str:
    path = tinhoctre_cookie_file()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def find_edge_executable() -> Path:
    candidates = [
        shutil.which("msedge"),
        shutil.which("msedge.exe"),
        os.environ.get("EDGE_PATH"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    raise RuntimeError("Không tìm thấy Edge/Chrome trên máy local. Hãy cài Edge hoặc đặt biến môi trường EDGE_PATH.")


def stop_edge_processes() -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/IM", "msedge.exe", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    subprocess.run(["pkill", "-f", "msedge"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cdp_json(path: str, port: int) -> dict:
    with urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def cookie_from_tinhoctre_debug_browser() -> str:
    try:
        import websocket
    except Exception as exc:
        raise RuntimeError("Thiếu thư viện websocket-client để đọc cookie Edge. Hãy cài: pip install websocket-client") from exc

    port = int(os.getenv("TINHOCTRE_CHROME_DEBUG_PORT", "9223"))
    deadline = time.time() + 20
    last_error: Exception | None = None
    version = None
    while time.time() < deadline:
        try:
            version = cdp_json("/json/version", port)
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    if not version:
        raise RuntimeError(f"Không kết nối được Edge đăng nhập TinHocTre ở cổng {port}. Hãy đóng hết Edge, rồi bấm Mở Edge đăng nhập TinHocTre trước.") from last_error

    ws_url = version.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("Edge DevTools không trả webSocketDebuggerUrl.")
    ws = websocket.create_connection(ws_url, timeout=10)
    counter = 0

    def cdp(method: str, params: dict | None = None):
        nonlocal counter
        counter += 1
        ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
        while True:
            message = json.loads(ws.recv())
            if message.get("id") == counter:
                if "error" in message:
                    raise RuntimeError(message["error"].get("message", str(message["error"])))
                return message.get("result", {})

    try:
        try:
            result = cdp("Network.getAllCookies")
            cookies = result.get("cookies", [])
        except Exception:
            result = cdp("Storage.getCookies")
            cookies = result.get("cookies", [])
    finally:
        ws.close()

    useful = []
    for cookie in cookies:
        domain = cookie.get("domain", "")
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        if "tinhoctre.vn" in domain and name and value:
            useful.append((name, value))
    if not useful:
        raise RuntimeError("Không thấy cookie tinhoctre.vn trong Edge. Hãy đăng nhập TinHocTre admin trong cửa sổ Edge vừa mở rồi thử lại.")

    priority = {"cf_clearance": 0, "aws-waf-token": 1, "csrftoken": 2, "sessionid": 3}
    useful.sort(key=lambda item: (priority.get(item[0], 50), item[0]))
    return "; ".join(f"{name}={value}" for name, value in useful)


def login_tinhoctre_source(account: dict, first_code: str):
    base_url = TARGETS["tinhoctre"]["base_url"]
    cookie_header = (account.get("cookie") or "").strip() or load_tinhoctre_cookie()
    if cookie_header:
        s = session_from_cookie(cookie_header)
        check = s.get(urljoin(base_url, f"/problem/{first_code}/edit"), timeout=30)
        if check.ok and (f'name="code"' in check.text or "name='code'" in check.text):
            return s
        raise RuntimeError(
            "Cookie TinHocTre chưa dùng được để đọc trang sửa bài. "
            "Hãy copy lại Cookie sau khi đã đăng nhập đúng tài khoản trên tinhoctre.vn."
        )
    try:
        return login_tinhoctre_public(base_url, account.get("username", ""), account.get("password", ""), "/problems/create")
    except Exception as exc:
        message = str(exc)
        if "csrf" in message.lower() or "login page failed" in message.lower():
            raise RuntimeError(
                "TinHocTre không trả form đăng nhập cho tool vì WAF/challenge nên không lấy được CSRF. "
                "Cách xử lý nhanh: đăng nhập tinhoctre.vn trên trình duyệt, copy Request Header Cookie và dán vào ô Cookie TinHocTre trong tab Tài khoản."
            ) from exc
        raise


def login_problem_source(target: str, account: dict, first_code: str):
    base_url = TARGETS[target]["base_url"]
    username = account.get("username", "")
    password = account.get("password", "")
    if target == "tinhoctre":
        return login_tinhoctre_source(account, first_code)
    if target == "tinhoctre":
        try:
            return login_tinhoctre_public(base_url, username, password, "/problems/create")
        except Exception as exc:
            message = str(exc)
            if "csrf" in message.lower() or "login page failed" in message.lower():
                raise RuntimeError(
                    "TinHocTre không trả form đăng nhập cho tool. "
                    "Trang có thể đang bật WAF/challenge nên tool không lấy được CSRF. "
                    "Hãy thử lại sau ít phút; nếu vẫn lỗi, cần whitelist IP VPS/tool hoặc tắt challenge cho /accounts/login/."
                ) from exc
            raise
    return login_hncode(base_url, username, password)


def contest_url(base_url: str, key: str) -> str:
    return urljoin(base_url, f"/contest/{key}")


def admin_contest_change_url(session, base_url: str, key: str) -> str | None:
    page = session.get(urljoin(base_url, "/admin/judge/contest/"), params={"q": key})
    if not page.ok:
        return None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page.text, re.S):
        plain = html.unescape(re.sub(r"<.*?>", " ", row))
        if re.search(rf"\b{re.escape(key)}\b", plain):
            link = re.search(r'href="(/admin/judge/contest/\d+/change/[^"]*)"', row)
            if link:
                return urljoin(base_url, html.unescape(link.group(1)))
    return None


def admin_problem_id(session, base_url: str, code: str) -> str | None:
    page = session.get(urljoin(base_url, "/admin/judge/problem/"), params={"q": code})
    if not page.ok:
        return None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page.text, re.S):
        code_match = re.search(r'<th class="field-code">\s*<a href="/admin/judge/problem/(\d+)/change/[^"]*">\s*([^<]+)\s*</a>', row)
        if code_match and html.unescape(code_match.group(2)).strip() == code:
            return code_match.group(1)
    return None


def public_contest_problem_codes(session, base_url: str, key: str) -> list[str]:
    page = session.get(contest_url(base_url, key))
    if not page.ok:
        return []
    codes: list[str] = []
    for code in re.findall(r"/problem/([A-Za-z0-9_-]+)", page.text):
        if code not in codes:
            codes.append(code)
    return codes


def problem_has_test_zip(session, base_url: str, code: str) -> bool:
    page = session.get(test_data_url(base_url, code))
    return page.ok and bool(re.search(r'href=[\"\'][^\"\']+\.zip[\"\']', page.text))


def upload_existing_problem_tests(session, dest: str, code: str, zip_path: Path, cases) -> None:
    base_url = TARGETS[dest]["base_url"]
    if dest == "hnoj":
        tests = GeneratedTests(zip_path, [case.input_file for case in cases], [case.output_file for case in cases])
        upload_tinhoctre_tests(session, base_url, code, tests)
    elif dest == "tinhoctre":
        tests = GeneratedTests(zip_path, [case.input_file for case in cases], [case.output_file for case in cases])
        upload_tinhoctre_tests(session, base_url, code, tests)
    else:
        upload_hncode_tests(session, base_url, code, zip_path, cases)


def selected_values(page: str, name: str) -> list[str]:
    match = re.search(r"<select\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>(.*?)</select>", page, re.S)
    if not match:
        return []
    values = []
    for option in re.finditer(r"<option\b([^>]*)>", match.group(1), re.S):
        attrs = option.group(1)
        if "selected" not in attrs:
            continue
        value = re.search(r"value=[\"']([^\"']*)", attrs)
        if value:
            values.append(html.unescape(value.group(1)))
    return values


def select_option_values(page: str, name: str) -> list[str]:
    match = re.search(r"<select\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>(.*?)</select>", page, re.S)
    if not match:
        return []
    values = []
    for option in re.finditer(r"<option\b([^>]*)>", match.group(1), re.S):
        value = re.search(r"value=[\"']([^\"']*)", option.group(1))
        if value:
            values.append(html.unescape(value.group(1)))
    return values


def valid_select_value(page: str, name: str, wanted: str, default: str = "") -> str:
    values = select_option_values(page, name)
    if wanted and wanted in values:
        return wanted
    selected = selected_option(page, name, "")
    if selected:
        return selected
    if default and default in values:
        return default
    return values[0] if values else wanted


class FormDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[list[tuple[str, str]]] = []
        self.current: list[tuple[str, str]] | None = None
        self.select: dict | None = None
        self.textarea: dict | None = None

    @staticmethod
    def attrs_dict(attrs) -> dict[str, str]:
        return {str(k): "" if v is None else str(v) for k, v in attrs}

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_map = self.attrs_dict(attrs)
        if tag == "form":
            self.current = []
            return
        if self.current is None:
            return
        if tag == "input":
            name = attrs_map.get("name", "")
            if not name or attrs_map.get("disabled") is not None:
                return
            input_type = attrs_map.get("type", "text").lower()
            if input_type in {"file", "submit", "button", "image", "reset"}:
                return
            if input_type in {"checkbox", "radio"}:
                if "checked" in attrs_map:
                    self.current.append((name, attrs_map.get("value") or "on"))
                return
            self.current.append((name, attrs_map.get("value", "")))
            return
        if tag == "select":
            name = attrs_map.get("name", "")
            self.select = {
                "name": name,
                "multiple": "multiple" in attrs_map,
                "disabled": "disabled" in attrs_map,
                "options": [],
            }
            return
        if tag == "option" and self.select is not None:
            self.select["options"].append(
                {
                    "value": attrs_map.get("value", ""),
                    "selected": "selected" in attrs_map,
                }
            )
            return
        if tag == "textarea":
            name = attrs_map.get("name", "")
            self.textarea = {"name": name, "disabled": "disabled" in attrs_map, "parts": []}

    def handle_data(self, data: str) -> None:
        if self.textarea is not None:
            self.textarea["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None
            return
        if self.current is None:
            return
        if tag == "select" and self.select is not None:
            name = self.select.get("name", "")
            if name and not self.select.get("disabled"):
                options = self.select.get("options") or []
                selected = [option for option in options if option.get("selected")]
                if not selected and not self.select.get("multiple") and options:
                    selected = [options[0]]
                for option in selected:
                    self.current.append((name, str(option.get("value", ""))))
            self.select = None
            return
        if tag == "textarea" and self.textarea is not None:
            name = self.textarea.get("name", "")
            if name and not self.textarea.get("disabled"):
                self.current.append((str(name), "".join(self.textarea.get("parts") or [])))
            self.textarea = None


def collect_contest_form_data(page: str) -> list[tuple[str, str]]:
    parser = FormDataParser()
    parser.feed(page)
    for form in parser.forms:
        if any(name == "contest_problems-TOTAL_FORMS" for name, _value in form):
            return form
    return []


def remove_contest_problem_fields(data: list[tuple[str, str]]) -> list[tuple[str, str]]:
    prefixes = (
        "contest_problems-",
        "contest_problems-TOTAL_FORMS",
        "contest_problems-INITIAL_FORMS",
        "contest_problems-MIN_NUM_FORMS",
        "contest_problems-MAX_NUM_FORMS",
    )
    return [(name, value) for name, value in data if not any(name.startswith(prefix) for prefix in prefixes)]


def clean_contest_base_field(name: str, value: str) -> str:
    if name in {"format_config", "problem_label_script", "summary"} and not str(value).strip():
        return ""
    return value


def form_has_field(page: str, name: str) -> bool:
    return bool(re.search(r'\bname=["\']' + re.escape(name) + r'["\']', page))


def select2_field_id(page: str, name: str) -> str:
    match = re.search(r'name="' + re.escape(name) + r'"[^>]*data-field_id="([^"]+)"', page)
    return html.unescape(match.group(1)) if match else ""


def profile_id_for_username(session, base_url: str, page: str, username: str) -> str:
    field_id = select2_field_id(page, "authors")
    if not field_id or not username:
        return ""
    result = session.get(
        urljoin(base_url, "/judge-select2/profile/"),
        params={"field_id": field_id, "term": username, "page": 1},
        headers={"Referer": urljoin(base_url, "/admin/judge/contest/add/"), "X-Requested-With": "XMLHttpRequest"},
    )
    if not result.ok:
        return ""
    try:
        data = result.json()
    except json.JSONDecodeError:
        return ""
    fallback = ""
    for item in data.get("results", []):
        text = str(item.get("text", ""))
        value = str(item.get("id", ""))
        if text == username:
            return value
        if not fallback:
            fallback = value
    return fallback


def split_datetime(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    if " " in value:
        date, time = value.split(" ", 1)
        return date.strip(), time.strip()
    return value, ""


def fetch_contest_info(session, base_url: str, key: str) -> dict:
    change_url = admin_contest_change_url(session, base_url, key)
    if not change_url:
        raise RuntimeError(f"Không tìm thấy contest {key} trong admin.")
    page = session.get(change_url)
    if not page.ok:
        raise RuntimeError(f"Không đọc được trang sửa contest {key}: HTTP {page.status_code}")
    problem_codes = public_contest_problem_codes(session, base_url, key)
    total = int(input_value(page.text, "contest_problems-TOTAL_FORMS", "0") or "0")
    entries = []
    order_rows = []
    for idx in range(total):
        problem_id = input_value(page.text, f"contest_problems-{idx}-problem")
        if not problem_id:
            continue
        order_rows.append(
            {
                "idx": idx,
                "problem_id": problem_id,
                "points": input_value(page.text, f"contest_problems-{idx}-points", "100") or "100",
                "partial": checkbox_checked(page.text, f"contest_problems-{idx}-partial"),
                "is_pretested": checkbox_checked(page.text, f"contest_problems-{idx}-is_pretested"),
                "max_submissions": input_value(page.text, f"contest_problems-{idx}-max_submissions", ""),
                "order": input_value(page.text, f"contest_problems-{idx}-order", str(idx)) or str(idx),
            }
        )
    for row, code in zip(order_rows, problem_codes):
        row["code"] = code
        entries.append(row)
    if not entries and problem_codes:
        entries = [{"code": code, "points": "100", "partial": True, "is_pretested": False, "max_submissions": "", "order": str(i)} for i, code in enumerate(problem_codes)]
    start_time = f"{input_value(page.text, 'start_time_0', '')} {input_value(page.text, 'start_time_1', '')}".strip()
    end_time = f"{input_value(page.text, 'end_time_0', '')} {input_value(page.text, 'end_time_1', '')}".strip()
    return {
        "key": input_value(page.text, "key", key) or key,
        "name": input_value(page.text, "name", key) or key,
        "description": textarea_value(page.text, "description"),
        "start_time": start_time,
        "end_time": end_time,
        "format_name": selected_option(page.text, "format_name", "vnoj") or "vnoj",
        "scoreboard_visibility": selected_option(page.text, "scoreboard_visibility", "H") or "H",
        "points_precision": input_value(page.text, "points_precision", "3") or "3",
        "is_visible": checkbox_checked(page.text, "is_visible"),
        "is_rated": checkbox_checked(page.text, "is_rated"),
        "is_private": checkbox_checked(page.text, "is_private"),
        "problems": entries,
        "change_url": change_url,
    }


def build_contest_post_data(page: str, info: dict, problem_ids: list[dict], dest: str, author_ids: list[str] | None = None) -> list[tuple[str, str]]:
    start_date, start_clock = split_datetime(info.get("start_time", ""))
    end_date, end_clock = split_datetime(info.get("end_time", ""))
    scoreboard_visibility = valid_select_value(page, "scoreboard_visibility", info.get("scoreboard_visibility") or "", "V")
    format_name = valid_select_value(page, "format_name", info.get("format_name") or "", "vnoj")
    data: list[tuple[str, str]] = [
        ("csrfmiddlewaretoken", csrf_token(page)),
        ("key", info["key"]),
        ("name", info["name"]),
        ("description", statement_for_target(dest, info.get("description", ""))),
        ("scoreboard_visibility", scoreboard_visibility),
        ("points_precision", info.get("points_precision") or "3"),
        ("start_time_0", start_date),
        ("start_time_1", start_clock),
        ("end_time_0", end_date),
        ("end_time_1", end_clock),
        ("time_limit", info.get("time_limit", "")),
        ("format_name", format_name),
        ("format_config", info.get("format_config", "")),
        ("frozen_last_minutes", info.get("frozen_last_minutes", "0") or "0"),
        ("rate_limit", info.get("rate_limit", "")),
        ("freeze_after", info.get("freeze_after", "")),
        ("problem_label_script", info.get("problem_label_script", "")),
        ("rating_floor", info.get("rating_floor", "")),
        ("rating_ceiling", info.get("rating_ceiling", "")),
        ("access_code", info.get("access_code", "")),
        ("ranking_access_code", info.get("ranking_access_code", "")),
        ("scoreboard_cache_timeout", info.get("scoreboard_cache_timeout", "0") or "0"),
        ("summary", info.get("summary", "")),
        ("og_image", ""),
        ("logo_override_image", ""),
        ("contest_problems-TOTAL_FORMS", str(len(problem_ids))),
        ("contest_problems-INITIAL_FORMS", "0"),
        ("contest_problems-MIN_NUM_FORMS", "0"),
        ("contest_problems-MAX_NUM_FORMS", "1000"),
        ("contestannouncement_set-TOTAL_FORMS", "0"),
        ("contestannouncement_set-INITIAL_FORMS", "0"),
        ("contestannouncement_set-MIN_NUM_FORMS", "0"),
        ("contestannouncement_set-MAX_NUM_FORMS", "1000"),
        ("official-TOTAL_FORMS", "0"),
        ("official-INITIAL_FORMS", "0"),
        ("official-MIN_NUM_FORMS", "0"),
        ("official-MAX_NUM_FORMS", "1000"),
        ("_continue", "Save and continue editing"),
    ]
    authors = author_ids if author_ids is not None else selected_values(page, "authors")
    data.extend(("authors", value) for value in authors if value)
    if info.get("is_visible", True):
        data.append(("is_visible", "on"))
    for flag in [
        "use_clarifications",
        "push_announcements",
        "hide_problem_tags",
        "hide_problem_authors",
        "show_short_display",
        "show_submission_list",
        "public_scoreboard",
        "run_pretests_only",
        "rate_all",
    ]:
        if info.get(flag):
            data.append((flag, "on"))
    if info.get("is_rated"):
        data.append(("is_rated", "on"))
    if info.get("is_private"):
        data.append(("is_private", "on"))
    has_quiz = form_has_field(page, "contest_problems-0-quiz") or form_has_field(page, "contest_problems-__prefix__-quiz")
    has_result_hidden = form_has_field(page, "contest_problems-0-is_result_hidden") or form_has_field(page, "contest_problems-__prefix__-is_result_hidden")
    has_show_testcases = form_has_field(page, "contest_problems-0-show_testcases") or form_has_field(page, "contest_problems-__prefix__-show_testcases")
    for idx, problem in enumerate(problem_ids):
        data.extend(
            [
                (f"contest_problems-{idx}-id", ""),
                (f"contest_problems-{idx}-contest", ""),
                (f"contest_problems-{idx}-problem", str(problem["id"])),
                (f"contest_problems-{idx}-points", str(problem.get("points") or "100")),
                (f"contest_problems-{idx}-max_submissions", contest_max_submissions_value(problem, dest)),
                (f"contest_problems-{idx}-hidden_subtasks", str(problem.get("hidden_subtasks") or "")),
                (f"contest_problems-{idx}-output_prefix_override", ""),
                (f"contest_problems-{idx}-order", str(problem.get("order", idx))),
            ]
        )
        if has_quiz:
            data.append((f"contest_problems-{idx}-quiz", str(problem.get("quiz") or "")))
        if problem.get("partial", True):
            data.append((f"contest_problems-{idx}-partial", "on"))
        if problem.get("is_pretested"):
            data.append((f"contest_problems-{idx}-is_pretested", "on"))
        if has_result_hidden and problem.get("is_result_hidden"):
            data.append((f"contest_problems-{idx}-is_result_hidden", "on"))
        if has_show_testcases and problem.get("show_testcases"):
            data.append((f"contest_problems-{idx}-show_testcases", "on"))
    return data


def existing_contest_problem_rows(page: str) -> list[dict]:
    total = int(input_value(page, "contest_problems-TOTAL_FORMS", "0") or "0")
    initial = int(input_value(page, "contest_problems-INITIAL_FORMS", "0") or "0")
    rows: list[dict] = []
    for idx in range(initial):
        problem_id = selected_option(page, f"contest_problems-{idx}-problem", "") or input_value(page, f"contest_problems-{idx}-problem", "")
        if not problem_id:
            continue
        rows.append(
            {
                "form_id": input_value(page, f"contest_problems-{idx}-id", ""),
                "contest": input_value(page, f"contest_problems-{idx}-contest", ""),
                "id": problem_id,
                "quiz": selected_option(page, f"contest_problems-{idx}-quiz", "") or input_value(page, f"contest_problems-{idx}-quiz", ""),
                "points": input_value(page, f"contest_problems-{idx}-points", "100") or "100",
                "partial": checkbox_checked(page, f"contest_problems-{idx}-partial"),
                "is_pretested": checkbox_checked(page, f"contest_problems-{idx}-is_pretested"),
                "is_result_hidden": checkbox_checked(page, f"contest_problems-{idx}-is_result_hidden"),
                "show_testcases": checkbox_checked(page, f"contest_problems-{idx}-show_testcases"),
                "max_submissions": input_value(page, f"contest_problems-{idx}-max_submissions", ""),
                "hidden_subtasks": input_value(page, f"contest_problems-{idx}-hidden_subtasks", ""),
                "output_prefix_override": input_value(page, f"contest_problems-{idx}-output_prefix_override", ""),
                "order": input_value(page, f"contest_problems-{idx}-order", str(idx)) or str(idx),
            }
        )
    return rows


def contest_max_submissions_value(problem: dict, dest: str) -> str:
    value = problem.get("max_submissions")
    if value not in (None, ""):
        return str(value)
    return "0" if dest == "hncode" else ""


def append_contest_problem_fields(data: list[tuple[str, str]], page: str, rows: list[dict], initial_forms: int, dest: str) -> None:
    data.extend(
        [
            ("contest_problems-TOTAL_FORMS", str(len(rows))),
            ("contest_problems-INITIAL_FORMS", str(initial_forms)),
            ("contest_problems-MIN_NUM_FORMS", "0"),
            ("contest_problems-MAX_NUM_FORMS", "1000"),
        ]
    )
    has_quiz = form_has_field(page, "contest_problems-0-quiz") or form_has_field(page, "contest_problems-__prefix__-quiz")
    has_result_hidden = form_has_field(page, "contest_problems-0-is_result_hidden") or form_has_field(page, "contest_problems-__prefix__-is_result_hidden")
    has_show_testcases = form_has_field(page, "contest_problems-0-show_testcases") or form_has_field(page, "contest_problems-__prefix__-show_testcases")
    for idx, problem in enumerate(rows):
        data.extend(
            [
                (f"contest_problems-{idx}-id", str(problem.get("form_id") or "")),
                (f"contest_problems-{idx}-contest", str(problem.get("contest") or "")),
                (f"contest_problems-{idx}-problem", str(problem["id"])),
                (f"contest_problems-{idx}-points", str(problem.get("points") or "100")),
                (f"contest_problems-{idx}-max_submissions", contest_max_submissions_value(problem, dest)),
                (f"contest_problems-{idx}-hidden_subtasks", str(problem.get("hidden_subtasks") or "")),
                (f"contest_problems-{idx}-output_prefix_override", str(problem.get("output_prefix_override") or "")),
                (f"contest_problems-{idx}-order", str(problem.get("order", idx))),
            ]
        )
        if has_quiz:
            data.append((f"contest_problems-{idx}-quiz", str(problem.get("quiz") or "")))
        if problem.get("partial", True):
            data.append((f"contest_problems-{idx}-partial", "on"))
        if problem.get("is_pretested"):
            data.append((f"contest_problems-{idx}-is_pretested", "on"))
        if has_result_hidden and problem.get("is_result_hidden"):
            data.append((f"contest_problems-{idx}-is_result_hidden", "on"))
        if has_show_testcases and problem.get("show_testcases"):
            data.append((f"contest_problems-{idx}-show_testcases", "on"))


def append_problems_to_existing_contest(session, base_url: str, dest: str, change_url: str, problem_ids: list[dict]) -> str:
    page = session.get(change_url)
    if not page.ok:
        raise RuntimeError(f"Không mở được form sửa contest: HTTP {page.status_code}")
    base_data = remove_contest_problem_fields(collect_contest_form_data(page.text))
    if not base_data:
        raise RuntimeError("Không đọc được form sửa contest để thêm bài.")
    rows = existing_contest_problem_rows(page.text)
    initial_forms = int(input_value(page.text, "contest_problems-INITIAL_FORMS", str(len(rows))) or str(len(rows)))
    existing_ids = {str(row["id"]) for row in rows}
    next_order = max([int(str(row.get("order") or 0)) for row in rows if str(row.get("order") or "").isdigit()] or [-1]) + 1
    added = 0
    for problem in problem_ids:
        problem_id = str(problem["id"])
        if problem_id in existing_ids:
            continue
        item = dict(problem)
        item["form_id"] = ""
        item["contest"] = ""
        item["id"] = problem_id
        item["order"] = str(next_order + added)
        item["max_submissions"] = contest_max_submissions_value(item, dest)
        rows.append(item)
        existing_ids.add(problem_id)
        added += 1
    if not added:
        return change_url
    data = [
        (name, clean_contest_base_field(name, value))
        for name, value in base_data
        if name not in {"_save", "_addanother", "_continue"}
    ]
    append_contest_problem_fields(data, page.text, rows, initial_forms, dest)
    data.append(("_continue", "Save and continue editing"))
    result = session.post(change_url, data=data, headers={"Referer": change_url}, allow_redirects=True)
    if not result.ok:
        raise RuntimeError(f"Thêm bài vào contest lỗi HTTP {result.status_code}")
    errors = form_errors(result.text)
    if errors:
        raise RuntimeError("Form thêm bài vào contest báo lỗi:\n" + "\n".join(errors))
    if "/change/" not in result.url:
        raise RuntimeError(f"Thêm bài vào contest chưa quay lại trang sửa: {result.url}")
    return result.url


def create_contest(session, base_url: str, dest: str, info: dict, problem_ids: list[dict], author_username: str = "") -> str:
    change_url = admin_contest_change_url(session, base_url, info["key"])
    if change_url:
        return append_problems_to_existing_contest(session, base_url, dest, change_url, problem_ids)
    add_url = urljoin(base_url, "/admin/judge/contest/add/")
    page = session.get(add_url)
    if not page.ok:
        raise RuntimeError(f"Không mở được form tạo contest: HTTP {page.status_code}")
    authors = selected_values(page.text, "authors")
    if not authors:
        author_id = profile_id_for_username(session, base_url, page.text, author_username)
        if author_id:
            authors = [author_id]
    result = session.post(add_url, data=build_contest_post_data(page.text, info, problem_ids, dest, authors), headers={"Referer": add_url}, allow_redirects=True)
    if not result.ok:
        raise RuntimeError(f"Tạo contest lỗi HTTP {result.status_code}")
    errors = form_errors(result.text)
    if errors:
        raise RuntimeError("Form tạo contest báo lỗi:\n" + "\n".join(errors))
    if "/change/" not in result.url:
        raise RuntimeError(f"Tạo contest chưa redirect vào trang sửa: {result.url}")
    return result.url


def contest_transfer_root(prepare_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", prepare_id or ""):
        raise RuntimeError("Mã chuẩn bị contest không hợp lệ.")
    return RUNTIME / ("contest_transfer_" + prepare_id)


def save_prepared_contest_transfer(prepare_id: str, state: dict) -> None:
    root = Path(state["root"])
    root.mkdir(parents=True, exist_ok=True)
    disk_state = {
        "root": str(root),
        "source": state["source"],
        "dest": state["dest"],
        "items": state["items"],
    }
    (root / "state.json").write_text(json.dumps(disk_state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_prepared_contest_transfer(prepare_id: str) -> dict | None:
    if prepare_id in prepared_contest_transfers:
        return prepared_contest_transfers[prepare_id]
    root = contest_transfer_root(prepare_id)
    state_file = root / "state.json"
    if not state_file.exists():
        return None
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["root"] = Path(state["root"])
    prepared_contest_transfers[prepare_id] = state
    return state


@app.post("/api/prepare-contest-transfer")
def api_prepare_contest_transfer():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id")
    source = payload["source"]
    dest = payload["dest"]
    codes = [code.strip() for code in payload.get("codes", []) if code.strip()]
    if not codes:
        return jsonify({"error": "Chưa nhập mã contest cần chuyển."}), 400
    if source == dest:
        return jsonify({"error": "Nguồn và đích đang trùng nhau."}), 400
    try:
        prepare_id = uuid.uuid4().hex
        root = RUNTIME / ("contest_transfer_" + prepare_id)
        root.mkdir(parents=True, exist_ok=True)
        source_account = payload["source_account"]
        source_info = CONTEST_TARGETS[source]
        src = login_hncode(source_info["base_url"], source_account["username"], source_account["password"])
        rows = []
        items = {}
        log_lines = [f"Đọc contest nguồn: {source_info['label']} → {TARGETS[dest]['label']}"]
        progress_update(progress_id, phase="prepare-contest-transfer", done=0, total=len(codes), rows=rows, message="Bắt đầu đọc contest nguồn")
        for index, key in enumerate(codes, 1):
            try:
                info = fetch_contest_info(src, source_info["base_url"], key)
                dest_exists = False
                try:
                    dest_account = payload.get("dest_account", {})
                    dst_probe = login_hncode(TARGETS[dest]["base_url"], dest_account.get("username", ""), dest_account.get("password", ""))
                    dest_exists = bool(admin_contest_change_url(dst_probe, TARGETS[dest]["base_url"], info["key"]))
                    for problem in info["problems"]:
                        pid = admin_problem_id(dst_probe, TARGETS[dest]["base_url"], problem["code"])
                        if pid:
                            problem["status"] = "Đã có ở đích, có test" if problem_has_test_zip(dst_probe, TARGETS[dest]["base_url"], problem["code"]) else "Đã có ở đích, thiếu test"
                        else:
                            problem["status"] = "Thiếu ở đích"
                except Exception:
                    dest_exists = False
                items[key] = info
                rows.append(
                    {
                        "original_key": key,
                        "key": info["key"],
                        "name": info["name"],
                        "start_time": info["start_time"],
                        "end_time": info["end_time"],
                        "problems": info["problems"],
                        "can_transfer": not dest_exists,
                        "status": "Đã tồn tại ở đích" if dest_exists else "Đã đọc",
                    }
                )
                log_lines.append(f"- {key}: {info['name']}, {len(info['problems'])} bài")
                if dest_exists:
                    log_lines.append(f"  Contest {info['key']} đã tồn tại ở đích, mặc định bỏ chọn để tránh tạo trùng.")
            except Exception as exc:
                rows.append({"original_key": key, "key": key, "name": "", "start_time": "", "end_time": "", "problems": [], "can_transfer": False, "status": "✗ Lỗi đọc nguồn"})
                log_lines.append(f"✗ {key}: {exc}")
            progress_update(progress_id, phase="prepare-contest-transfer", done=index, total=len(codes), rows=rows, message=f"{key}: {rows[-1]['status']}")
        state = {"root": root, "source": source, "dest": dest, "items": items}
        prepared_contest_transfers[prepare_id] = state
        save_prepared_contest_transfer(prepare_id, state)
        progress_finish(progress_id, True, f"Đã đọc {len(rows)}/{len(codes)} contest")
        return jsonify({"prepare_id": prepare_id, "rows": rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return jsonify({"error": str(exc)}), 400


@app.post("/api/confirm-contest-transfer")
def api_confirm_contest_transfer():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id")
    prepare_id = payload.get("prepare_id")
    state = load_prepared_contest_transfer(prepare_id) if prepare_id else None
    if not state:
        progress_finish(progress_id, False, "Dữ liệu chuẩn bị chuyển contest đã hết hạn")
        return jsonify({"error": "Dữ liệu chuẩn bị chuyển contest đã hết hạn. Hãy bấm Chuẩn bị dữ liệu lại."}), 400
    source = payload["source"]
    dest = payload["dest"]
    settings = payload.get("settings", {})
    rows = payload.get("rows", [])
    result_rows = []
    log_lines = [f"Chuyển contest: {CONTEST_TARGETS[source]['label']} → {TARGETS[dest]['label']}"]
    try:
        source_account = payload["source_account"]
        dest_account = payload["dest_account"]
        src = login_hncode(CONTEST_TARGETS[source]["base_url"], source_account["username"], source_account["password"])
        dst = login_hncode(TARGETS[dest]["base_url"], dest_account["username"], dest_account["password"])
        root = state["root"]
        language_ids = list(TARGETS[dest]["languages"].values())
        total = len([row for row in rows if row.get("selected")])
        done = 0
        progress_update(progress_id, phase="confirm-contest-transfer", done=done, total=total, rows=result_rows, message="Bắt đầu chuyển contest")
        for row in rows:
            row = dict(row)
            if not row.get("selected"):
                row["status"] = "Bỏ qua"
                result_rows.append(row)
                continue
            try:
                info = dict(state["items"].get(row["original_key"]) or {})
                if not info:
                    raise RuntimeError("Chưa đọc được dữ liệu contest nguồn")
                info["key"] = row.get("key") or info["key"]
                info["name"] = row.get("name") or info["name"]
                selected_codes = {problem.get("code") for problem in row.get("problems", []) if problem.get("selected")}
                if row.get("problems"):
                    info["problems"] = [problem for problem in info["problems"] if problem["code"] in selected_codes]
                if not info["problems"]:
                    raise RuntimeError("Chưa chọn bài nào trong contest")
                problem_refs = []
                for problem in info["problems"]:
                    code = problem["code"]
                    pid = admin_problem_id(dst, TARGETS[dest]["base_url"], code)
                    if pid and not settings.get("reuse_existing_problems", True):
                        raise RuntimeError(f"Bài {code} đã có ở đích và tùy chọn dùng lại bài đã có đang tắt")
                    if not pid and not settings.get("create_missing_problems", True):
                        raise RuntimeError(f"Bài {code} chưa có ở đích")
                    if not pid:
                        pinfo, zip_path, cases, _zip_url = fetch_source_problem(src, CONTEST_TARGETS[source]["base_url"], code, root)
                        pinfo.time_limit = pinfo.time_limit or settings.get("time_limit") or "1.0"
                        pinfo.memory_limit = pinfo.memory_limit or settings.get("memory_limit") or "1048576"
                        transfer_row = {"upload_statement": True, "upload_tests": True}
                        if dest == "tinhoctre":
                            upload_transfer_to_tinhoctre(dst, dest, code, pinfo, zip_path, cases, transfer_row, root, language_ids, log_lines)
                        else:
                            upload_transfer_to_dmoj(dst, dest, code, pinfo, zip_path, cases, transfer_row, language_ids, log_lines)
                        pid = admin_problem_id(dst, TARGETS[dest]["base_url"], code)
                    elif settings.get("create_missing_problems", True) and not problem_has_test_zip(dst, TARGETS[dest]["base_url"], code):
                        _pinfo, zip_path, cases, _zip_url = fetch_source_problem(src, CONTEST_TARGETS[source]["base_url"], code, root)
                        upload_existing_problem_tests(dst, dest, code, zip_path, cases)
                        log_lines.append(f"{code}: đã bổ sung test cho bài đã có.")
                    if not pid:
                        raise RuntimeError(f"Không tìm thấy ID admin của bài {code} sau khi chuyển")
                    problem_ref = dict(problem)
                    problem_ref["id"] = pid
                    problem_refs.append(problem_ref)
                create_contest(dst, TARGETS[dest]["base_url"], dest, info, problem_refs, dest_account.get("username", ""))
                row["status"] = "✓ Thành công"
                row["link"] = contest_url(TARGETS[dest]["base_url"], info["key"])
                log_lines.append(f"✓ {info['key']}: đã tạo/cập nhật contest với {len(problem_refs)} bài theo đúng thứ tự gửi lên.")
            except ContestAlreadyExists as exc:
                row["status"] = "✗ Contest đã tồn tại"
                row["link"] = contest_url(TARGETS[dest]["base_url"], row.get("key") or row.get("original_key"))
                log_lines.append(f"✗ {row.get('key')}: {exc}. Bỏ qua contest này.")
            except ProblemAlreadyExists:
                row["status"] = "✗ Bài đã tồn tại nhưng chưa dùng lại được"
                log_lines.append(f"✗ {row.get('key')}: gặp bài đã tồn tại khi chuyển problem, hãy bật dùng lại bài đã có hoặc kiểm tra mã bài.")
            except Exception as exc:
                row["status"] = "✗ Lỗi"
                log_lines.append(f"✗ {row.get('key')}: {exc}")
            result_rows.append(row)
            done += 1
            progress_update(progress_id, phase="confirm-contest-transfer", done=done, total=total, rows=result_rows, message=f"{row.get('key')}: {row.get('status')}")
        ok = all((not row.get("selected")) or row.get("status", "").startswith("✓") for row in result_rows)
        progress_finish(progress_id, ok, "Đã hoàn tất chuyển contest")
        return jsonify({"ok": ok, "rows": result_rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/create-contest")
def api_create_contest():
    payload = request.get_json(force=True)
    target = payload["target"]
    key = payload.get("key", "").strip()
    name = payload.get("name", "").strip()
    problems = [code.strip() for code in payload.get("problems", []) if code.strip()]
    if not key or not name or not problems:
        return jsonify({"error": "Cần nhập mã contest, tên contest và danh sách mã bài."}), 400
    try:
        account = payload["account"]
        dst = login_upload_target(target, TARGETS[target], account)
        refs = []
        for idx, code in enumerate(problems):
            pid = admin_problem_id(dst, TARGETS[target]["base_url"], code)
            if not pid:
                raise RuntimeError(f"Không tìm thấy bài {code} ở {TARGETS[target]['label']}")
            refs.append({"code": code, "id": pid, "points": "100", "partial": True, "is_pretested": False, "max_submissions": "", "order": str(idx)})
        info = {
            "key": key,
            "name": name,
            "description": "",
            "start_time": payload.get("start_time", ""),
            "end_time": payload.get("end_time", ""),
            "format_name": "vnoj",
            "scoreboard_visibility": "H",
            "points_precision": "3",
            "is_visible": True,
            "is_rated": False,
            "is_private": False,
        }
        create_contest(dst, TARGETS[target]["base_url"], target, info, refs, account.get("username", ""))
        link = contest_url(TARGETS[target]["base_url"], key)
        return jsonify({"ok": True, "log": f"✓ Đã tạo/cập nhật contest {key}\nLink: {link}", "link": link})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/prepare-transfer")
def api_prepare_transfer():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id")
    source = payload["source"]
    dest = payload["dest"]
    codes = [code.strip() for code in payload.get("codes", []) if code.strip()]
    if not codes:
        return jsonify({"error": "Chưa nhập mã bài cần chuyển."}), 400
    if source == dest:
        return jsonify({"error": "Nguồn và đích đang trùng nhau."}), 400
    try:
        prepare_id = uuid.uuid4().hex
        root = RUNTIME / ("transfer_" + prepare_id)
        root.mkdir(parents=True, exist_ok=True)
        source_account = payload["source_account"]
        src = login_problem_source(source, source_account, codes[0])
        rows = []
        state_items = {}
        log_lines = [f"Đọc dữ liệu nguồn: {TARGETS[source]['label']} → {TARGETS[dest]['label']}"]
        progress_update(progress_id, phase="prepare-transfer", done=0, total=len(codes), rows=rows, message="Bắt đầu đọc dữ liệu nguồn")
        for index, code in enumerate(codes, 1):
            try:
                info, zip_path, cases, zip_url = fetch_source_problem(src, TARGETS[source]["base_url"], code, root)
                state_items[code] = {"info": info, "zip_path": zip_path, "cases": cases, "zip_url": zip_url}
                source_code = info.code or code
                dest_code = normalize_problem_code_for_target(source_code, dest)
                rows.append(
                    {
                        "original_code": code,
                        "code": dest_code,
                        "name": info.name,
                        "time_limit": info.time_limit or payload.get("settings", {}).get("time_limit") or "1.0",
                        "memory_limit": info.memory_limit or payload.get("settings", {}).get("memory_limit") or "1048576",
                        "source_time_limit": info.time_limit or "1.0",
                        "source_memory_limit": info.memory_limit or "1048576",
                        "test_file": zip_path.name,
                        "test_link": test_data_url(TARGETS[source]["base_url"], code),
                        "test_count": len(cases),
                        "status": "Đã đọc",
                    }
                )
                log_lines.append(f"- {code}: {info.name}, {len(cases)} test, bộ test {test_data_url(TARGETS[source]['base_url'], code)}")
            except Exception as exc:
                rows.append(
                    {
                        "original_code": code,
                        "code": code,
                        "name": "",
                        "time_limit": payload.get("settings", {}).get("time_limit") or "1.0",
                        "memory_limit": payload.get("settings", {}).get("memory_limit") or "1048576",
                        "source_time_limit": "1.0",
                        "source_memory_limit": "1048576",
                        "test_file": "Lỗi khi đọc nguồn",
                        "test_link": test_data_url(TARGETS[source]["base_url"], code),
                        "test_count": 0,
                        "status": "✗ Lỗi đọc nguồn",
                    }
                )
                log_lines.append(f"✗ {code}: {exc}")
            progress_update(progress_id, phase="prepare-transfer", done=index, total=len(codes), rows=rows, message=f"{code}: {rows[-1]['status']}")
        prepared_transfers[prepare_id] = {"root": root, "source": source, "dest": dest, "items": state_items}
        progress_finish(progress_id, True, f"Đã đọc {len(rows)}/{len(codes)} bài")
        return jsonify({"prepare_id": prepare_id, "rows": rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return jsonify({"error": str(exc)}), 400


@app.post("/api/confirm-transfer")
def api_confirm_transfer():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id")
    rows = payload["rows"]
    source = payload["source"]
    dest = payload["dest"]
    settings = payload.get("settings", {})
    log_lines = [
        f"Chuyển bài: {TARGETS[source]['label']} → {TARGETS[dest]['label']}",
        "Tạo bài đích qua admin form: /admin/judge/problem/add/",
    ]
    result_rows = []
    if source == dest:
        for row in rows:
            row["status"] = "✗ Nguồn và đích trùng nhau"
            result_rows.append(row)
        log_lines.append("Nguồn và đích đang trùng nhau, không thực hiện chuyển.")
        progress_finish(progress_id, False, "Nguồn và đích đang trùng nhau")
        return jsonify({"ok": False, "rows": result_rows, "log": "\n".join(log_lines)})

    try:
        dest_account = payload["dest_account"]
        prepare_id = payload.get("prepare_id")
        if not prepare_id or prepare_id not in prepared_transfers:
            return jsonify(
                {
                    "ok": False,
                    "error": "Dữ liệu chuẩn bị chuyển bài đã hết hạn hoặc server vừa khởi động lại. Hãy bấm Chuẩn bị dữ liệu lại rồi mới Xác nhận chuyển bài.",
                }
            ), 400
        state = prepared_transfers[prepare_id]
        dst = login_hncode(TARGETS[dest]["base_url"], dest_account["username"], dest_account["password"])
        out_dir = state["root"]
        language_ids = language_ids_for_target(dest, settings.get("languages", []))

        total = len([row for row in rows if row.get("selected")])
        done = 0
        progress_update(progress_id, phase="confirm-transfer", done=done, total=total, rows=result_rows, message="Bắt đầu chuyển bài")
        for row in rows:
            row = dict(row)
            if not row.get("selected"):
                row["status"] = "Bỏ qua"
                result_rows.append(row)
                continue
            try:
                item = state["items"].get(row["original_code"])
                if not item:
                    raise RuntimeError("Chưa đọc được dữ liệu nguồn cho bài này")
                info = item["info"]
                zip_path = item["zip_path"]
                cases = item["cases"]
                raw_dest_code = row["code"] or row["original_code"]
                dest_code = normalize_problem_code_for_target(raw_dest_code, dest)
                validate_problem_code_for_target(dest_code, dest)
                if dest_code != raw_dest_code:
                    row["code"] = dest_code
                    log_lines.append(f"{raw_dest_code}: mã đích {TARGETS[dest]['label']} được đổi thành {dest_code}")
                if row.get("name"):
                    info.name = row["name"]
                info.time_limit = row.get("time_limit") or settings.get("time_limit") or info.time_limit or "1.0"
                info.memory_limit = row.get("memory_limit") or settings.get("memory_limit") or info.memory_limit or "1048576"
                if dest == "tinhoctre":
                    upload_transfer_to_tinhoctre(dst, dest, dest_code, info, zip_path, cases, row, out_dir, language_ids, log_lines)
                else:
                    upload_transfer_to_dmoj(dst, dest, dest_code, info, zip_path, cases, row, language_ids, log_lines)
                row["status"] = "✓ Thành công"
                row["link"] = problem_url(TARGETS[dest]["base_url"], dest_code)
            except ProblemAlreadyExists as exc:
                row["status"] = "✗ Bài đã tồn tại"
                log_lines.append(f"✗ {row.get('code')}: {exc}. Bỏ qua bài này và tiếp tục các bài khác.")
            except Exception as exc:
                row["status"] = "✗ Lỗi"
                log_lines.append(f"✗ {row.get('code')}: {exc}")
            result_rows.append(row)
            done += 1
            progress_update(progress_id, phase="confirm-transfer", done=done, total=total, rows=result_rows, message=f"{row.get('code')}: {row.get('status')}")
        ok = all((not row.get("selected")) or row["status"].startswith("✓") for row in result_rows)
        progress_finish(progress_id, ok, "Đã hoàn tất chuyển bài")
        return jsonify({"ok": ok, "rows": result_rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400


def upload_transfer_to_dmoj(session, dest: str, dest_code: str, info: ProblemInfo, zip_path: Path, cases, row: dict, language_ids: list[str], log_lines: list[str]) -> None:
    base_url = TARGETS[dest]["base_url"]
    exists = destination_problem_exists(session, base_url, dest_code)
    if exists:
        raise ProblemAlreadyExists(f"Mã bài {dest_code} đã tồn tại tại {problem_url(base_url, dest_code)}")
    if row.get("upload_statement") and not exists:
        dest_info = problem_info_for_target(info, dest)
        create_hncode_problem(
            session,
            base_url,
            dest_info,
            dest_code=dest_code,
            type_id=TARGETS[dest]["type_id"],
            group_id=TARGETS[dest]["group_id"],
            public=False,
            allow_all_languages=False,
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{dest_code}: đã tạo đề.")
    else:
        log_lines.append(f"{dest_code}: bỏ qua tạo đề.")
    if row.get("upload_tests"):
        if dest == "hnoj":
            tests = GeneratedTests(zip_path, [case.input_file for case in cases], [case.output_file for case in cases])
            upload_tinhoctre_tests(session, base_url, dest_code, tests)
        else:
            upload_hncode_tests(session, base_url, dest_code, zip_path, cases)
        log_lines.append(f"{dest_code}: đã upload test.")
    else:
        log_lines.append(f"{dest_code}: không upload test.")


def upload_transfer_to_tinhoctre(session, dest: str, dest_code: str, info: ProblemInfo, zip_path: Path, cases, row: dict, out_dir: Path, language_ids: list[str], log_lines: list[str]) -> None:
    base_url = TARGETS[dest]["base_url"]
    statement = out_dir / f"{dest_code}.md"
    dest_info = problem_info_for_target(info, dest)
    statement.write_text(dest_info.description, encoding="utf-8")
    bundle = ProblemBundle(0, dest_code, info.name, statement, None, zip_path, None)
    tests = GeneratedTests(zip_path, [case.input_file for case in cases], [case.output_file for case in cases])
    exists = tinhoctre_problem_exists(session, base_url, dest_code)
    if exists:
        raise ProblemAlreadyExists(f"Mã bài {dest_code} đã tồn tại tại {problem_url(base_url, dest_code)}")
    if row.get("upload_statement") and not exists:
        create_tinhoctre_admin_problem(
            session,
            base_url,
            dest_info,
            dest_code=dest_code,
            type_id=TARGETS[dest]["type_id"],
            group_id=TARGETS[dest]["group_id"],
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{dest_code}: đã tạo đề.")
    else:
        log_lines.append(f"{dest_code}: bỏ qua tạo đề.")
    if row.get("upload_tests"):
        upload_tinhoctre_tests(session, base_url, dest_code, tests)
        log_lines.append(f"{dest_code}: đã upload test.")
    else:
        log_lines.append(f"{dest_code}: không upload test.")


if __name__ == "__main__":
    app.run(
        host=os.getenv("TOOL_OJ_HOST", "127.0.0.1"),
        port=int(os.getenv("TOOL_OJ_PORT", "5050")),
        debug=False,
    )
