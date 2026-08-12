#!/usr/bin/env python3
"""Local web UI for preparing, uploading, and transferring OJ problems."""

from __future__ import annotations

import html
import base64
import csv
import json
import math
import os
import re
import requests
import shutil
import subprocess
import sys
import time
import unicodedata
import uuid
import zipfile
from collections import Counter, defaultdict
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import urlopen

from flask import Flask, Response, jsonify, render_template, request, send_file

from services import ai_assistant as ai_service
from services import api_response
from services import contest as contest_service
from services import course as course_service
from services import grading as grading_service
from services import hncode as hncode_service
from services import jobs as job_service
from services import lesson as lesson_service
from services import misc as misc_service
from services import problem_bundle as bundle_service
from services import problem_transfer as transfer_service
from services import problem_upload as upload_service
from services import quiz as quiz_service
from services import tinhoctre as tinhoctre_service

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
    USER_AGENT,
    clean_statement,
    csrf_token,
    discover_bundles,
    extract_zip,
    form_errors,
    find_named_file,
    generate_tests,
    login as login_tinhoctre_public,
    problem_exists as tinhoctre_problem_exists,
    read_text_smart,
    session as tinhoctre_session,
    statement_body_text,
    submit_solution,
    upload_tests as upload_tinhoctre_tests,
    zip_case_files,
)


ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".runtime"
SAMPLE_TONGHAISO_ZIP = ROOT / "samples" / "bo_mau_1_bai_tonghaiso.zip"
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
prepared_single_uploads: dict[str, dict] = {}
prepared_transfers: dict[str, dict] = {}
prepared_contest_transfers: dict[str, dict] = {}
prepared_quizzes: dict[str, dict] = {}
prepared_lesson_copies: dict[str, dict] = {}
prepared_course_clones: dict[str, dict] = {}
prepared_hncode_grading: dict[str, dict] = {}
prepared_ai_normalize: dict[str, dict] = {}


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

HNCODE_TYPE_ALIASES = {
    "binary search": "198",
    "binary-search": "198",
    "binary_search": "198",
    "sortings": "188",
    "sorting": "188",
    "sort": "188",
    "dp": "172",
    "dynamic programming": "172",
    "quy hoach dong": "172",
    "quy hoạch động": "172",
    "two pointers": "196",
    "two-pointers": "196",
    "two_pointers": "196",
    "2 pointers": "196",
    "implementation": "340",
    "cai dat": "340",
    "cài đặt": "340",
    "math": "175",
    "toan": "175",
    "toán": "175",
    "greedy": "171",
    "tham lam": "171",
    "strings": "176",
    "string": "176",
    "chuoi": "176",
    "chuỗi": "176",
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
    return quiz_service.normalize_key_text(value)


def quiz_field_from_line(line: str) -> tuple[str, str] | None:
    return quiz_service.quiz_field_from_line(line)


def split_quiz_blocks(text: str) -> list[str]:
    return quiz_service.split_quiz_blocks(text)


def parse_choice_lines(text: str) -> list[dict]:
    return quiz_service.parse_choice_lines(text)


def split_answers(text: str) -> list[str]:
    return quiz_service.split_answers(text)


def parse_quiz_markdown(text: str) -> list[dict]:
    return quiz_service.parse_quiz_markdown(text)


def prepare_quiz_items(text: str) -> tuple[list[dict], list[dict]]:
    return quiz_service.prepare_quiz_items(text)


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
    return job_service.valid_job_id(progress_id)

def progress_path(progress_id: str) -> Path:
    return job_service.job_path(PROGRESS_DIR, progress_id)

def progress_update(progress_id: str | None, **payload) -> None:
    job_service.update_job(PROGRESS_DIR, progress_id, **payload)

def progress_finish(progress_id: str | None, ok: bool, message: str = "") -> None:
    job_service.finish_job(PROGRESS_DIR, progress_id, ok, message)

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
    return misc_service.scratch_submission_score(student_dir)


def find_scratch_data_root(extract_root: Path) -> Path:
    return misc_service.find_scratch_data_root(extract_root)


def history_version(path: Path) -> int:
    return misc_service.history_version(path)


def get_last_scratch_submission(student_dir: Path) -> Path | None:
    return misc_service.get_last_scratch_submission(student_dir)


def collect_last_scratch_submissions(data_root: Path, output_dir: Path) -> dict:
    return misc_service.collect_last_scratch_submissions(data_root, output_dir)


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




@app.get("/")
def index():
    return render_template(
        "index.html",
        default_zip=DEFAULT_ZIP,
        ai_source_default=AI_SOURCE_DEFAULT,
        prompt_guide=PROMPT_GUIDE,
        quiz_format_guide_json=json.dumps(QUIZ_FORMAT_GUIDE, ensure_ascii=False),
        targets_json=json.dumps(TARGETS, ensure_ascii=False),
    )


@app.get("/samples/bo_mau_1_bai_tonghaiso.zip")
def sample_tonghaiso_zip():
    if not SAMPLE_TONGHAISO_ZIP.exists():
        return api_response.api_error("Không tìm thấy file mẫu.", status=404)
    return send_file(SAMPLE_TONGHAISO_ZIP, as_attachment=True, download_name=SAMPLE_TONGHAISO_ZIP.name)


@app.post("/api/sample/tonghaiso")
def api_sample_tonghaiso():
    try:
        if not SAMPLE_TONGHAISO_ZIP.exists():
            raise FileNotFoundError(f"Không tìm thấy file mẫu: {SAMPLE_TONGHAISO_ZIP}")
        with zipfile.ZipFile(SAMPLE_TONGHAISO_ZIP) as archive:
            statement = read_zip_member_text(archive, "tonghaiso.md")
            generator = read_zip_member_text(archive, "gentest_tonghaiso.py")
            solution_md = read_zip_member_text(archive, "sol_tonghaiso.md")
        parts = first_markdown_header_parts(statement)
        return api_response.api_success(
            message="Đã đọc bộ mẫu Tổng hai số.",
            meta={"sample": "tonghaiso"},
            zip_path=str(SAMPLE_TONGHAISO_ZIP),
            code=parts[1] if len(parts) > 1 else "tonghaiso",
            name=parts[0] if parts else "Tổng hai số",
            points=parts[2] if len(parts) > 2 else "800",
            tags=parts[3] if len(parts) > 3 else "implementation, math",
            statement=statement,
            generator=generator,
            solution_md=solution_md,
        )
    except Exception as exc:
        return api_response.api_error(str(exc))


def read_zip_member_text(archive: zipfile.ZipFile, name: str) -> str:
    raw = archive.read(name)
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def first_markdown_header_parts(text: str) -> list[str]:
    for line in text.splitlines():
        stripped = line.strip().strip("#* ")
        if stripped:
            return [part.strip() for part in stripped.split("|")]
    return []


def read_normalize_reference() -> str:
    candidates = [
        ROOT / "MO_TA_CHUAN_HOA_BAI_HNCODE_CHO_AI.md",
        Path(r"C:\Users\Admin\Documents\ChuyenBai\MO_TA_CHUAN_HOA_BAI_HNCODE_CHO_AI.md"),
        Path(r"E:\CodeX_Project\prompt_chuanhoa\MO_TA_CHUAN_HOA_BAI_HNCODE_CHO_AI.md"),
    ]
    for path in candidates:
        if path.exists():
            return read_text_smart(path)
    return (
        "Chuẩn hóa đề bài HNCode: có **Yêu cầu:**, #### Input, #### Output, #### Example; "
        "dùng `$...$` cho công thức, chọn tags/points hợp lý, bật partial points, memory 1024 MB."
    )


def hncode_problem_snapshot(session: requests.Session, code: str) -> dict:
    base_url = TARGETS["hncode"]["base_url"]
    edit_url = urljoin(base_url, f"/problem/{code}/edit")
    edit = session.get(edit_url, timeout=30)
    if not edit.ok:
        raise RuntimeError(f"Không mở được trang edit bài {code}: HTTP {edit.status_code}")
    if "/accounts/login" in edit.url or "/admin/login" in edit.url:
        raise RuntimeError(f"Bị chuyển về trang đăng nhập khi đọc bài {code}: {edit.url}")
    if not (f'name="code"' in edit.text or "name='code'" in edit.text):
        raise RuntimeError(f"Không đọc được form edit bài {code}. Tài khoản có thể không có quyền sửa bài.")
    test_url = urljoin(base_url, f"/problem/{code}/test_data")
    solution_url = urljoin(base_url, f"/problem/{code}/edit/solutions")
    test_page = session.get(test_url, timeout=30)
    solution_page = session.get(solution_url, timeout=30)
    test_count = len(parse_source_cases(test_page.text)) if test_page.ok else 0
    if test_page.ok and not test_count:
        test_count = len(infer_cases_from_zip_paths(test_page.text))
    tags = [str(option["text"]) for option in select_options_with_text(edit.text, "types") if option.get("selected")]
    return {
        "code": input_value(edit.text, "code", code),
        "name": input_value(edit.text, "name", code),
        "statement": textarea_value(edit.text, "description").replace("~", "$"),
        "points": input_value(edit.text, "points", ""),
        "partial": checkbox_checked(edit.text, "partial"),
        "time_limit": input_value(edit.text, "time_limit", ""),
        "memory_limit": input_value(edit.text, "memory_limit", ""),
        "memory_unit": selected_option(edit.text, "memory_unit", ""),
        "tags": tags,
        "test_count": test_count,
        "test_summary": f"{test_count} test; test_data HTTP {test_page.status_code if test_page else 'N/A'}",
        "solution": textarea_value(solution_page.text, "content") if solution_page.ok else "",
        "edit_url": edit_url,
        "test_url": test_url,
        "solution_url": solution_url,
    }


@app.post("/api/ai/prepare-file")
def api_ai_prepare_file():
    try:
        uploaded = request.files.get("source_file")
        if not uploaded:
            raise RuntimeError("Hãy chọn file đề bài.")
        data = uploaded.read()
        text, note = ai_service.extract_source_text(uploaded.filename or "source", data)
        file_info = ai_service.file_payload(uploaded.filename or "source", data)
        return api_response.api_success(
            message=note,
            log=note,
            filename=uploaded.filename,
            source_text=text,
            mime_type=file_info["mime_type"],
            file_base64=base64.b64encode(data).decode("ascii"),
        )
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/ai/prepare-normalize")
def api_ai_prepare_normalize():
    try:
        payload = request.get_json(force=True)
        source_mode = payload.get("source_mode") or "codes"
        target = payload.get("target") or "hncode"
        prepare_id = uuid.uuid4().hex
        rows: list[dict] = []
        snapshots: dict[str, dict] = {}
        files: dict[str, list[dict]] = {}
        log_lines: list[str] = []
        if source_mode == "file":
            code = (payload.get("problem_code") or "file_1").strip()
            name = (payload.get("problem_name") or payload.get("filename") or code).strip()
            snapshot = {
                "code": code,
                "name": name,
                "statement": payload.get("source_text") or "",
                "points": payload.get("points") or "100",
                "partial": True,
                "time_limit": "1.0",
                "memory_limit": "1024",
                "memory_unit": "MB",
                "tags": payload.get("tags") or "",
                "test_count": "",
                "test_summary": "Nguồn là file/nội dung rời, chưa có test_data.",
                "solution": "",
            }
            rows.append({"original_code": code, "code": code, "name": name, "points": snapshot["points"], "tags": snapshot["tags"], "test_count": "", "status": "Đã chuẩn bị", "can_normalize": True})
            snapshots[code] = snapshot
            if payload.get("file_base64") and payload.get("mime_type"):
                files[code] = [{"mime_type": payload.get("mime_type"), "data": base64.b64decode(payload.get("file_base64"))}]
            log_lines.append(f"Đã chuẩn bị nội dung rời: {name}.")
        else:
            codes = [item.strip() for item in re.split(r"[\s,;]+", payload.get("codes") or "") if item.strip()]
            if not codes:
                raise RuntimeError("Hãy nhập ít nhất một mã bài cần chuẩn hóa.")
            account = payload.get("account") or {}
            session = login_hncode(TARGETS["hncode"]["base_url"], account.get("username", ""), account.get("password", ""))
            for code in codes:
                try:
                    snapshot = hncode_problem_snapshot(session, code)
                    key = snapshot["code"] or code
                    snapshots[key] = snapshot
                    rows.append({"original_code": key, "code": key, "name": snapshot["name"], "points": snapshot["points"], "tags": ", ".join(snapshot.get("tags") or []), "test_count": snapshot["test_count"], "status": "Đã đọc dữ liệu", "can_normalize": True})
                    log_lines.append(f"✓ {key}: {snapshot['name']}, {snapshot['test_count']} test.")
                except Exception as exc:
                    rows.append({"original_code": code, "code": code, "name": "", "points": "", "tags": "", "test_count": "", "status": f"✗ {exc}", "can_normalize": False})
                    log_lines.append(f"✗ {code}: {exc}")
        prepared_ai_normalize[prepare_id] = {"reference": read_normalize_reference(), "target": target, "snapshots": snapshots, "files": files, "rows": rows, "created_at": time.time()}
        return api_response.api_success(message="Đã chuẩn bị dữ liệu AI", rows=rows, log="\n".join(log_lines), prepare_id=prepare_id)
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/ai/normalize")
def api_ai_normalize():
    try:
        payload = request.get_json(force=True)
        prepare_id = payload.get("prepare_id")
        if not prepare_id or prepare_id not in prepared_ai_normalize:
            return api_response.api_error("Dữ liệu chuẩn bị AI đã hết hạn. Hãy bấm Chuẩn bị dữ liệu lại.")
        state = prepared_ai_normalize[prepare_id]
        options = payload.get("options") or {}
        target = options.get("target") or state.get("target") or "hncode"
        rows = payload.get("rows") or state["rows"]
        api_key = payload.get("api_key") or ""
        model = payload.get("model") or ai_service.DEFAULT_GEMINI_MODEL
        result_rows = []
        log_lines = [f"Chuẩn hóa bằng Google AI model {model}."]
        for row in rows:
            result = dict(row)
            original = row.get("original_code") or row.get("code")
            if not row.get("selected", True) or not row.get("can_normalize", True):
                result["status"] = "Bỏ qua"
                result_rows.append(result)
                continue
            try:
                snapshot = state["snapshots"].get(original) or state["snapshots"].get(row.get("code"))
                if not snapshot:
                    raise RuntimeError("Không tìm thấy snapshot bài đã chuẩn bị.")
                prompt = ai_service.build_hncode_normalization_prompt(state["reference"], snapshot, {**options, "target": target})
                raw = ai_service.gemini_generate(api_key=api_key, model=model, prompt=prompt, files=state.get("files", {}).get(original) or state.get("files", {}).get(row.get("code")))
                parsed = ai_service.parse_ai_json(raw)
                statement = ai_service.normalize_statement_for_target(parsed.get("statement_markdown") or "", target)
                checks, meta = ai_service.validate_statement_markdown(statement, target)
                result.update({
                    "status": "✓ Đã chuẩn hóa" if meta["valid"] else "⚠ Cần kiểm tra",
                    "name": parsed.get("name") or result.get("name") or meta.get("name"),
                    "points": str(parsed.get("points") or result.get("points") or meta.get("points") or ""),
                    "tags": ", ".join(parsed.get("tags") or []),
                    "statement_markdown": statement,
                    "solution_markdown": parsed.get("solution_markdown") or "",
                    "test_review": parsed.get("test_review") or "",
                    "issues": parsed.get("issues") or [],
                    "confidence": parsed.get("confidence") or "",
                    "checks": checks,
                })
                log_lines.append(f"✓ {result.get('code')}: {result['status']}, confidence {result.get('confidence') or 'N/A'}.")
            except Exception as exc:
                result["status"] = f"✗ {exc}"
                result["error"] = str(exc)
                log_lines.append(f"✗ {row.get('code')}: {exc}")
            result_rows.append(result)
        ok = all(not str(row.get("status", "")).startswith("✗") for row in result_rows)
        return api_response.api_success(message="Đã chạy chuẩn hóa AI", rows=result_rows, log="\n".join(log_lines), ok=ok)
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/ai/validate-statement")
def api_ai_validate_statement():
    try:
        payload = request.get_json(force=True)
        target = payload.get("target") or "hncode"
        checks, meta = ai_service.validate_statement_markdown(payload.get("markdown") or "", target)
        return api_response.api_success(message="Đã kiểm tra Markdown", rows=checks, meta=meta, ok=meta["valid"])
    except Exception as exc:
        return api_response.api_error(str(exc))


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
                if tinhoctre_service.is_waf_challenge_response(page):
                    return jsonify({"ok": False, "message": "WAF/challenge"})
                if probe_code and not (f'name="code"' in page.text or "name='code'" in page.text):
                    return jsonify({"ok": False, "message": "Cookie không mở được trang sửa bài"})
                if tinhoctre_service.is_login_redirect(page):
                    return jsonify({"ok": False, "message": "Cookie hết hạn"})
                return jsonify({"ok": True, "message": "Đăng nhập OK"})
            login_tinhoctre_public(TARGETS[target]["base_url"], account.get("username", ""), account.get("password", ""), "/problems/create")
            return jsonify({"ok": True, "message": "Đăng nhập OK"})
        if target == "hncode_oj":
            login_hncode(QUIZ_BASE_URL, account.get("username", ""), account.get("password", ""))
            return jsonify({"ok": True, "message": "Đăng nhập OK"})
        if target == "contest_hnoj":
            info = CONTEST_TARGETS[target]
        else:
            info = TARGETS[target]
        login_hncode(info["base_url"], account.get("username", ""), account.get("password", ""))
        return jsonify({"ok": True, "message": "Đăng nhập OK"})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)[:180]})


@app.post("/api/misc/list-problem-codes")
def api_misc_list_problem_codes():
    payload = request.get_json(force=True)
    site = payload.get("site", "hncode")
    source_type = payload.get("source_type", "contest")
    source_url = (payload.get("url") or "").strip()
    account = payload.get("account", {})
    try:
        if site == "hncode":
            session = login_hncode(TARGETS["hncode"]["base_url"], account.get("username", ""), account.get("password", ""))
            if source_type == "lesson":
                course_slug, lesson_id = extract_hncode_lesson_ref(source_url)
                rows = hncode_lesson_problem_code_rows(session, course_slug, lesson_id)
                source_label = f"HNCode Lesson: {course_slug}/lesson/{lesson_id}"
            else:
                contest_key = extract_hncode_contest_key(source_url)
                rows = hncode_contest_problem_rows(session, contest_key)
                source_label = f"HNCode Contest: {contest_key}"
        elif site == "hnoj":
            if source_type != "contest":
                raise RuntimeError("HNOJ hiện chỉ hỗ trợ lấy mã bài từ Contest.")
            session = login_hncode(TARGETS["hnoj"]["base_url"], account.get("username", ""), account.get("password", ""))
            contest_key = extract_hncode_contest_key(source_url)
            rows = hnoj_contest_problem_rows(session, contest_key)
            source_label = f"HNOJ Contest: {contest_key}"
        else:
            raise RuntimeError("Nguồn không hợp lệ. Hãy chọn HNCode hoặc HNOJ.")
        for index, row in enumerate(rows, 1):
            row["index"] = index
        codes_text = "\n".join(row["code"] for row in rows)
        compact_text = " ".join(row["code"] for row in rows)
        log_lines = [
            f"Nguồn: {source_label}",
            f"Số bài: {len(rows)}",
            "Danh sách mã bài:",
            codes_text,
        ]
        return api_response.api_success(
            message=f"Đã lấy {len(rows)} mã bài.",
            rows=rows,
            log="\n".join(log_lines),
            meta={"source": source_label, "count": len(rows)},
            codes_text=codes_text,
            compact_text=compact_text,
        )
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/upload-quiz")
def api_upload_quiz():
    payload = request.get_json(force=True)
    account = payload.get("account", {})
    try:
        prepare_id = payload.get("prepare_id", "")
        state = prepared_quizzes.get(prepare_id)
        if not state:
            return api_response.api_error("Dữ liệu quiz đã hết hạn hoặc chưa chuẩn bị. Hãy bấm Chuẩn bị dữ liệu lại.")
        questions = state["questions"]
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
                row["error"] = ""
                log_lines.append(f"✓ Câu {question['index']}: {question['title']} - {link}")
            except Exception as exc:
                ok = False
                row["status"] = "✗ Lỗi"
                row["error"] = str(exc)
                log_lines.append(f"✗ Câu {question['index']}: {question['title']} - {exc}")
            rows.append(row)
        return jsonify({"ok": ok, "rows": rows, "log": "\n".join(log_lines)})
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/prepare-quiz")
def api_prepare_quiz():
    payload = request.get_json(force=True)
    try:
        questions, rows = prepare_quiz_items(payload.get("text", ""))
        prepare_id = uuid.uuid4().hex
        prepared_quizzes[prepare_id] = {"questions": questions, "rows": rows, "created_at": time.time()}
        ok_count = sum(1 for row in rows if row.get("can_upload"))
        bad_count = len(rows) - ok_count
        log_lines = [f"Chuẩn bị dữ liệu quiz: {ok_count}/{len(rows)} câu hợp lệ."]
        for row in rows:
            if row.get("can_upload"):
                log_lines.append(f"✓ Câu {row['index']}: {row['title']} ({row['type']}) hợp lệ.")
            else:
                log_lines.append(f"✗ Câu {row['index']}: {row.get('error')}")
        return jsonify(
            {
                "ok": bad_count == 0,
                "can_upload": bad_count == 0 and ok_count > 0,
                "prepare_id": prepare_id,
                "rows": rows,
                "log": "\n".join(log_lines),
            }
        )
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/prepare-course-clone")
def api_prepare_course_clone():
    payload = request.get_json(force=True)
    account = payload.get("account", {})
    try:
        source_slug = extract_hncode_course_slug(payload.get("source_url", ""))
        dest_slug = extract_hncode_course_slug(payload.get("dest_url", ""))
        if source_slug == dest_slug:
            raise RuntimeError("Course nguồn và course đích đang trùng nhau.")
        include_lessons = bool(payload.get("include_lessons", True))
        include_contests = bool(payload.get("include_contests", True))
        if not include_lessons and not include_contests:
            raise RuntimeError("H?y ch?n Clone lesson ho?c Clone contest.")
        session = login_hncode(TARGETS["hncode"]["base_url"], account.get("username", ""), account.get("password", ""))
        dest_course_id = hncode_course_admin_id(session, dest_slug)
        source_lessons = hncode_course_lessons(session, source_slug) if include_lessons else []
        source_contests = hncode_course_contests(session, source_slug) if include_contests else []
        dest_lessons = hncode_course_lessons(session, dest_slug)
        dest_contests = hncode_course_contests(session, dest_slug)
        log_lines = [
            "Chu?n b? Clone Course HNCode",
            f"Nguồn: {source_slug}",
            f"Đích: {dest_slug}",
            f"Lesson ngu?n: {len(source_lessons)}",
            f"Contest ngu?n: {len(source_contests)}",
        ]
        suffix = payload.get("contest_suffix", "")
        rows, row_logs = course_service.build_course_clone_rows(
            source_lessons,
            source_contests,
            dest_lessons,
            dest_contests,
            dest_slug,
            suffix,
            contest_exists=lambda new_key: admin_contest_change_url(session, TARGETS["hncode"]["base_url"], new_key),
        )
        log_lines.extend(row_logs)
        prepare_id = uuid.uuid4().hex
        prepared_course_clones[prepare_id] = {
            "created_at": time.time(),
            "source_slug": source_slug,
            "dest_slug": dest_slug,
            "dest_course_id": dest_course_id,
            "rows": rows,
        }
        return api_response.api_success(
            message="Đã chuẩn bị dữ liệu Clone Course",
            rows=rows,
            log="\n".join(log_lines),
            prepare_id=prepare_id,
            can_clone=any(row.get("selected") for row in rows),
            meta={"source_slug": source_slug, "dest_slug": dest_slug},
        )
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/confirm-course-clone")
def api_confirm_course_clone():
    payload = request.get_json(force=True)
    account = payload.get("account", {})
    prepare_id = payload.get("prepare_id", "")
    state = prepared_course_clones.get(prepare_id)
    if not state:
        return api_response.api_error("Dữ liệu chuẩn bị Clone Course đã hết hạn. Hãy bấm Chuẩn bị dữ liệu lại.")
    requested_rows = payload.get("rows", [])
    result_rows = []
    ok = True
    log_lines = [
        "Clone Course HNCode",
        f"Nguồn: {state['source_slug']}",
        f"Đích: {state['dest_slug']}",
    ]
    try:
        session = login_hncode(TARGETS["hncode"]["base_url"], account.get("username", ""), account.get("password", ""))
        for base in course_service.merge_requested_course_clone_rows(state["rows"], requested_rows):
            key = base.get("key", "")
            kind = base.get("kind", "")
            if not base["selected"]:
                base["status"] = "Bỏ qua"
                result_rows.append(base)
                log_lines.append(f"- {kind} {key}: bỏ qua.")
                continue
            try:
                if kind == "lesson":
                    link = clone_hncode_lesson_native(session, state["source_slug"], key, base.get("title") or f"Lesson {key}", state["dest_slug"], state["dest_course_id"])
                    base["status"] = "✓ Đã clone"
                    base["link"] = link
                    log_lines.append(f"✓ Lesson {key}: đã clone.")
                elif kind == "contest":
                    new_key = base.get("new_key", "")
                    if not re.fullmatch(r"[a-z0-9_-]+", new_key):
                        raise RuntimeError("Mã contest đích chỉ nên gồm chữ thường, số, dấu gạch dưới hoặc gạch ngang.")
                    link = clone_hncode_contest_native(session, key, new_key, state["dest_slug"], state["dest_course_id"])
                    base["status"] = "✓ Đã clone"
                    base["link"] = link
                    log_lines.append(f"✓ Contest {key} → {new_key}: đã clone.")
                else:
                    raise RuntimeError(f"Loại dòng không hợp lệ: {kind}")
            except Exception as item_exc:
                ok = False
                base["status"] = "✗ Lỗi"
                base["error"] = str(item_exc)
                log_lines.append(f"✗ {kind} {key}: {item_exc}")
            result_rows.append(base)
        if not result_rows:
            ok = False
            log_lines.append("Không có dòng nào được gửi lên để clone.")
        return api_response.api_success(
            message="Đã hoàn tất Clone Course" if ok else "Clone Course có lỗi",
            rows=result_rows,
            log="\n".join(log_lines),
            course_link=hncode_course_page_url(state["dest_slug"]),
            meta={"source_slug": state["source_slug"], "dest_slug": state["dest_slug"]},
            ok=ok,
        )
    except Exception as exc:
        return api_response.api_error(str(exc), rows=result_rows)


@app.post("/api/prepare-contest-to-lesson")
def api_prepare_contest_to_lesson():
    payload = request.get_json(force=True)
    contest_url_value = payload.get("contest_url", "")
    source = contest_lesson_source_from_url(payload.get("source", "hncode"), contest_url_value)
    source_account = payload.get("source_account", {})
    account = payload.get("account", {})
    try:
        contest_key = extract_hncode_contest_key(contest_url_value)
        course_slug, lesson_id = extract_hncode_lesson_ref(payload.get("lesson_url", ""))
        dst_session = login_hncode(TARGETS["hncode"]["base_url"], account.get("username", ""), account.get("password", ""))
        if source == "hnoj":
            src_session = login_hncode(TARGETS["hnoj"]["base_url"], source_account.get("username", ""), source_account.get("password", ""))
            contest_rows = hnoj_contest_problem_rows(src_session, contest_key)
            source_label = "HNOJ"
        else:
            contest_rows = hncode_contest_problem_rows(dst_session, contest_key)
            source_label = "HNCode"
        lesson_page = dst_session.get(hncode_lesson_edit_url(course_slug, lesson_id), timeout=30)
        if not lesson_page.ok:
            raise RuntimeError(f"Không mở được lesson đích: HTTP {lesson_page.status_code}")
        existing_ids = {row["problem"] for row in lesson_problem_rows_from_page(lesson_page.text, lesson_id)}
        log_lines = [
            f"Chuẩn bị sao chép bài {source_label} Contest → Lesson HNCode",
            f"Contest: {contest_key}",
            f"Lesson: {hncode_lesson_url(course_slug, lesson_id)}",
        ]
        rows = lesson_service.build_contest_to_lesson_rows(
            contest_rows,
            source=source,
            existing_problem_ids=existing_ids,
            normalize_problem_code=normalize_problem_code_for_target,
            admin_problem_id=lambda code: admin_problem_id(dst_session, TARGETS["hncode"]["base_url"], code),
        )
        for row in rows:
            log_lines.append(f"{row['index']}. {row['source_code']} → {row['code']} - {row['title']} - {row['status']}")
        prepare_id = uuid.uuid4().hex
        root = RUNTIME / ("contest_lesson_copy_" + prepare_id)
        root.mkdir(parents=True, exist_ok=True)
        prepared_lesson_copies[prepare_id] = {
            "created_at": time.time(),
            "source": source,
            "contest_key": contest_key,
            "course_slug": course_slug,
            "lesson_id": lesson_id,
            "rows": rows,
            "root": root,
        }
        return api_response.api_success(
            message="Đã chuẩn bị dữ liệu sao chép Contest → Lesson",
            rows=rows,
            log="\n".join(log_lines),
            prepare_id=prepare_id,
            can_copy=any(row.get("selected") for row in rows),
            lesson_link=hncode_lesson_url(course_slug, lesson_id),
            meta={"source": source, "contest_key": contest_key, "course_slug": course_slug, "lesson_id": lesson_id},
        )
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/confirm-contest-to-lesson")
def api_confirm_contest_to_lesson():
    payload = request.get_json(force=True)
    account = payload.get("account", {})
    source_account = payload.get("source_account", {})
    prepare_id = payload.get("prepare_id", "")
    state = prepared_lesson_copies.get(prepare_id)
    if not state:
        return api_response.api_error("Dữ liệu chuẩn bị đã hết hạn. Hãy bấm Chuẩn bị dữ liệu lại.")
    try:
        requested_rows = payload.get("rows", [])
        result_rows, selected_refs = lesson_service.merge_requested_lesson_copy_rows(state["rows"], requested_rows)
        source = state.get("source", "hncode")
        source_label = "HNOJ" if source == "hnoj" else "HNCode"
        log_lines = [
            f"Sao chép bài từ Contest {source_label} → Lesson HNCode",
            f"Contest: {state['contest_key']}",
            f"Lesson: {hncode_lesson_url(state['course_slug'], state['lesson_id'])}",
        ]
        dst_session = None
        src_session = None
        for base in result_rows:
            code = base.get("code", "")
            if base.get("selected") and base.get("status") == "Cần chuyển/tìm problem_id":
                if not dst_session:
                    dst_session = login_hncode(TARGETS["hncode"]["base_url"], account.get("username", ""), account.get("password", ""))
                if not base.get("problem_id") and source == "hnoj":
                    if not src_session:
                        src_session = login_hncode(TARGETS["hnoj"]["base_url"], source_account.get("username", ""), source_account.get("password", ""))
                    source_code = base.get("source_code") or code
                    log_lines.append(f"Đang chuyển {source_code} sang HNCode...")
                    try:
                        info, zip_path, cases, _attachments = fetch_source_problem(src_session, TARGETS["hnoj"]["base_url"], source_code, state["root"])
                        upload_transfer_to_dmoj(
                            dst_session,
                            "hncode",
                            code,
                            info,
                            zip_path,
                            cases,
                            {"upload_statement": True, "upload_tests": True},
                            list(TARGETS["hncode"]["languages"].values()),
                            log_lines,
                        )
                    except ProblemAlreadyExists:
                        log_lines.append(f"{code}: bài đã có trên HNCode, dùng lại bài hiện có.")
                    base["problem_id"] = admin_problem_id(dst_session, TARGETS["hncode"]["base_url"], code) or ""
                if not base.get("problem_id"):
                    base["status"] = "✗ Không tìm thấy bài trong admin HNCode"
                else:
                    selected_refs.append(base)
                    base["status"] = "Đang thêm..."
        link = hncode_lesson_url(state["course_slug"], state["lesson_id"])
        if selected_refs:
            if not dst_session:
                dst_session = login_hncode(TARGETS["hncode"]["base_url"], account.get("username", ""), account.get("password", ""))
            added_ids: set[str] = set()
            failed_by_id: dict[str, str] = {}
            for ref in selected_refs:
                problem_id = str(ref.get("problem_id") or ref.get("id") or "")
                try:
                    link = copy_hncode_contest_to_lesson(dst_session, state["course_slug"], state["lesson_id"], [ref])
                    added_ids.add(problem_id)
                except Exception as item_exc:
                    failed_by_id[problem_id] = str(item_exc)
            for row in result_rows:
                if str(row.get("problem_id")) in added_ids and row.get("selected"):
                    row["status"] = "✓ Đã thêm"
                    row["link"] = link
                    log_lines.append(f"✓ {row['code']}: đã thêm vào lesson.")
                elif str(row.get("problem_id")) in failed_by_id and row.get("selected"):
                    row["status"] = "✗ Lỗi"
                    row["error"] = failed_by_id[str(row.get("problem_id"))]
                    log_lines.append(f"✗ {row.get('code')}: {row['error']}")
                elif row["status"] == "Bỏ qua":
                    log_lines.append(f"- {row.get('code')}: bỏ qua.")
                elif row["status"] == "Đã có trong lesson":
                    log_lines.append(f"- {row.get('code')}: đã có trong lesson.")
        else:
            log_lines.append("Không có bài mới được chọn để thêm.")
        ok = all(not row.get("selected") or row.get("status", "").startswith("✓") or "Đã có" in row.get("status", "") for row in result_rows)
        return api_response.api_success(message="Đã hoàn tất sao chép Contest → Lesson" if ok else "Sao chép Contest → Lesson có lỗi", rows=result_rows, log="\n".join(log_lines), link=link, ok=ok)
    except Exception as exc:
        rows = payload.get("rows", [])
        for row in rows:
            row["status"] = "✗ Lỗi"
            row["error"] = str(exc)
        return api_response.api_error(str(exc), rows=rows)


def decode_text_smart(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_hncode_contest_key_any(value: str) -> str:
    return contest_service.extract_contest_key(str(value or ""), "contest")


def hncode_student_session(username: str, password: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    login_url = urljoin(TARGETS["hncode"]["base_url"], "/accounts/login/?next=/")
    page = session.get(login_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được trang đăng nhập HNCode: HTTP {page.status_code}")
    result = session.post(
        login_url,
        data={"username": username, "password": password, "csrfmiddlewaretoken": csrf_token(page.text), "next": "/"},
        headers={"Referer": login_url},
        allow_redirects=True,
        timeout=30,
    )
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if not result.ok or errors:
        raise RuntimeError("Form đăng nhập HNCode báo lỗi: " + "; ".join(errors or [f"HTTP {result.status_code}"]))
    if "sessionid" not in session.cookies.get_dict() or "/accounts/login" in result.url:
        raise RuntimeError("HNCode login did not create a session")
    return session


def parse_hncode_contest_problems(session: requests.Session, contest_key: str) -> list[dict]:
    page = session.get(urljoin(TARGETS["hncode"]["base_url"], f"/contest/{contest_key}/problems"), timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được danh sách bài contest {contest_key}: HTTP {page.status_code}")
    rows = extract_contest_problem_rows_from_html(page.text, contest_key, "100")
    if not rows:
        ranking = session.get(urljoin(TARGETS["hncode"]["base_url"], f"/contest/{contest_key}/ranking/"), timeout=30)
        if ranking.ok:
            rows = extract_contest_problem_rows_from_html(ranking.text, contest_key, "100")
    if not rows:
        raise RuntimeError(f"Không tìm thấy bài nào trong contest {contest_key}.")
    for row in rows:
        try:
            row["points"] = float(str(row.get("points") or "100").replace(",", "."))
        except ValueError:
            row["points"] = 100.0
    change_url = admin_contest_change_url(session, TARGETS["hncode"]["base_url"], contest_key)
    if change_url:
        admin_page = session.get(change_url, timeout=30)
        if admin_page.ok:
            total = int(input_value(admin_page.text, "contest_problems-TOTAL_FORMS", "0") or "0")
            point_rows = []
            for idx in range(total):
                points = input_value(admin_page.text, f"contest_problems-{idx}-points", "")
                order = input_value(admin_page.text, f"contest_problems-{idx}-order", str(idx + 1)) or str(idx + 1)
                if points:
                    try:
                        point_rows.append((int(float(order)), float(str(points).replace(",", "."))))
                    except ValueError:
                        pass
            point_rows.sort(key=lambda item: item[0])
            if len(point_rows) >= len(rows):
                for row, (_order, points) in zip(rows, point_rows):
                    row["points"] = points
    return rows


def read_hncode_grading_accounts(csv_path: Path) -> list[dict]:
    return grading_service.read_accounts(csv_path, decode_text_smart)


def normalize_grading_key(value: str) -> str:
    return grading_service.normalize_key(value)


def grading_source_root(extract_root: Path) -> Path:
    return grading_service.source_root(extract_root)


def map_grading_problem_code(stem: str, contest_problems: list[dict]) -> str:
    return grading_service.map_problem_code(stem, contest_problems)


def collect_hncode_grading_files(source_root: Path, accounts: list[dict], contest_problems: list[dict]) -> tuple[list[dict], list[str]]:
    return grading_service.collect_submission_files(source_root, accounts, contest_problems)


def join_hncode_contest_if_needed(session: requests.Session, contest_key: str, contest_password: str) -> str:
    join_url = urljoin(TARGETS["hncode"]["base_url"], f"/contest/{contest_key}/join")
    page = session.get(join_url, timeout=30, allow_redirects=True)
    if f"/contest/{contest_key}/problems" in page.url:
        return "Đã tham gia"
    parser = FormDataParser()
    parser.feed(page.text)
    form = next((item for item in parser.forms if any(name == "access_code" for name, _value in item)), None)
    if not form:
        return "Không cần nhập mật khẩu"
    result = session.post(
        join_url,
        data=[(name, contest_password if name == "access_code" else value) for name, value in form],
        headers={"Referer": join_url},
        allow_redirects=True,
        timeout=30,
    )
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Join contest báo lỗi: " + "; ".join(errors))
    return "Đã nhập mật khẩu contest"


def preferred_languages_for_source(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix in {".cpp", ".cc", ".cxx"}:
        return ["C++17", "GNU C++17", "C++20", "GNU C++20", "C++"]
    if suffix == ".c":
        return ["C", "C11", "GNU C"]
    if suffix == ".py":
        return ["PyPy 3", "Pypy 3", "Python 3", "Python3", "Python"]
    if suffix == ".pas":
        return ["Pascal", "FPC"]
    return ["C++17", "C++"]


def submit_hncode_grading_file(session: requests.Session, problem_code: str, source_path: Path) -> str:
    submit_url = urljoin(TARGETS["hncode"]["base_url"], f"/problem/{problem_code}/submit")
    page = session.get(submit_url, timeout=30, allow_redirects=True)
    if not page.ok:
        raise RuntimeError(f"Không mở được trang nộp bài {problem_code}: HTTP {page.status_code}")
    language_id = language_id_from_submit_page(page.text, preferred_languages_for_source(source_path))
    if not language_id:
        raise RuntimeError(f"Không tìm thấy ngôn ngữ phù hợp cho file {source_path.name}")
    result = session.post(
        submit_url,
        data={"csrfmiddlewaretoken": csrf_token(page.text), "source": read_text_smart(source_path), "language": language_id, "judge": ""},
        headers={"Referer": submit_url},
        allow_redirects=True,
        timeout=30,
    )
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if not result.ok or errors:
        raise RuntimeError("Submit form báo lỗi: " + "; ".join(errors or [f"HTTP {result.status_code}"]))
    if "/submission/" not in result.url:
        raise RuntimeError(f"Submit chưa tạo submission; URL sau POST: {result.url}")
    return result.url


def parse_hncode_submission_result(page: str) -> dict:
    plain = html.unescape(re.sub(r"<[^>]+>", " ", page))
    plain = re.sub(r"\s+", " ", plain)
    total_match = re.search(r"Tổng cộng:\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*100", plain, re.I)
    score_match = re.search(r"Điểm:\s*([0-9]+(?:[.,][0-9]+)?)\s*/\s*([0-9]+(?:[.,][0-9]+)?)", plain, re.I)
    verdict = ""
    for candidate in ["Accepted", "Wrong Answer", "Time Limit Exceeded", "Runtime Error", "Compilation Error", "Memory Limit Exceeded", "Output Limit Exceeded"]:
        if candidate in plain:
            verdict = candidate
            break
    if total_match:
        return {"done": True, "percent": float(total_match.group(1).replace(",", ".")), "verdict": verdict or "Done"}
    if score_match:
        got = float(score_match.group(1).replace(",", "."))
        total = float(score_match.group(2).replace(",", "."))
        return {"done": True, "percent": 100.0 * got / total if total else 0.0, "verdict": verdict or "Done"}
    if verdict and verdict in {"Compilation Error", "Runtime Error", "Wrong Answer", "Time Limit Exceeded", "Memory Limit Exceeded", "Output Limit Exceeded"}:
        return {"done": True, "percent": 0.0, "verdict": verdict}
    pending = any(word.lower() in plain.lower() for word in ["Queued", "Đang chấm", "Processing", "grading", "Chờ chấm"])
    return {"done": not pending, "percent": None, "verdict": verdict or "Đang chấm"}


def poll_hncode_submission(session: requests.Session, submission_url: str) -> dict:
    while True:
        page = session.get(submission_url, timeout=30)
        if not page.ok:
            raise RuntimeError(f"Không đọc được submission: HTTP {page.status_code}")
        result = parse_hncode_submission_result(page.text)
        if result.get("done") and result.get("percent") is not None:
            return result
        time.sleep(2)


def html_cell_text(fragment: str) -> str:
    return grading_service.html_cell_text(fragment)


def number_from_rank_text(value: str) -> float | str:
    return grading_service.number_from_rank_text(value)


def parse_hncode_ranking_table(page: str) -> tuple[list[dict], list[str]]:
    return grading_service.parse_ranking_table(page)


def fetch_hncode_contest_ranking(session: requests.Session, contest_key: str) -> tuple[list[dict], list[str]]:
    all_rows: list[dict] = []
    problem_codes: list[str] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for page_num in range(1, 51):
        page = session.get(
            urljoin(TARGETS["hncode"]["base_url"], f"/contest/{contest_key}/ranking/"),
            params={"friend": "0", "virtual": "1", "page": str(page_num)},
            timeout=30,
        )
        if not page.ok:
            raise RuntimeError(f"Không đọc được bảng rank contest: HTTP {page.status_code}")
        rows, codes = parse_hncode_ranking_table(page.text)
        if codes and not problem_codes:
            problem_codes = codes
        new_rows = []
        for row in rows:
            key = (str(row.get("username", "")), str(row.get("participation", "")), str(row.get("rank", "")))
            if key not in seen_keys:
                seen_keys.add(key)
                new_rows.append(row)
        if not new_rows:
            break
        all_rows.extend(new_rows)
        if len(rows) < 100:
            break
    return all_rows, problem_codes


def write_hncode_grading_excel(rows: list[dict], contest_problems: list[dict], accounts: list[dict], output_path: Path, ranking_rows: list[dict] | None = None, ranking_problem_codes: list[str] | None = None) -> None:
    grading_service.write_excel(rows, contest_problems, accounts, output_path, ranking_rows, ranking_problem_codes)


@app.post("/api/prepare-hncode-grading")
def api_prepare_hncode_grading():
    progress_id = request.form.get("progress_id")
    try:
        contest_key = extract_hncode_contest_key_any(request.form.get("contest_url", ""))
        zip_file = request.files.get("zip_file")
        csv_file = request.files.get("csv_file")
        if not zip_file or not zip_file.filename:
            return api_response.api_error("Chưa chọn file zip bài làm.")
        if not csv_file or not csv_file.filename:
            return api_response.api_error("Chưa chọn file CSV tài khoản.")
        prepare_id = uuid.uuid4().hex
        root = RUNTIME / ("hncode_grading_" + prepare_id)
        source_zip = root / "bai_lam.zip"
        account_csv = root / "tai_khoan.csv"
        extract_root = root / "extract"
        root.mkdir(parents=True, exist_ok=True)
        zip_file.save(source_zip)
        csv_file.save(account_csv)
        progress_update(progress_id, phase="prepare-hncode-grading", done=0, total=3, rows=[], message="Đang đọc contest HNCode")
        admin_session = login_hncode(TARGETS["hncode"]["base_url"], "hncode", "HNCodemaidinh89()")
        contest_problems = parse_hncode_contest_problems(admin_session, contest_key)
        accounts = read_hncode_grading_accounts(account_csv)
        safe_extract_zip(source_zip, extract_root)
        source_root = grading_source_root(extract_root)
        rows, warnings = collect_hncode_grading_files(source_root, accounts, contest_problems)
        prepared_hncode_grading[prepare_id] = {"root": root, "source_root": source_root, "contest_key": contest_key, "contest_problems": contest_problems, "accounts": accounts, "rows": rows, "output": ""}
        log_lines = [f"Contest: {contest_key}", f"Đã đọc {len(contest_problems)} bài: " + ", ".join(problem["code"] for problem in contest_problems), f"Đã đọc {len(accounts)} tài khoản.", f"Đã tìm thấy {len(rows)} file bài làm."]
        log_lines.extend(f"- {warning}" for warning in warnings)
        progress_update(progress_id, phase="prepare-hncode-grading", done=3, total=3, rows=rows, message="Đã chuẩn bị dữ liệu chấm")
        progress_finish(progress_id, True, "Đã chuẩn bị dữ liệu chấm")
        return api_response.api_success(message="Đã chuẩn bị dữ liệu chấm HNCode", rows=rows, log="\n".join(log_lines), prepare_id=prepare_id, problems=contest_problems, accounts=accounts, meta={"contest_key": contest_key})
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


@app.post("/api/confirm-hncode-grading")
def api_confirm_hncode_grading():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id")
    state = prepared_hncode_grading.get(payload.get("prepare_id", ""))
    if not state:
        progress_finish(progress_id, False, "Dữ liệu chuẩn bị chấm đã hết hạn")
        return api_response.api_error("Dữ liệu chuẩn bị chấm đã hết hạn. Hãy bấm Chuẩn bị dữ liệu lại.")
    try:
        rows = grading_service.merge_requested_rows(state["rows"], payload.get("rows", []))
        selected_rows = [row for row in rows if row.get("selected")]
        if not selected_rows:
            raise RuntimeError("Chưa chọn bài nào để nộp chấm.")
        contest_password = payload.get("contest_password", "")
        account_by_username = {account["username"]: account for account in state["accounts"]}
        sessions: dict[str, requests.Session] = {}
        done = 0
        log_lines = [f"Chấm bài HNCode contest {state['contest_key']}: {len(selected_rows)} file được chọn."]
        progress_update(progress_id, phase="confirm-hncode-grading", done=0, total=len(selected_rows), rows=rows, message="Bắt đầu nộp bài")
        for row in rows:
            if not row.get("selected"):
                row["status"] = "Bỏ qua"
                continue
            try:
                account = account_by_username[row["username"]]
                session = sessions.get(row["username"])
                if session is None:
                    session = hncode_student_session(account["username"], account["password"])
                    log_lines.append(f"{account['name']} ({account['username']}): {join_hncode_contest_if_needed(session, state['contest_key'], contest_password)}.")
                    sessions[row["username"]] = session
                progress_update(progress_id, phase="confirm-hncode-grading", done=done, total=len(selected_rows), rows=rows, message=f"{row['student']} - {row['problem']}: đang nộp")
                row["status"] = "Đang nộp"
                row["submission_url"] = submit_hncode_grading_file(session, row["problem"], Path(row["local_path"]))
                result = poll_hncode_submission(session, row["submission_url"])
                percent = result.get("percent")
                row["percent"] = "" if percent is None else round(float(percent), 2)
                row["score"] = "" if percent is None else round(float(row.get("contest_points") or 0) * float(percent) / 100.0, 2)
                row["status"] = "✓ Đã chấm" if percent is not None else "✓ Đã nộp"
                row["message"] = result.get("verdict") or ""
                log_lines.append(f"✓ {row['student']} - {row['problem']}: {row['message']}, {row['percent']}%, điểm {row['score']}.")
            except Exception as exc:
                row["status"] = "✗ Lỗi"
                row["message"] = str(exc)
                log_lines.append(f"✗ {row.get('student')} - {row.get('problem')}: {exc}")
            done += 1
            progress_update(progress_id, phase="confirm-hncode-grading", done=done, total=len(selected_rows), rows=rows, message=f"{row.get('student')} - {row.get('problem')}: {row.get('status')}")
        output_path = Path(state["root"]) / "bang_diem_hncode.xlsx"
        ranking_rows: list[dict] = []
        ranking_problem_codes: list[str] = []
        try:
            rank_session = login_hncode(TARGETS["hncode"]["base_url"], "hncode", "HNCodemaidinh89()")
            ranking_rows, ranking_problem_codes = fetch_hncode_contest_ranking(rank_session, state["contest_key"])
            log_lines.append(f"Đã đọc lại bảng rank contest: {len(ranking_rows)} dòng.")
        except Exception as exc:
            log_lines.append(f"Không đọc được bảng rank, Excel dùng dữ liệu submission vừa nộp: {exc}")
        write_hncode_grading_excel(rows, state["contest_problems"], state["accounts"], output_path, ranking_rows, ranking_problem_codes)
        state["rows"] = rows
        state["output"] = str(output_path)
        ok = all((not row.get("selected")) or str(row.get("status", "")).startswith("✓") for row in rows)
        progress_finish(progress_id, ok, "Đã hoàn tất chấm bài")
        return api_response.api_success(message="Đã hoàn tất chấm bài HNCode" if ok else "Chấm bài HNCode có lỗi", rows=rows, log="\n".join(log_lines), download_url=f"/api/download-hncode-grading/{payload.get('prepare_id', '')}", ok=ok)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


@app.get("/api/download-hncode-grading/<prepare_id>")
def api_download_hncode_grading(prepare_id: str):
    state = prepared_hncode_grading.get(prepare_id)
    if not state or not state.get("output"):
        return jsonify({"error": "Chưa có file bảng điểm để tải."}), 404
    path = Path(state["output"])
    if not path.exists():
        return jsonify({"error": "File bảng điểm không còn tồn tại."}), 404
    return send_file(path, as_attachment=True, download_name=path.name, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/progress/<progress_id>")
def api_progress(progress_id: str):
    if not valid_progress_id(progress_id):
        return api_response.api_error("invalid progress_id")
    return jsonify(job_service.read_job(PROGRESS_DIR, progress_id))

@app.post("/api/misc/last-submissions")
def api_misc_last_submissions():
    uploaded = request.files.get("zip_file")
    if not uploaded or not uploaded.filename:
        return api_response.api_error("Chưa chọn file zip data.")
    if Path(uploaded.filename).suffix.lower() != ".zip":
        return api_response.api_error("File data phải là .zip.")
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
            return api_response.api_error("Không tìm thấy thư mục thí sinh nào trong file zip.")
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
        return api_response.api_error(str(exc))


@app.post("/api/misc/ai-code-warning")
def api_misc_ai_code_warning():
    job_root = RUNTIME / "misc" / uuid.uuid4().hex
    try:
        job_root.mkdir(parents=True, exist_ok=True)
        uploaded = request.files.get("zip_file")
        source_zips: list[Path] = []
        if uploaded and uploaded.filename:
            if Path(uploaded.filename).suffix.lower() != ".zip":
                return api_response.api_error("File data phải là .zip.")
            input_zip = job_root / safe_output_part(Path(uploaded.filename).name)
            uploaded.save(input_zip)
            source_zips = [input_zip]
        else:
            folder_path = (request.form.get("folder_path") or "").strip()
            if not folder_path:
                return api_response.api_error("Hãy chọn file zip hoặc nhập folder chứa các zip contest.")
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
        return api_response.api_error(str(exc))


@app.post("/api/tinhoctre-browser/start")
def api_tinhoctre_browser_start():
    try:
        browser = find_edge_executable()
        port = int(os.getenv("TINHOCTRE_CHROME_DEBUG_PORT", "9223"))
        url = tinhoctre_service.admin_problem_add_url()
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
        return api_response.api_error(str(exc))


@app.post("/api/tinhoctre-browser/cookie")
def api_tinhoctre_browser_cookie():
    try:
        cookie = cookie_from_tinhoctre_debug_browser()
        save_tinhoctre_cookie(cookie)
        s = session_from_cookie(cookie)
        check = s.get(tinhoctre_service.admin_problem_add_url(), timeout=30)
        if not check.ok or not is_problem_add_form(check.text):
            raise RuntimeError(tinhoctre_admin_cookie_error(check.url))
        return jsonify({"ok": True, "cookie": cookie, "message": "Đã lấy Cookie TinHocTre từ Edge và kiểm tra mở được form admin tạo bài."})
    except Exception as exc:
        return api_response.api_error(str(exc))


@app.post("/api/tinhoctre-browser/quick-cookie")
def api_tinhoctre_browser_quick_cookie():
    try:
        stop_edge_processes()
        time.sleep(1)
        chrome = find_edge_executable()
        port = int(os.getenv("TINHOCTRE_CHROME_DEBUG_PORT", "9223"))
        url = tinhoctre_service.admin_problem_add_url()
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
        return api_response.api_error(str(exc))


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
        solutions_md: dict[str, Path | None] = {}
        metadata: dict[str, dict] = {}
        for index, bundle in enumerate(bundles, 1):
            generated = tests.get(bundle.code)
            source = "Markdown tổng hợp"
            if bundle.generator or bundle.test_zip:
                generated = generate_tests(bundle, build_root)
                tests[bundle.code] = generated
                source = "gentest" if bundle.generator else "zip có sẵn"
            meta = metadata_from_statement(bundle.statement, payload)
            metadata[bundle.code] = meta
            solution_md = find_named_file(source_dir, ["sol"], bundle.index, bundle.code, ".md") if source_path.suffix.lower() != ".md" else None
            solutions_md[bundle.code] = solution_md
            rows.append(
                {
                    "original_code": bundle.code,
                    "code": bundle.code,
                    "name": bundle.name,
                    "points": meta["points"],
                    "tags": meta["tags"],
                    "time_limit": payload.get("time_limit") or "1.0",
                    "memory_limit": payload.get("memory_limit") or "1048576",
                    "partial": meta["partial"],
                    "test_file": generated.zip_path.name if generated else "Không có test",
                    "test_count": len(generated.input_files) if generated else 0,
                    "upload_tests_default": bool(generated),
                    "upload_solution_default": bool(solution_md),
                }
            )
            test_text = f"{len(generated.input_files)} test" if generated else "không có test"
            solution_text = ", có lời giải Markdown" if solution_md else ""
            log_lines.append(f"- {bundle.code}: {bundle.name}, điểm {meta['points']}, tags {meta['tags'] or 'trống'}, {test_text}, nguồn {source}{solution_text}.")
            progress_update(progress_id, phase="prepare-upload", done=index, total=len(bundles), rows=rows, message=f"{bundle.code}: đã chuẩn bị {test_text}")
        prepared_uploads[prepare_id] = {"root": root, "bundles": {b.code: b for b in bundles}, "tests": tests, "solutions": solutions_md, "metadata": metadata}
        progress_finish(progress_id, True, f"Đã chuẩn bị {len(bundles)}/{len(bundles)} bài")
        return api_response.api_success(
            message=f"Đã chuẩn bị {len(rows)} bài.",
            rows=rows,
            log="\n".join(log_lines),
            meta={"source": source_name, "count": len(rows)},
            prepare_id=prepare_id,
        )
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


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
    return bundle_service.split_combined_markdown_bundles(markdown_path, source_dir)

def statement_header_parts(statement_path: Path) -> list[str]:
    return bundle_service.statement_header_parts(statement_path)

def metadata_from_statement(statement_path: Path, defaults: dict) -> dict:
    return bundle_service.metadata_from_statement(statement_path, defaults)

@app.post("/api/prepare-single-upload")
def api_prepare_single_upload():
    progress_id = None
    try:
        payload = upload_payload()
        progress_id = payload.get("progress_id")
        target = payload.get("target") or "hncode"
        raw_code = (payload.get("code") or "").strip()
        statement_text = (payload.get("statement_text") or "").strip()
        inferred_name, inferred_code = infer_statement_title(statement_text)
        code = (raw_code or inferred_code).strip().lower()
        name = (payload.get("name") or inferred_name or code).strip()
        if not code:
            raise RuntimeError("Hãy nhập mã bài hoặc dùng dòng đầu đề bài dạng: Tên bài | ma_bai.")
        if not name:
            raise RuntimeError("Hãy nhập tên bài toán.")
        prepare_note = ""
        if target == "hncode" and not re.fullmatch(r"[a-z0-9_]+", code):
            normalized = normalize_problem_code_for_target(code, target)
            prepare_note = (
                f"Mã {code} có ký tự ngoài chuẩn tạo mới của HNCode. Khi xác nhận, nếu bài này đã tồn tại thì tool dùng đúng mã này; "
                f"nếu tạo mới thì đổi thành {normalized}."
            )

        prepare_id = uuid.uuid4().hex
        root = RUNTIME / prepare_id
        source_dir = root / "single"
        build_root = root / "generated"
        source_dir.mkdir(parents=True, exist_ok=True)
        build_root.mkdir(parents=True, exist_ok=True)

        statement_path = source_dir / f"{code}.md"
        if statement_text:
            statement_path.write_text(statement_text.strip() + "\n", encoding="utf-8")
        else:
            statement_path.write_text(f"{name} | {code}\n", encoding="utf-8")

        generator_path: Path | None = None
        generator_text = (payload.get("generator_text") or "").strip()
        generator_filename = Path(payload.get("generator_filename") or "").name
        if generator_text:
            suffix = Path(generator_filename).suffix.lower() if generator_filename else ".py"
            if suffix not in {".py", ".cpp"}:
                suffix = ".py"
            generator_path = source_dir / f"gentest_{code}{suffix}"
            generator_path.write_text(repair_python_main_guard(generator_text) + "\n", encoding="utf-8")

        test_zip_path: Path | None = None
        uploaded_test_zip = request.files.get("test_zip")
        if uploaded_test_zip and uploaded_test_zip.filename:
            test_zip_path = source_dir / f"{code}.zip"
            uploaded_test_zip.save(test_zip_path)

        bundle = ProblemBundle(1, code, name, statement_path, generator_path if generator_path and generator_path.suffix.lower() == ".py" else None, test_zip_path, None, None)
        tests: GeneratedTests | None = None
        test_source = "Không có test"
        log_lines = [f"Đã chuẩn bị bài {code}: {name}."]
        if prepare_note:
            log_lines.append(f"- {prepare_note}")
        if test_zip_path:
            input_files, output_files = zip_case_files(test_zip_path)
            tests = GeneratedTests(test_zip_path, input_files, output_files)
            test_source = test_zip_path.name
            log_lines.append(f"- Dùng zip test có sẵn: {test_zip_path.name}, {len(input_files)} test.")
        elif bundle.generator:
            tests = generate_tests(bundle, build_root)
            test_source = tests.zip_path.name
            log_lines.append(f"- Đã chạy gentest Python và sinh {len(tests.input_files)} test: {tests.zip_path.name}.")
        elif generator_path and generator_path.suffix.lower() == ".cpp":
            tests = generate_tests_from_cpp_generator(generator_path, build_root, code)
            test_source = tests.zip_path.name
            log_lines.append(f"- Đã compile/chạy C++ generator và sinh {len(tests.input_files)} test: {tests.zip_path.name}.")

        solution_path: Path | None = None
        solution_text = (payload.get("solution_text") or "").strip()
        if solution_text:
            solution_path = source_dir / f"solution_{code}.md"
            solution_path.write_text(solution_text + "\n", encoding="utf-8")
            log_lines.append("- Có lời giải/hướng dẫn Markdown.")

        rows = [
            {
                "original_code": code,
                "code": code,
                "name": name,
                "points": payload.get("points") or "100",
                "tags": payload.get("tags") or "",
                "time_limit": payload.get("time_limit") or "1.0",
                "memory_limit": payload.get("memory_limit") or "1024M",
                "partial": bool(payload.get("partial", True)),
                "test_file": test_source,
                "test_count": len(tests.input_files) if tests else 0,
                "upload_statement_default": bool(statement_text),
                "upload_tests_default": bool(tests),
                "upload_solution_default": bool(solution_path),
                "status": "Đã chuẩn bị" if bool(statement_text) or bool(tests) or bool(solution_path) else "Chưa có phần nào để up",
                "note": prepare_note,
            }
        ]
        prepared_single_uploads[prepare_id] = {
            "root": root,
            "bundles": {code: bundle},
            "tests": {code: tests},
            "solutions": {code: solution_path},
        }
        progress_finish(progress_id, True, "Đã chuẩn bị 1/1 bài")
        return api_response.api_success(message="Đã chuẩn bị dữ liệu", rows=rows, log="\n".join(log_lines), prepare_id=prepare_id)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


def infer_statement_title(statement: str) -> tuple[str, str]:
    for line in statement.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 2 and parts[0] and re.fullmatch(r"[A-Za-z0-9_-]+", parts[1]):
            return parts[0], parts[1]
        break
    return "", ""


def repair_python_main_guard(text: str) -> str:
    return bundle_service.repair_python_main_guard(text)

def generate_tests_from_cpp_generator(generator_path: Path, build_root: Path, code: str) -> GeneratedTests:
    return bundle_service.generate_tests_from_cpp_generator(generator_path, build_root, code)

def find_generated_zip_for_single(build_dir: Path, bundle: ProblemBundle) -> Path | None:
    return bundle_service.find_generated_zip_for_single(build_dir, bundle)

def zip_generated_case_files(build_dir: Path, code: str) -> Path:
    return bundle_service.zip_generated_case_files(build_dir, code)

@app.post("/api/confirm-single-upload")
def api_confirm_single_upload():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id") or payload.get("settings", {}).get("progress_id")
    try:
        prepare_id = payload.get("prepare_id")
        if not prepare_id or prepare_id not in prepared_single_uploads:
            return api_response.api_error("Dữ liệu Up 1 bài đã hết hạn. Hãy bấm Chuẩn bị dữ liệu lại.")
        settings = dict(payload.get("settings") or {})
        rows = payload.get("rows") or []
        target = settings.get("target") or "hncode"
        state = prepared_single_uploads[prepare_id]
        result_rows, log_lines = upload_rows(target, settings, rows, state, progress_id)
        append_single_solution_uploads(target, settings, result_rows, state, log_lines)
        ok = all((not row.get("selected")) or row["status"].startswith("✓") for row in result_rows)
        progress_finish(progress_id, ok, "Đã hoàn tất Up 1 bài")
        return api_response.api_success(message="Đã hoàn tất" if ok else "Có lỗi trong quá trình xử lý", rows=result_rows, log="\n".join(log_lines), ok=ok)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


def append_single_solution_uploads(target: str, settings: dict, rows: list[dict], state: dict, log_lines: list[str]) -> None:
    if not any(row.get("selected") and row.get("upload_solution") for row in rows):
        return
    target_info = TARGETS[target]
    session = login_upload_target(target, target_info, settings)
    for row in rows:
        if not row.get("selected") or not row.get("upload_solution") or not row.get("status", "").startswith("✓"):
            continue
        code = row.get("code") or row.get("original_code")
        solution_path = state.get("solutions", {}).get(row.get("original_code")) or state.get("solutions", {}).get(code)
        if not solution_path:
            continue
        try:
            update_problem_solution_markdown(session, target_info["base_url"], code, read_text_smart(solution_path))
            row["status"] += " và lời giải"
            log_lines.append(f"{code}: đã up lời giải/hướng dẫn Markdown.")
        except Exception as exc:
            row["status"] = "✗ Lỗi"
            row["error"] = str(exc)
            log_lines.append(f"✗ {code}: không up lời giải được: {exc}")


def update_problem_solution_markdown(session, base_url: str, code: str, content: str) -> str:
    solution_url = urljoin(base_url, f"/problem/{code}/edit/solutions")
    page = session.get(solution_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được trang lời giải {code}: HTTP {page.status_code}")
    parser = FormDataParser()
    parser.feed(page.text)
    form = next((form for form in parser.forms if any(name == "content" for name, _value in form)), None)
    if not form:
        raise RuntimeError("Không tìm thấy form lời giải có trường content.")
    data = set_single_form_fields(form, {"content": content})
    result = session.post(solution_url, data=data, headers={"Referer": solution_url}, allow_redirects=True, timeout=30)
    if not result.ok:
        raise RuntimeError(f"Up lời giải lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Form lời giải báo lỗi:\n" + "\n".join(errors))
    return result.url


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
        append_single_solution_uploads(target, payload["settings"], result_rows, state, log_lines)
        ok = all((not row.get("selected")) or row["status"].startswith("✓") for row in result_rows)
        progress_finish(progress_id, ok, "Đã hoàn tất up bài")
        return api_response.api_success(message="Đã hoàn tất" if ok else "Có lỗi trong quá trình xử lý", rows=result_rows, log="\n".join(log_lines), ok=ok)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


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
            raw_code = row["code"] or row["original_code"]
            dest_code, code_note = resolve_problem_code_for_upload(session, target, target_info["base_url"], raw_code)
            if dest_code != raw_code:
                row["code"] = dest_code
                log_lines.append(code_note or f"{raw_code}: mã đích {TARGETS[target]['label']} được đổi thành {dest_code}")
            bundle = replace(state["bundles"][row["original_code"]], code=dest_code, name=row["name"])
            tests = state["tests"].get(row["original_code"])
            action_status = upload_one_problem(session, target, target_info, bundle, tests, row, settings, selected_language_ids, log_lines)
            row["status"] = action_status or "✓ Thành công"
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
        check = s.get(tinhoctre_service.admin_problem_add_url(target_info["base_url"]), timeout=30)
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
    return tinhoctre_service.is_problem_add_form(page)


def tinhoctre_admin_cookie_error(final_url: str = "") -> str:
    return tinhoctre_service.admin_cookie_error(final_url)

def collect_problem_edit_form_data(page: str) -> list[tuple[str, str]]:
    parser = FormDataParser()
    parser.feed(page)
    for form in parser.forms:
        names = {name for name, _value in form}
        if "code" in names and "description" in names:
            return form
    return []


def set_single_form_fields(data: list[tuple[str, str]], updates: dict[str, str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, value in data:
        if name in updates:
            if name not in seen:
                out.append((name, updates[name]))
                seen.add(name)
            continue
        out.append((name, value))
    for name, value in updates.items():
        if name not in seen:
            out.append((name, value))
    return out


def set_form_fields(
    data: list[tuple[str, str]],
    updates: dict[str, str],
    *,
    multi_updates: dict[str, list[str]] | None = None,
    checkbox_updates: dict[str, bool] | None = None,
) -> list[tuple[str, str]]:
    multi_updates = multi_updates or {}
    checkbox_updates = checkbox_updates or {}
    skip_names = set(updates) | set(multi_updates) | set(checkbox_updates)
    out: list[tuple[str, str]] = []
    for name, value in data:
        if name not in skip_names:
            out.append((name, value))
    out.extend(updates.items())
    for name, values in multi_updates.items():
        out.extend((name, value) for value in values if value)
    for name, checked in checkbox_updates.items():
        if checked:
            out.append((name, "on"))
    return out


def normalized_lookup_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def select_options_with_text(page: str, name: str) -> list[dict[str, str | bool]]:
    match = re.search(r"<select\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>(.*?)</select>", page, re.S)
    if not match:
        return []
    options: list[dict[str, str | bool]] = []
    for option in re.finditer(r"<option\b([^>]*)>(.*?)</option>", match.group(1), re.S):
        attrs = option.group(1)
        value = re.search(r"value=[\"']([^\"']*)", attrs)
        label = html.unescape(re.sub(r"<.*?>", " ", option.group(2))).strip()
        label = re.sub(r"\s+", " ", label)
        options.append(
            {
                "value": html.unescape(value.group(1)) if value else "",
                "text": label,
                "selected": "selected" in attrs,
            }
        )
    return options


def resolve_hncode_type_ids(page: str, tags_text: object, fallback_ids: list[str]) -> list[str]:
    options = select_options_with_text(page, "types")
    valid_values = {str(option["value"]) for option in options if option.get("value")}
    ids: list[str] = []

    def add(value: str) -> None:
        if value and value in valid_values and value not in ids:
            ids.append(value)

    lookup: dict[str, str] = {}
    for option in options:
        value = str(option.get("value") or "")
        text = str(option.get("text") or "")
        if not value:
            continue
        labels = [text]
        if " - " in text:
            labels.extend(part.strip() for part in text.split(" - ", 1))
        if "-" in text:
            labels.extend(part.strip() for part in text.split("-", 1))
        for label in labels:
            key = normalized_lookup_text(label)
            if key:
                lookup.setdefault(key, value)

    for raw_tag in re.split(r"[,;|]+", str(tags_text or "")):
        tag = raw_tag.strip()
        if not tag:
            continue
        if tag in valid_values:
            add(tag)
            continue
        alias_id = HNCODE_TYPE_ALIASES.get(tag.lower()) or HNCODE_TYPE_ALIASES.get(normalized_lookup_text(tag))
        if alias_id:
            add(alias_id)
            continue
        add(lookup.get(normalized_lookup_text(tag), ""))

    if not ids:
        for value in fallback_ids or []:
            add(str(value))
    return ids or [TARGETS["hncode"]["type_id"]]


def update_existing_problem_statement(
    session,
    target: str,
    base_url: str,
    bundle: ProblemBundle,
    settings: dict,
) -> str:
    edit_url = urljoin(base_url, f"/problem/{bundle.code}/edit")
    page = session.get(edit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form sửa bài {bundle.code}: HTTP {page.status_code}")
    data = collect_problem_edit_form_data(page.text)
    if not data:
        raise RuntimeError(f"Không tìm thấy form sửa đề bài cho {bundle.code}. Tài khoản có thể chưa có quyền sửa bài này.")
    description = statement_for_target(
        target,
        read_text_smart(bundle.statement),
        skip_title_line=bool(settings.get("skip_statement_title", True)),
    )
    data = set_single_form_fields(
        data,
        {
            "code": bundle.code,
            "name": bundle.name,
            "description": description,
        },
    )
    result = session.post(edit_url, data=data, headers={"Referer": edit_url}, allow_redirects=True, timeout=30)
    if not result.ok:
        raise RuntimeError(f"Ghi đè đề bài lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Form ghi đè đề bài báo lỗi:\n" + "\n".join(errors))
    if "/accounts/login" in result.url or "/admin/login" in result.url:
        raise RuntimeError(f"Ghi đè đề bài bị chuyển về trang đăng nhập: {result.url}")
    verify = session.get(edit_url, timeout=30)
    if not verify.ok:
        raise RuntimeError(f"Không kiểm tra lại được đề bài sau khi ghi đè: HTTP {verify.status_code}")
    saved_description = textarea_value(verify.text, "description")
    saved_name = input_value_from_page(verify.text, "name", "")
    if saved_description.strip() != description.strip():
        debug_dir = RUNTIME / "debug_overwrite_statement"
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"{bundle.code}_expected.md").write_text(description, encoding="utf-8", errors="replace")
        (debug_dir / f"{bundle.code}_saved.md").write_text(saved_description, encoding="utf-8", errors="replace")
        (debug_dir / f"{bundle.code}_post.html").write_text(result.text, encoding="utf-8", errors="replace")
        (debug_dir / f"{bundle.code}_verify.html").write_text(verify.text, encoding="utf-8", errors="replace")
        raise RuntimeError(
            f"HNCode nhận POST nhưng đề bài {bundle.code} chưa khớp nội dung mới. "
            f"Đã lưu debug tại {debug_dir}."
        )
    if saved_name and saved_name != bundle.name:
        raise RuntimeError(f"HNCode nhận POST nhưng tên bài {bundle.code} chưa đổi: {saved_name!r}")
    return result.url


def update_hncode_problem_metadata(
    session,
    base_url: str,
    code: str,
    *,
    name: str,
    points: str,
    partial: bool,
    time_limit: str,
    memory_limit: str,
    type_ids: list[str],
    group_id: str,
    tags_text: object = "",
) -> str:
    edit_url = urljoin(base_url, f"/problem/{code}/edit")
    page = session.get(edit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form metadata HNCode {code}: HTTP {page.status_code}")
    data = collect_problem_edit_form_data(page.text)
    if not data:
        raise RuntimeError(f"Không tìm thấy form metadata HNCode cho {code}.")
    resolved_type_ids = resolve_hncode_type_ids(page.text, tags_text, type_ids or [TARGETS["hncode"]["type_id"]])
    data = set_form_fields(
        data,
        {
            "code": code,
            "name": name,
            "points": str(points or "100"),
            "time_limit": str(time_limit or "1.0"),
            "memory_limit": memory_limit_to_kb(memory_limit or "1048576"),
            "memory_unit": "KB",
            "group": group_id,
        },
        multi_updates={"types": resolved_type_ids},
        checkbox_updates={"partial": bool(partial)},
    )
    result = session.post(edit_url, data=data, headers={"Referer": edit_url}, allow_redirects=True, timeout=30)
    if not result.ok:
        raise RuntimeError(f"Cập nhật metadata HNCode {code} lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError(f"Form metadata HNCode {code} báo lỗi:\n" + "\n".join(errors))
    if "/accounts/login" in result.url or "/admin/login" in result.url:
        raise RuntimeError(f"Cập nhật metadata HNCode {code} bị chuyển về trang đăng nhập: {result.url}")
    verify = session.get(edit_url, timeout=30)
    if not verify.ok:
        raise RuntimeError(f"Không kiểm tra lại metadata HNCode {code}: HTTP {verify.status_code}")
    saved_points = input_value_from_page(verify.text, "points", "")
    saved_type_ids = selected_values(verify.text, "types")
    if not same_numeric_value(saved_points, str(points or "100")):
        debug_dir = RUNTIME / "debug_hncode_metadata"
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"{code}_post.html").write_text(result.text, encoding="utf-8", errors="replace")
        (debug_dir / f"{code}_verify.html").write_text(verify.text, encoding="utf-8", errors="replace")
        raise RuntimeError(
            f"HNCode nhận POST nhưng Points của {code} vẫn là {saved_points!r}, "
            f"không phải {points!r}. Đã lưu debug tại {debug_dir}."
        )
    missing_type_ids = [value for value in resolved_type_ids if value not in saved_type_ids]
    if missing_type_ids:
        debug_dir = RUNTIME / "debug_hncode_metadata"
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"{code}_post.html").write_text(result.text, encoding="utf-8", errors="replace")
        (debug_dir / f"{code}_verify.html").write_text(verify.text, encoding="utf-8", errors="replace")
        raise RuntimeError(
            f"HNCode nhận POST nhưng Problem Types của {code} vẫn là {saved_type_ids}, "
            f"chưa có {missing_type_ids}. Đã lưu debug tại {debug_dir}."
        )
    saved_description = textarea_value(verify.text, "description")
    ensure_hncode_vi_translation(session, base_url, code, name, saved_description)
    return result.url


def find_hncode_admin_problem_change_url(session, base_url: str, code: str) -> str:
    search_url = urljoin(base_url, f"/admin/judge/problem/?q={quote(code)}")
    page = session.get(search_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được trang admin tìm bài {code}: HTTP {page.status_code}")
    match = re.search(r"/admin/judge/problem/(\d+)/change/", page.text)
    if not match:
        raise RuntimeError(f"Không tìm thấy admin change URL cho bài {code}.")
    return urljoin(base_url, f"/admin/judge/problem/{match.group(1)}/change/")


def ensure_hncode_vi_translation(session, base_url: str, code: str, name: str, description: str) -> None:
    change_url = find_hncode_admin_problem_change_url(session, base_url, code)
    page = session.get(change_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được admin form bài {code}: HTTP {page.status_code}")
    data = collect_problem_edit_form_data(page.text)
    if not data:
        raise RuntimeError(f"Không đọc được admin form để cập nhật bản dịch tiếng Việt cho {code}.")
    object_id = re.search(r"/admin/judge/problem/(\d+)/change/", change_url)
    problem_id = object_id.group(1) if object_id else ""
    data = [(key, value) for key, value in data if "__prefix__" not in key]
    values = dict(data)
    total = int(values.get("translations-TOTAL_FORMS") or "0")
    target_index: int | None = None
    for index in range(total):
        if values.get(f"translations-{index}-language") == "vi":
            target_index = index
            break
    if target_index is None:
        target_index = total
        total += 1
    updates = {
        "translations-TOTAL_FORMS": str(total),
        f"translations-{target_index}-language": "vi",
        f"translations-{target_index}-name": name,
        f"translations-{target_index}-description": description,
        f"translations-{target_index}-id": values.get(f"translations-{target_index}-id", ""),
        f"translations-{target_index}-problem": values.get(f"translations-{target_index}-problem", problem_id),
    }
    data = set_single_form_fields(data, updates)
    data.append(("_save", "Lưu"))
    result = session.post(change_url, data=data, headers={"Referer": change_url}, allow_redirects=True, timeout=30)
    if not result.ok:
        raise RuntimeError(f"Cập nhật bản dịch tiếng Việt cho {code} lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError(f"Form bản dịch tiếng Việt HNCode {code} báo lỗi:\n" + "\n".join(errors))


def same_numeric_value(left: str, right: str) -> bool:
    try:
        return abs(float(str(left).strip()) - float(str(right).strip())) < 1e-9
    except (TypeError, ValueError):
        return str(left).strip() == str(right).strip()


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
) -> str:
    base_url = target_info["base_url"]

    def refresh_hncode_metadata() -> None:
        if target != "hncode":
            return
        tags_text = row.get("tags") or settings.get("tags")
        type_ids = type_ids_from_tags(tags_text, target) or [target_info["type_id"]]
        update_hncode_problem_metadata(
            session,
            base_url,
            bundle.code,
            name=row.get("name") or bundle.name,
            points=str(row.get("points") or settings.get("points") or "100"),
            partial=bool(row.get("partial", settings.get("partial", True))),
            time_limit=row.get("time_limit") or settings.get("time_limit") or "1.0",
            memory_limit=row.get("memory_limit") or settings.get("memory_limit") or "1048576",
            type_ids=type_ids,
            group_id=target_info["group_id"],
            tags_text=tags_text,
        )
        log_lines.append(f"{bundle.code}: đã cập nhật lại điểm và dạng bài tập HNCode.")

    exists = problem_exists_for_target(session, target, base_url, bundle.code)
    if exists:
        overwrite_row = bool(row.get("overwrite") or settings.get("overwrite_existing"))
        overwrite_statement = bool(settings.get("overwrite_statement") or overwrite_row) and bool(row.get("upload_statement"))
        overwrite_tests = bool(settings.get("overwrite_tests") or overwrite_row) and bool(row.get("upload_tests"))
        if not (overwrite_statement or overwrite_tests):
            raise ProblemAlreadyExists(f"Mã bài {bundle.code} đã tồn tại tại {problem_url(base_url, bundle.code)}")
        log_lines.append(f"{bundle.code}: bài đã tồn tại, chuyển sang chế độ ghi đè phần được chọn.")
        actions: list[str] = []
        if row.get("upload_statement"):
            if overwrite_statement:
                change_url = update_existing_problem_statement(session, target, base_url, bundle, settings)
                log_lines.append(f"{bundle.code}: đã ghi đè đề bài ({change_url}).")
                actions.append("đề bài")
            else:
                log_lines.append(f"{bundle.code}: không ghi đè đề bài vì chưa tích Ghi đè đề bài.")
        if row.get("upload_tests"):
            if overwrite_tests:
                if tests is None:
                    raise RuntimeError("Bài này không có bộ test trong dữ liệu chuẩn bị. Hãy bỏ tích Up test hoặc dùng file zip/gentest.")
                upload_tests_for_target(session, target, base_url, bundle.code, tests)
                log_lines.append(f"{bundle.code}: đã ghi đè {len(tests.input_files)} test.")
                actions.append("test")
            else:
                log_lines.append(f"{bundle.code}: không ghi đè test vì chưa tích Ghi đè test.")
        submit_if_requested(session, base_url, bundle, settings, log_lines)
        if overwrite_statement or overwrite_tests or overwrite_row:
            refresh_hncode_metadata()
        return "✓ Ghi đè " + " và ".join(actions) if actions else "✓ Không có phần ghi đè"
    actions: list[str] = []
    if row.get("upload_statement"):
        type_ids = type_ids_from_tags(row.get("tags") or settings.get("tags"), target) or [target_info["type_id"]]
        type_id = type_ids[0] if type_ids else target_info["type_id"]
        info = ProblemInfo(
            code=bundle.code,
            name=bundle.name,
            description=statement_for_target(
                target,
                read_text_smart(bundle.statement),
                skip_title_line=bool(settings.get("skip_statement_title", True)),
            ),
            points=str(row.get("points") or settings.get("points") or "100"),
            partial=bool(row.get("partial", settings.get("partial", True))),
            time_limit=row.get("time_limit") or settings.get("time_limit") or "1.0",
            memory_limit=memory_limit_to_kb(row.get("memory_limit") or settings.get("memory_limit") or "1048576"),
            memory_unit="KB",
        )
        change_url = create_hncode_problem(
            session,
            base_url,
            info,
            dest_code=bundle.code,
            type_id=",".join(type_ids),
            group_id=target_info["group_id"],
            public=False,
            allow_all_languages=False,
            allowed_language_ids=language_ids,
        ) if target != "tinhoctre" else create_tinhoctre_admin_problem(
            session,
            base_url,
            info,
            dest_code=bundle.code,
            type_id=type_id,
            group_id=target_info["group_id"],
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{bundle.code}: đã tạo đề qua admin form ({change_url}).")
        actions.append("tạo đề")
    else:
        log_lines.append(f"{bundle.code}: không upload đề.")

    if row.get("upload_tests"):
        if tests is None:
            raise RuntimeError("Bài này không có bộ test trong dữ liệu chuẩn bị. Hãy bỏ tích Up test hoặc dùng file zip/gentest.")
        upload_tests_for_target(session, target, base_url, bundle.code, tests)
        log_lines.append(f"{bundle.code}: đã upload {len(tests.input_files)} test.")
        actions.append("upload test")
    else:
        log_lines.append(f"{bundle.code}: không upload test.")

    submit_if_requested(session, base_url, bundle, settings, log_lines)
    if target == "hncode" and row.get("upload_statement"):
        refresh_hncode_metadata()
    return "✓ " + " và ".join(actions) if actions else "✓ Thành công"


def problem_exists_for_target(session, target: str, base_url: str, code: str) -> bool:
    if target == "tinhoctre":
        return tinhoctre_problem_exists(session, base_url, code)
    return upload_service.problem_exists_for_target(session, target, base_url, code)

def resolve_problem_code_for_upload(session, target: str, base_url: str, raw_code: str) -> tuple[str, str]:
    if target == "tinhoctre":
        return (raw_code or "").strip().lower(), ""
    return upload_service.resolve_problem_code_for_upload(session, target, base_url, raw_code)

def statement_for_target(target: str, statement: str, *, skip_title_line: bool = False) -> str:
    if target == "tinhoctre":
        return tinhoctre_service.statement_for_tinhoctre(statement, skip_title_line=skip_title_line)
    return upload_service.statement_for_target(target, statement, skip_title_line=skip_title_line)

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
    add_url = tinhoctre_service.admin_problem_add_url(base_url)
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
    if target == "tinhoctre":
        upload_tinhoctre_tests(session, base_url, code, tests)
        return
    upload_service.upload_tests_for_target(session, target, base_url, code, tests, upload_hncode_tests, upload_tinhoctre_tests)

def submit_if_requested(session, base_url: str, bundle: ProblemBundle, settings: dict, log_lines: list[str]) -> None:
    fallback = None if "hncode.edu.vn" in base_url else submit_solution
    upload_service.submit_if_requested(session, base_url, bundle, settings, log_lines, compact_form_red_errors, fallback_submit_solution=fallback)

def submit_solution_file(session, base_url: str, code: str, source_path: Path, preferred_languages: list[str]) -> str:
    return upload_service.submit_solution_file(session, base_url, code, source_path, preferred_languages, compact_form_red_errors)

def language_id_from_submit_page(page: str, preferred_languages: list[str]) -> str:
    return upload_service.language_id_from_submit_page(page, preferred_languages)

def normalize_language_label(label: str) -> str:
    return upload_service.normalize_language_label(label)

def language_ids_for_target(target: str, names: list[str]) -> list[str]:
    return upload_service.language_ids_for_target(TARGETS[target], names)

def memory_limit_to_kb(value: object) -> str:
    return upload_service.memory_limit_to_kb(value)

def type_id_from_tags(value: object) -> str:
    match = re.search(r"\b\d+\b", str(value or ""))
    return match.group(0) if match else ""


def type_ids_from_tags(value: object, target: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    numeric_ids = re.findall(r"\b\d+\b", text)
    if numeric_ids:
        return list(dict.fromkeys(numeric_ids))
    if target != "hncode":
        return []
    ids: list[str] = []
    for raw_tag in re.split(r"[,;|]+", text):
        tag = re.sub(r"\s+", " ", raw_tag.strip().lower())
        if not tag:
            continue
        type_id = HNCODE_TYPE_ALIASES.get(tag)
        if type_id and type_id not in ids:
            ids.append(type_id)
    return ids


def problem_url(base_url: str, code: str) -> str:
    return upload_service.problem_url(base_url, code)

def normalize_problem_code_for_target(code: str, target: str) -> str:
    return upload_service.normalize_problem_code_for_target(code, target)

def validate_problem_code_for_target(code: str, target: str) -> None:
    upload_service.validate_problem_code_for_target(code, target)

def test_data_url(base_url: str, code: str) -> str:
    return upload_service.test_data_url(base_url, code)

def session_from_cookie(cookie_header: str):
    s = tinhoctre_session()
    return tinhoctre_service.apply_cookie_header(s, cookie_header)


def tinhoctre_cookie_file() -> Path:
    return tinhoctre_service.cookie_file(RUNTIME)


def save_tinhoctre_cookie(cookie_header: str) -> None:
    tinhoctre_service.save_cookie(RUNTIME, cookie_header)


def load_tinhoctre_cookie() -> str:
    return tinhoctre_service.load_cookie(RUNTIME)


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
    return contest_service.contest_url(base_url, key)


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
    return hncode_service.find_problem_admin_id(session, base_url, code)


def public_contest_problem_codes(session, base_url: str, key: str) -> list[str]:
    return [row["code"] for row in public_contest_problem_rows(session, base_url, key)]


def public_contest_problem_rows(session, base_url: str, key: str) -> list[dict]:
    rows = hncode_service.list_contest_problems(session, base_url, key, default_points="100")
    if rows:
        return rows
    page = session.get(contest_url(base_url, key), timeout=30)
    if not page.ok:
        return []
    codes: list[str] = []
    for code in re.findall(r"(?:/problem/|/contest/" + re.escape(key) + r"/problems/)([A-Za-z0-9_-]+)", page.text):
        if code not in codes:
            codes.append(code)
    return [{"code": code, "title": code, "points": "100", "order": index} for index, code in enumerate(codes, 1)]


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


def strip_html_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<.*?>", " ", value, flags=re.S))).strip()


def compact_form_red_errors(page: str) -> list[str]:
    errors = []
    for block in re.findall(r'<div\b[^>]*class=["\'][^"\']*\bred\b[^"\']*["\'][^>]*>(.*?)</div>', page, re.S | re.I):
        text = strip_html_text(block)
        if text and text not in errors:
            errors.append(text)
    return errors


def extract_hncode_course_slug(value: str) -> str:
    return course_service.extract_course_slug(value)


def hncode_course_page_url(course_slug: str, path: str = "") -> str:
    return course_service.course_page_url(TARGETS["hncode"]["base_url"], course_slug, path)


def hncode_course_admin_id(session: requests.Session, course_slug: str) -> str:
    page = session.get(hncode_course_page_url(course_slug, "/edit_lessons"), timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được course {course_slug}: HTTP {page.status_code}")
    match = re.search(r"/admin/judge/course/(\d+)/change/", page.text)
    if not match:
        raise RuntimeError(f"Không đọc được ID admin của course {course_slug}.")
    return match.group(1)


def hncode_course_lessons(session: requests.Session, course_slug: str) -> list[dict]:
    page = session.get(hncode_course_page_url(course_slug, "/edit_lessons"), timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được danh sách lesson course {course_slug}: HTTP {page.status_code}")
    return course_service.parse_course_lessons_from_html(page.text)


def hncode_course_contests(session: requests.Session, course_slug: str) -> list[dict]:
    page = session.get(hncode_course_page_url(course_slug, "/contests"), timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được danh sách contest course {course_slug}: HTTP {page.status_code}")
    return course_service.parse_course_contests_from_html(page.text)


def find_hncode_course_lesson_url(session: requests.Session, course_slug: str, title: str) -> str | None:
    wanted = (title or "").strip().casefold()
    if not wanted:
        return None
    matches = [row for row in hncode_course_lessons(session, course_slug) if row.get("title", "").strip().casefold() == wanted]
    if not matches:
        return None
    chosen = matches[-1]
    return hncode_course_page_url(course_slug, f"/lesson/{chosen['key']}")


def find_hncode_course_contest_url(session: requests.Session, course_slug: str, contest_key: str) -> str | None:
    contest_key = (contest_key or "").strip()
    if not contest_key:
        return None
    for row in hncode_course_contests(session, course_slug):
        if row.get("key") == contest_key:
            return urljoin(TARGETS["hncode"]["base_url"], f"/contest/{contest_key}")
    return None


def default_course_clone_contest_key(source_key: str, dest_slug: str, suffix: str = "") -> str:
    return course_service.default_clone_contest_key(source_key, dest_slug, suffix)


def collect_form_with_field(page: str, field_name: str) -> list[tuple[str, str]]:
    parser = FormDataParser()
    parser.feed(page)
    for form in parser.forms:
        if any(name == field_name for name, _value in form):
            return form
    return []


def replace_form_fields(data: list[tuple[str, str]], updates: dict[str, str], remove_names: set[str] | None = None) -> list[tuple[str, str]]:
    remove_names = set(remove_names or set()) | set(updates)
    out = [(name, value) for name, value in data if name not in remove_names]
    out.extend((name, value) for name, value in updates.items())
    return out


def lesson_quiz_rows_from_page(page: str, lesson_id: str) -> list[dict]:
    prefix = f"quizzes_{lesson_id}"
    total = int(input_value_from_page(page, f"{prefix}-TOTAL_FORMS", "0") or "0")
    rows: list[dict] = []
    for index in range(total):
        quiz_id = selected_option_value(page, f"{prefix}-{index}-quiz", "") or input_value_from_page(page, f"{prefix}-{index}-quiz", "")
        if not quiz_id:
            continue
        rows.append(
            {
                "id": input_value_from_page(page, f"{prefix}-{index}-id", ""),
                "lesson": input_value_from_page(page, f"{prefix}-{index}-lesson", ""),
                "quiz": quiz_id,
                "points": input_value_from_page(page, f"{prefix}-{index}-points", "0"),
                "max_attempts": input_value_from_page(page, f"{prefix}-{index}-max_attempts", "0"),
                "order": input_value_from_page(page, f"{prefix}-{index}-order", str(index)),
                "is_visible": input_checked(page, f"{prefix}-{index}-is_visible"),
                "delete": input_checked(page, f"{prefix}-{index}-DELETE"),
            }
        )
    return rows


def remove_lesson_item_fields(data: list[tuple[str, str]], lesson_id: str) -> list[tuple[str, str]]:
    return lesson_service.remove_lesson_item_fields(data, lesson_id)


def append_lesson_quiz_formset(data: list[tuple[str, str]], lesson_id: str, rows: list[dict], initial_forms: int) -> list[tuple[str, str]]:
    prefix = f"quizzes_{lesson_id}"
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
                (f"{prefix}-{index}-quiz", str(row.get("quiz", ""))),
                (f"{prefix}-{index}-points", str(row.get("points", "0") or "0")),
                (f"{prefix}-{index}-max_attempts", str(row.get("max_attempts", "0") or "0")),
            ]
        )
        if row.get("is_visible"):
            out.append((f"{prefix}-{index}-is_visible", "on"))
        if row.get("delete"):
            out.append((f"{prefix}-{index}-DELETE", "on"))
    return out


def copy_hncode_lesson_items(session: requests.Session, dest_course_slug: str, dest_lesson_id: str, source_page: str, source_lesson_id: str) -> None:
    edit_url = hncode_course_page_url(dest_course_slug, f"/edit_lessons_new/{dest_lesson_id}")
    page = session.get(edit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form sửa lesson đích {dest_lesson_id}: HTTP {page.status_code}")
    form_data = collect_lesson_form_data(page.text, dest_lesson_id)
    if not form_data:
        raise RuntimeError(f"Không tìm thấy form danh sách bài/quiz trong lesson đích {dest_lesson_id}.")
    source_problems = lesson_problem_rows_from_page(source_page, source_lesson_id)
    source_quizzes = lesson_quiz_rows_from_page(source_page, source_lesson_id)
    if not source_problems and not source_quizzes:
        return
    base_data = remove_lesson_item_fields(form_data, dest_lesson_id)
    problem_rows = lesson_problem_rows_from_page(page.text, dest_lesson_id)
    quiz_rows = lesson_quiz_rows_from_page(page.text, dest_lesson_id)
    problem_initial = int(input_value_from_page(page.text, f"problems_{dest_lesson_id}-INITIAL_FORMS", str(len(problem_rows))) or str(len(problem_rows)))
    quiz_initial = int(input_value_from_page(page.text, f"quizzes_{dest_lesson_id}-INITIAL_FORMS", str(len(quiz_rows))) or str(len(quiz_rows)))
    existing_problem_ids = {str(row.get("problem")) for row in problem_rows}
    existing_quiz_ids = {str(row.get("quiz")) for row in quiz_rows}
    for row in source_problems:
        problem_id = str(row.get("problem") or "")
        if not problem_id or problem_id in existing_problem_ids:
            continue
        problem_rows.append(
            {
                "id": "",
                "lesson": str(dest_lesson_id),
                "problem": problem_id,
                "score": str(row.get("score") or "100"),
                "order": str(row.get("order") or len(problem_rows)),
                "delete": False,
            }
        )
        existing_problem_ids.add(problem_id)
    for row in source_quizzes:
        quiz_id = str(row.get("quiz") or "")
        if not quiz_id or quiz_id in existing_quiz_ids:
            continue
        quiz_rows.append(
            {
                "id": "",
                "lesson": str(dest_lesson_id),
                "quiz": quiz_id,
                "points": str(row.get("points") or "0"),
                "max_attempts": str(row.get("max_attempts") or "0"),
                "order": str(row.get("order") or len(quiz_rows)),
                "is_visible": bool(row.get("is_visible")),
                "delete": False,
            }
        )
        existing_quiz_ids.add(quiz_id)
    data = append_lesson_problem_formset(base_data, dest_lesson_id, problem_rows, problem_initial)
    data = append_lesson_quiz_formset(data, dest_lesson_id, quiz_rows, quiz_initial)
    result = session.post(edit_url, data=data, headers={"Referer": edit_url}, allow_redirects=True, timeout=60)
    if not result.ok:
        raise RuntimeError(f"Lưu danh sách bài/quiz lesson {dest_lesson_id} lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Form sửa lesson báo lỗi:\n" + "\n".join(errors))


def clone_hncode_lesson_native(session: requests.Session, source_course: str, lesson_id: str, title: str, dest_course_slug: str, dest_course_id: str) -> str:
    source_edit_url = hncode_course_page_url(source_course, f"/edit_lessons_new/{lesson_id}")
    source_page = session.get(source_edit_url, timeout=30)
    if not source_page.ok:
        raise RuntimeError(f"Không mở được form sửa lesson nguồn {lesson_id}: HTTP {source_page.status_code}")
    title = input_value_from_page(source_page.text, "title", title) or title
    points = input_value_from_page(source_page.text, "points", "100") or "100"
    content = textarea_value(source_page.text, "content")
    order = input_value_from_page(source_page.text, "order", "")
    create_url = hncode_course_page_url(dest_course_slug, "/lesson/create")
    page = session.get(create_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form tạo lesson ở course đích {dest_course_slug}: HTTP {page.status_code}")
    form_data = collect_form_with_field(page.text, "title")
    if not form_data:
        raise RuntimeError(f"Không tìm thấy form tạo lesson ở course đích {dest_course_slug}.")
    data = replace_form_fields(
        form_data,
        {"title": title, "points": points, "content": content, "order": order},
        remove_names={"is_visible"},
    )
    if input_checked(source_page.text, "is_visible"):
        data.append(("is_visible", "on"))
    result = session.post(create_url, data=data, headers={"Referer": create_url}, allow_redirects=True, timeout=60)
    if not result.ok:
        raise RuntimeError(f"Tạo lesson {lesson_id} ở course đích lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Form tạo lesson báo lỗi:\n" + "\n".join(errors))
    link = find_hncode_course_lesson_url(session, dest_course_slug, title)
    if not link:
        raise RuntimeError(f"Tạo lesson {lesson_id} xong nhung chua thay lesson moi trong course dich {dest_course_slug}.")
    match = re.search(r"/lesson/(\d+)", link)
    if not match:
        raise RuntimeError(f"Không đọc được ID lesson mới từ link {link}.")
    copy_hncode_lesson_items(session, dest_course_slug, match.group(1), source_page.text, lesson_id)
    return link


def hncode_contest_edit_problem_rows(page: str) -> list[dict]:
    total = int(input_value_from_page(page, "rows-TOTAL_FORMS", "0") or "0")
    rows: list[dict] = []
    for index in range(total):
        problem_id = selected_option_value(page, f"rows-{index}-problem", "") or input_value_from_page(page, f"rows-{index}-problem", "")
        if not problem_id:
            continue
        rows.append(
            {
                "problem": problem_id,
                "points": input_value_from_page(page, f"rows-{index}-points", "100") or "100",
                "order": input_value_from_page(page, f"rows-{index}-order", str(index + 1)) or str(index + 1),
            }
        )
    return rows


def clone_hncode_contest_native(session: requests.Session, contest_key: str, new_key: str, dest_course_slug: str, dest_course_id: str) -> str:
    source_url = urljoin(TARGETS["hncode"]["base_url"], f"/contest/{contest_key}/edit")
    source_page = session.get(source_url, timeout=30)
    if not source_page.ok:
        raise RuntimeError(f"Không mở được form sửa contest nguồn {contest_key}: HTTP {source_page.status_code}")
    name = input_value_from_page(source_page.text, "name", contest_key) or contest_key
    start_time = input_value_from_page(source_page.text, "start_time", "")
    end_time = input_value_from_page(source_page.text, "end_time", "")
    problem_rows = hncode_contest_edit_problem_rows(source_page.text)
    if not problem_rows:
        raise RuntimeError(f"Contest nguồn {contest_key} không có bài để clone.")
    add_url = hncode_course_page_url(dest_course_slug, "/add_contest")
    page = session.get(add_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form thêm contest vào course đích {dest_course_slug}: HTTP {page.status_code}")
    form_data = collect_form_with_field(page.text, "key")
    if not form_data:
        raise RuntimeError(f"Không tìm thấy form thêm contest vào course đích {dest_course_slug}.")
    data = replace_form_fields(
        form_data,
        {
            "points": "1000",
            "key": new_key,
            "name": name,
            "start_time": start_time,
            "end_time": end_time,
        },
        remove_names={"problems"},
    )
    for row in sorted(problem_rows, key=lambda item: int(str(item.get("order") or "0")) if str(item.get("order") or "0").isdigit() else 0):
        data.append(("problems", str(row["problem"])))
    result = session.post(add_url, data=data, headers={"Referer": add_url}, allow_redirects=True, timeout=90)
    if not result.ok:
        raise RuntimeError(f"Tạo contest {new_key} trong course đích lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Form thêm contest vào course báo lỗi:\n" + "\n".join(errors))
    link = find_hncode_course_contest_url(session, dest_course_slug, new_key)
    if not link:
        raise RuntimeError(f"Tạo contest {new_key} xong nhung chua thay trong course dich {dest_course_slug}.")
    return link


def extract_hncode_contest_key(value: str) -> str:
    return contest_service.extract_contest_key(value, "contest HNCode")


def contest_lesson_source_from_url(source: str, contest_url_value: str) -> str:
    return contest_service.source_from_contest_url(source, contest_url_value)


def extract_hncode_lesson_ref(value: str) -> tuple[str, str]:
    return lesson_service.extract_lesson_ref(value)


def hncode_lesson_url(course_slug: str, lesson_id: str) -> str:
    return lesson_service.lesson_url(TARGETS["hncode"]["base_url"], course_slug, lesson_id)


def hncode_lesson_edit_url(course_slug: str, lesson_id: str) -> str:
    return lesson_service.lesson_edit_url(TARGETS["hncode"]["base_url"], course_slug, lesson_id)


def contest_lesson_score(value: str, default: str = "100") -> str:
    return hncode_service.contest_lesson_score(value, default)


def extract_contest_problem_rows_from_html(page: str, contest_key: str = "", default_points: str = "100") -> list[dict]:
    return hncode_service.extract_contest_problem_rows_from_html(page, contest_key, default_points)


def hncode_contest_problem_rows(session, contest_key: str) -> list[dict]:
    rows = hncode_service.list_contest_problems(session, TARGETS["hncode"]["base_url"], contest_key, default_points="1")
    if not rows:
        raise RuntimeError(f"Không tìm thấy bài nào trong contest {contest_key}.")
    return rows


def source_problem_title(session: requests.Session, base_url: str, code: str) -> str:
    page = session.get(urljoin(base_url, f"/problem/{code}/edit"), timeout=30)
    if page.ok:
        title = input_value(page.text, "name", "")
        if title:
            return title
    public = session.get(urljoin(base_url, f"/problem/{code}"), timeout=30)
    if public.ok:
        match = re.search(r"<h1\b[^>]*>(.*?)</h1>", public.text, re.S | re.I)
        if match:
            title = strip_html_text(match.group(1))
            if title:
                return title
    return code


def extract_problem_link_rows_from_html(page: str, default_points: str = "") -> list[dict]:
    return hncode_service.extract_problem_link_rows_from_html(page, default_points)


def admin_problem_code_name_by_id(session: requests.Session, base_url: str, problem_id: str) -> tuple[str, str]:
    return hncode_service.find_problem_code_name_by_id(session, base_url, problem_id)


def hncode_lesson_problem_code_rows(session: requests.Session, course_slug: str, lesson_id: str) -> list[dict]:
    rows = hncode_service.list_lesson_problems(session, TARGETS["hncode"]["base_url"], course_slug, lesson_id)
    if not rows:
        raise RuntimeError(f"Không tìm thấy bài nào trong lesson {course_slug}/lesson/{lesson_id}.")
    return rows


def hnoj_contest_problem_rows(session: requests.Session, contest_key: str) -> list[dict]:
    rows = public_contest_problem_rows(session, TARGETS["hnoj"]["base_url"], contest_key)
    if rows:
        return rows
    try:
        info = fetch_contest_info(session, TARGETS["hnoj"]["base_url"], contest_key)
    except Exception:
        codes = public_contest_problem_codes(session, TARGETS["hnoj"]["base_url"], contest_key)
        rows = [
            {
                "code": code,
                "title": source_problem_title(session, TARGETS["hnoj"]["base_url"], code),
                "points": "100",
                "order": index,
            }
            for index, code in enumerate(codes, 1)
        ]
        if rows:
            return rows
        raise
    rows: list[dict] = []
    for index, item in enumerate(info.get("problems", []), 1):
        code = item.get("code", "")
        if not code:
            continue
        order_value = item.get("order") or index
        rows.append(
            {
                "code": code,
                "title": source_problem_title(session, TARGETS["hnoj"]["base_url"], code),
                "points": item.get("points") or "100",
                "order": int(order_value) if str(order_value).isdigit() else index,
            }
        )
    if not rows:
        raise RuntimeError(f"Không tìm thấy bài nào trong contest HNOJ {contest_key}.")
    return rows


def collect_lesson_form_data(page: str, lesson_id: str) -> list[tuple[str, str]]:
    parser = FormDataParser()
    parser.feed(page)
    marker = f"problems_{lesson_id}-TOTAL_FORMS"
    for form in parser.forms:
        if any(name == marker for name, _value in form):
            return form
    return []


def remove_lesson_problem_fields(data: list[tuple[str, str]], lesson_id: str) -> list[tuple[str, str]]:
    prefix = f"problems_{lesson_id}-"
    return [(name, value) for name, value in data if not name.startswith(prefix)]


def lesson_problem_rows_from_page(page: str, lesson_id: str) -> list[dict]:
    return lesson_service.parse_lesson_problem_rows(page, lesson_id)


def append_lesson_problem_formset(data: list[tuple[str, str]], lesson_id: str, rows: list[dict], initial_forms: int) -> list[tuple[str, str]]:
    return lesson_service.append_lesson_problem_formset(data, lesson_id, rows, initial_forms)


def copy_hncode_contest_to_lesson(session, course_slug: str, lesson_id: str, problem_refs: list[dict]) -> str:
    edit_url = hncode_lesson_edit_url(course_slug, lesson_id)
    page = session.get(edit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form sửa lesson HNCode: HTTP {page.status_code}")
    form_data = collect_lesson_form_data(page.text, lesson_id)
    if not form_data:
        raise RuntimeError("Không tìm thấy form danh sách bài trong lesson HNCode.")
    base_data = remove_lesson_item_fields(form_data, lesson_id)
    current_rows = lesson_problem_rows_from_page(page.text, lesson_id)
    quiz_rows = lesson_quiz_rows_from_page(page.text, lesson_id)
    initial_forms = int(input_value_from_page(page.text, f"problems_{lesson_id}-INITIAL_FORMS", str(len(current_rows))) or str(len(current_rows)))
    quiz_initial = int(input_value_from_page(page.text, f"quizzes_{lesson_id}-INITIAL_FORMS", str(len(quiz_rows))) or str(len(quiz_rows)))
    existing_problem_ids = {str(row.get("problem")) for row in current_rows if row.get("problem")}
    next_order = 1
    if current_rows:
        order_values = [int(str(row.get("order") or "0")) for row in current_rows if str(row.get("order") or "0").isdigit()]
        next_order = (max(order_values) + 1) if order_values else len(current_rows) + 1
    added = 0
    for ref in problem_refs:
        problem_id = str(ref.get("problem_id") or ref.get("id") or "")
        if not problem_id or problem_id in existing_problem_ids:
            continue
        current_rows.append(
            {
                "id": "",
                "lesson": str(lesson_id),
                "problem": problem_id,
                "score": str(ref.get("score") or ref.get("points") or "100"),
                "order": str(next_order + added),
                "delete": False,
            }
        )
        existing_problem_ids.add(problem_id)
        added += 1
    if added == 0:
        return hncode_lesson_url(course_slug, lesson_id)
    data = append_lesson_problem_formset(base_data, lesson_id, current_rows, initial_forms)
    data = append_lesson_quiz_formset(data, lesson_id, quiz_rows, quiz_initial)
    result = session.post(edit_url, data=data, headers={"Referer": edit_url}, allow_redirects=True, timeout=60)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    debug_post = RUNTIME / "hncode_lesson_copy_last_post.html"
    debug_post.write_text(result.text, encoding="utf-8", errors="replace")
    if not result.ok:
        raise RuntimeError(f"Lưu lesson lỗi HTTP {result.status_code}")
    errors = form_errors(result.text) + compact_form_red_errors(result.text)
    if errors:
        raise RuntimeError("Form sửa lesson báo lỗi:\n" + "\n".join(errors))
    verify = session.get(edit_url, timeout=30)
    if verify.ok:
        debug_verify = RUNTIME / "hncode_lesson_copy_last_verify.html"
        debug_verify.write_text(verify.text, encoding="utf-8", errors="replace")
        saved_ids = {row["problem"] for row in lesson_problem_rows_from_page(verify.text, lesson_id)}
        missing = [str(ref.get("problem_id") or ref.get("id")) for ref in problem_refs if str(ref.get("problem_id") or ref.get("id")) not in saved_ids]
        if missing:
            raise RuntimeError(
                "Lesson chưa lưu đủ bài: "
                + ", ".join(missing)
                + f"\nĐã lưu HTML debug: {debug_post} và {debug_verify}"
            )
    return hncode_lesson_url(course_slug, lesson_id)


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
        return api_response.api_error("Chưa nhập mã contest cần chuyển.")
    if source == dest:
        return api_response.api_error("Nguồn và đích đang trùng nhau.")
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
        return api_response.api_success(message="Đã chuẩn bị dữ liệu", rows=rows, log="\n".join(log_lines), prepare_id=prepare_id)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


@app.post("/api/confirm-contest-transfer")
def api_confirm_contest_transfer():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id")
    prepare_id = payload.get("prepare_id")
    try:
        state = load_prepared_contest_transfer(prepare_id) if prepare_id else None
    except Exception:
        state = None
    if not state:
        progress_finish(progress_id, False, "Dữ liệu chuẩn bị chuyển contest đã hết hạn")
        return api_response.api_error("Dữ liệu chuẩn bị chuyển contest đã hết hạn. Hãy bấm Chuẩn bị dữ liệu lại.")
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
        return api_response.api_success(message="Đã hoàn tất" if ok else "Có lỗi trong quá trình xử lý", rows=result_rows, log="\n".join(log_lines), ok=ok)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


@app.post("/api/create-contest")
def api_create_contest():
    payload = request.get_json(force=True)
    target = payload["target"]
    key = payload.get("key", "").strip()
    name = payload.get("name", "").strip()
    problems = [code.strip() for code in payload.get("problems", []) if code.strip()]
    if not key or not name or not problems:
        return api_response.api_error("Cần nhập mã contest, tên contest và danh sách mã bài.")
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
        return api_response.api_error(str(exc))


@app.post("/api/prepare-transfer")
def api_prepare_transfer():
    payload = request.get_json(force=True)
    progress_id = payload.get("progress_id")
    source = payload["source"]
    dest = payload["dest"]
    codes = [code.strip() for code in payload.get("codes", []) if code.strip()]
    if not codes:
        return api_response.api_error("Chưa nhập mã bài cần chuyển.")
    if source == dest:
        return api_response.api_error("Nguồn và đích đang trùng nhau.")
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
                rows.append(
                    transfer_service.make_prepare_transfer_row(
                        original_code=code,
                        info=info,
                        zip_path=zip_path,
                        cases=cases,
                        source_base_url=TARGETS[source]["base_url"],
                        dest=dest,
                        settings=payload.get("settings", {}),
                        normalize_problem_code_for_target=normalize_problem_code_for_target,
                        test_data_url=test_data_url,
                    )
                )
                log_lines.append(f"- {code}: {info.name}, {len(cases)} test, bộ test {test_data_url(TARGETS[source]['base_url'], code)}")
            except Exception as exc:
                rows.append(
                    transfer_service.make_failed_prepare_transfer_row(
                        code=code,
                        source_base_url=TARGETS[source]["base_url"],
                        settings=payload.get("settings", {}),
                        test_data_url=test_data_url,
                    )
                )
                log_lines.append(f"✗ {code}: {exc}")
            progress_update(progress_id, phase="prepare-transfer", done=index, total=len(codes), rows=rows, message=f"{code}: {rows[-1]['status']}")
        prepared_transfers[prepare_id] = {"root": root, "source": source, "dest": dest, "items": state_items}
        progress_finish(progress_id, True, f"Đã đọc {len(rows)}/{len(codes)} bài")
        return api_response.api_success(message="Đã chuẩn bị dữ liệu", rows=rows, log="\n".join(log_lines), prepare_id=prepare_id)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


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
        return api_response.api_error("Nguồn và đích đang trùng nhau", rows=result_rows, log="\n".join(log_lines), status=200)

    try:
        dest_account = payload["dest_account"]
        prepare_id = payload.get("prepare_id")
        if not prepare_id or prepare_id not in prepared_transfers:
            return api_response.api_error("Dữ liệu chuẩn bị chuyển bài đã hết hạn hoặc server vừa khởi động lại. Hãy bấm Chuẩn bị dữ liệu lại rồi mới Xác nhận chuyển bài.")
        state = prepared_transfers[prepare_id]
        dst = login_hncode(TARGETS[dest]["base_url"], dest_account["username"], dest_account["password"])
        out_dir = state["root"]
        language_ids = language_ids_for_target(dest, settings.get("languages", []))

        total = transfer_service.selected_count(rows)
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
                transfer_service.apply_transfer_row_to_info(info, row, settings)
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
        return api_response.api_success(message="Đã hoàn tất" if ok else "Có lỗi trong quá trình xử lý", rows=result_rows, log="\n".join(log_lines), ok=ok)
    except Exception as exc:
        progress_finish(progress_id, False, str(exc))
        return api_response.api_error(str(exc))


def upload_transfer_to_dmoj(session, dest: str, dest_code: str, info: ProblemInfo, zip_path: Path, cases, row: dict, language_ids: list[str], log_lines: list[str]) -> None:
    transfer_service.upload_transfer_to_dmoj(
        session=session,
        dest=dest,
        dest_code=dest_code,
        info=info,
        zip_path=zip_path,
        cases=cases,
        row=row,
        language_ids=language_ids,
        log_lines=log_lines,
        target_info=TARGETS[dest],
        problem_info_for_target=problem_info_for_target,
        destination_problem_exists=destination_problem_exists,
        problem_url=problem_url,
        create_problem=create_hncode_problem,
        upload_hncode_tests=upload_hncode_tests,
        upload_hnoj_tests=upload_tinhoctre_tests,
        generated_tests_cls=GeneratedTests,
        problem_already_exists_cls=ProblemAlreadyExists,
    )


def upload_transfer_to_tinhoctre(session, dest: str, dest_code: str, info: ProblemInfo, zip_path: Path, cases, row: dict, out_dir: Path, language_ids: list[str], log_lines: list[str]) -> None:
    transfer_service.upload_transfer_to_tinhoctre(
        session=session,
        dest=dest,
        dest_code=dest_code,
        info=info,
        zip_path=zip_path,
        cases=cases,
        row=row,
        out_dir=out_dir,
        language_ids=language_ids,
        log_lines=log_lines,
        target_info=TARGETS[dest],
        problem_info_for_target=problem_info_for_target,
        problem_exists=tinhoctre_problem_exists,
        problem_url=problem_url,
        create_problem=create_tinhoctre_admin_problem,
        upload_tests=upload_tinhoctre_tests,
        generated_tests_cls=GeneratedTests,
        problem_bundle_cls=ProblemBundle,
        problem_already_exists_cls=ProblemAlreadyExists,
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("TOOL_OJ_HOST", "127.0.0.1"),
        port=int(os.getenv("TOOL_OJ_PORT", "5050")),
        debug=False,
    )
