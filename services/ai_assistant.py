"""Offline helpers for AI-assisted statement preparation.

The tool does not log in to consumer AI websites or store third-party
passwords. These helpers prepare prompts and validate the result users paste
back from an AI chat surface.
"""

from __future__ import annotations

import html
import base64
import json
import mimetypes
import re
import time
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import requests


TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_OPENROUTER_MODEL = "deepseek/deepseek-v4-flash-0731"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
]


def read_text_smart_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_docx_text(data: bytes) -> str:
    import io

    paragraphs: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [name for name in archive.namelist() if name.startswith("word/") and name.endswith(".xml")]
        for name in sorted(names):
            if name != "word/document.xml" and not name.startswith("word/header") and not name.startswith("word/footer"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            for para in root.findall(".//w:p", ns):
                text = "".join(node.text or "" for node in para.findall(".//w:t", ns)).strip()
                if text:
                    paragraphs.append(text)
    return "\n".join(paragraphs).strip()


def extract_pdf_text(data: bytes) -> str:
    import io

    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception as exc:
            raise RuntimeError("Máy chưa có thư viện đọc PDF (`pypdf` hoặc `PyPDF2`).") from exc
    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page).strip()


def extract_source_text(filename: str, data: bytes) -> tuple[str, str]:
    suffix = Path(filename or "").suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return read_text_smart_bytes(data).strip(), "Đã đọc file text/Markdown."
    if suffix == ".docx":
        text = extract_docx_text(data)
        return text, "Đã đọc text từ file Word .docx." if text else "File .docx không có text đọc được."
    if suffix == ".pdf":
        text = extract_pdf_text(data)
        return text, "Đã đọc text từ file PDF." if text else "PDF có thể là scan/ảnh nên không có text đọc được."
    if suffix in IMAGE_SUFFIXES:
        return "", "File là ảnh. Hãy đính kèm ảnh trực tiếp vào Gemini cùng prompt này để Gemini đọc ảnh."
    if suffix == ".doc":
        return "", "File .doc cũ chưa hỗ trợ đọc trực tiếp. Hãy lưu lại thành .docx hoặc PDF/text."
    return read_text_smart_bytes(data).strip(), "Đã thử đọc file theo dạng text."


def normalize_statement_for_target(statement: str, target: str) -> str:
    text = str(statement or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if target == "hncode":
        return text.replace("~", "$")
    return text.replace("$", "~")


def strip_markdown_fence(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    return value


def _ascii_label(value: str) -> str:
    value = str(value or "").strip().replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def is_forbidden_statement_heading(line: str) -> bool:
    stripped = str(line or "").strip()
    if not stripped:
        return False
    stripped = stripped.lstrip("#").strip().strip(":：").strip()
    return _ascii_label(stripped) in {"de bai", "problem statement", "statement", "bai toan"}


def clean_statement_markdown(markdown: str) -> str:
    text = strip_markdown_fence(markdown)
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and is_forbidden_statement_heading(lines[0]):
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
    if lines:
        header_probe = parse_statement_header("\n".join(lines))
        code_ok = bool(re.fullmatch(r"[A-Za-z0-9_\-]+", header_probe.get("code") or ""))
        if len(header_probe.get("parts") or []) >= 2 and header_probe.get("name") and code_ok:
            idx = 1
            while idx < len(lines) and not lines[idx].strip():
                idx += 1
            if idx < len(lines) and is_forbidden_statement_heading(lines[idx]):
                del lines[idx]
    return "\n".join(lines).strip()


def ensure_statement_header(
    markdown: str,
    *,
    name: str = "",
    code: str = "",
    points: str = "",
    tags: object = "",
) -> str:
    text = clean_statement_markdown(markdown)
    header = parse_statement_header(text)
    code_ok = bool(re.fullmatch(r"[A-Za-z0-9_\-]+", header.get("code") or ""))
    if len(header.get("parts") or []) >= 2 and header.get("name") and code_ok:
        return text
    tag_text = ", ".join(str(item).strip() for item in tags if str(item).strip()) if isinstance(tags, list) else str(tags or "").strip()
    header_name = str(name or header.get("name") or code or "Bai").strip()
    header_code = str(code or header.get("code") or "bai").strip()
    header_points = str(points or header.get("points") or "100").strip()
    first_line = f"{header_name} | {header_code} | {header_points}"
    if tag_text:
        first_line += f" | {tag_text}"
    return (first_line + "\n\n" + text).strip()


def target_math_note(target: str) -> str:
    if target == "hncode":
        return "Dùng ký hiệu `$...$` cho công thức; nếu nguồn dùng `~...~` thì đổi sang `$...$`."
    return "Dùng ký hiệu `~...~` cho công thức; nếu nguồn dùng `$...$` thì đổi sang `~...~`."


def build_statement_prompt(
    *,
    target: str,
    source_text: str,
    filename: str = "",
    problem_name: str = "",
    problem_code: str = "",
    points: str = "100",
    tags: str = "",
) -> str:
    target_label = "HNCode" if target == "hncode" else "HNOJ"
    header_hint = "Tên bài | Mã bài | Điểm | Tags"
    given = []
    if problem_name:
        given.append(f"- Tên bài gợi ý: {problem_name}")
    if problem_code:
        given.append(f"- Mã bài gợi ý: {problem_code}")
    if points:
        given.append(f"- Điểm gợi ý: {points}")
    if tags:
        given.append(f"- Tags gợi ý: {tags}")
    given_text = "\n".join(given) if given else "- Chưa có metadata gợi ý, hãy tự suy luận từ đề."
    source_block = source_text.strip() or (
        "Tôi sẽ đính kèm ảnh/PDF scan trực tiếp trong Gemini. Hãy đọc nội dung từ file đính kèm đó."
    )
    return f"""Bạn là trợ lý chuẩn hóa đề bài lập trình thi học sinh.

Hãy viết lại đề bài theo format Markdown để up lên {target_label}.

Yêu cầu bắt buộc:
- Dòng đầu tiên đúng dạng: `{header_hint}`.
- Nếu thiếu điểm thì dùng `{points or "100"}`.
- Tags viết ngắn gọn, phân tách bằng dấu phẩy.
- Giữ nguyên ý nghĩa đề, input/output, ví dụ, giới hạn, ràng buộc.
- Sửa lỗi font, lỗi OCR, lỗi xuống dòng, lỗi chính tả rõ ràng nếu có.
- Không tự bịa dữ kiện, giới hạn, ví dụ. Nếu thông tin thiếu thì ghi rõ `Cần bổ sung: ...`.
- {target_math_note(target)}
- Chỉ trả về Markdown cuối cùng, không giải thích thêm.

Metadata gợi ý:
{given_text}

Nguồn file: {filename or "dán trực tiếp"}

Nội dung đề gốc hoặc ghi chú file đính kèm:
```text
{source_block}
```
""".strip()


def first_nonempty_line(text: str) -> str:
    for line in str(text or "").splitlines():
        if line.strip():
            return line.strip().strip("#* ")
    return ""


def parse_statement_header(markdown: str) -> dict:
    parts = [part.strip() for part in first_nonempty_line(markdown).split("|")]
    return {
        "name": parts[0] if len(parts) > 0 else "",
        "code": parts[1] if len(parts) > 1 else "",
        "points": parts[2] if len(parts) > 2 else "",
        "tags": parts[3] if len(parts) > 3 else "",
        "parts": parts,
    }


def validate_statement_markdown(markdown: str, target: str) -> tuple[list[dict], dict]:
    text = clean_statement_markdown(markdown)
    header = parse_statement_header(text)
    checks = []

    def add(name: str, ok: bool, message: str) -> None:
        checks.append({"name": name, "ok": ok, "status": "✓ OK" if ok else "✗ Lỗi", "message": message})

    add("Có nội dung", bool(text), "Đã có nội dung Markdown." if text else "Chưa có nội dung Markdown.")
    add(
        "Dòng đầu metadata",
        len(header["parts"]) >= 2 and bool(header["name"]) and bool(header["code"]),
        "Dòng đầu đọc được Tên bài | Mã bài." if len(header["parts"]) >= 2 and header["name"] and header["code"] else "Dòng đầu cần dạng: Tên bài | Mã bài | Điểm | Tags.",
    )
    code_ok = bool(re.fullmatch(r"[A-Za-z0-9_\\-]+", header["code"] or ""))
    add("Mã bài", code_ok, "Mã bài hợp lệ." if code_ok else "Mã bài nên chỉ gồm chữ, số, gạch dưới hoặc gạch ngang.")
    points_ok = (not header["points"]) or bool(re.fullmatch(r"\d+(?:\.\d+)?", header["points"]))
    add("Điểm", points_ok, "Điểm hợp lệ hoặc để trống." if points_ok else "Điểm nên là số, ví dụ 100.")
    if target == "hncode":
        math_ok = "~" not in text
        math_message = "Đã dùng `$` cho HNCode." if math_ok else "HNCode nên dùng `$`, còn thấy ký tự `~`."
    else:
        math_ok = "$" not in text
        math_message = "Đã dùng `~` cho HNOJ/TinHocTre." if math_ok else "HNOJ/TinHocTre nên dùng `~`, còn thấy ký tự `$`."
    add("Ký hiệu công thức", math_ok, math_message)
    body_ok = len(text.splitlines()) >= 3
    lines = text.splitlines()
    forbidden_heading_ok = True
    if lines and is_forbidden_statement_heading(lines[0]):
        forbidden_heading_ok = False
    if len(lines) >= 2:
        idx = 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx < len(lines) and is_forbidden_statement_heading(lines[idx]):
            forbidden_heading_ok = False
    add("Không có heading Đề bài", forbidden_heading_ok, "Không có heading `# Đề bài` thừa." if forbidden_heading_ok else "Không viết `# Đề bài`/`## Đề bài` ở đầu đề.")
    add("Phần thân đề", body_ok, "Có phần thân đề sau dòng metadata." if body_ok else "Nên có nội dung đề sau dòng đầu.")
    requirement_ok = "**Yêu cầu:**" in text or "**Yeu cau:**" in text
    add("Dòng yêu cầu", requirement_ok, "Có dòng `**Yêu cầu:**`." if requirement_ok else "Thiếu dòng `**Yêu cầu:**` sau mô tả bài toán.")
    headings_ok = all(heading in text for heading in ("#### Input", "#### Output", "#### Example"))
    add("Heading Input/Output/Example", headings_ok, "Có đủ `#### Input`, `#### Output`, `#### Example`." if headings_ok else "Thiếu một trong các heading `#### Input`, `#### Output`, `#### Example`.")
    has_file_io = bool(re.findall(r"\b[A-Za-z0-9_./-]+\.(?:INP|OUT)\b", text, flags=re.IGNORECASE))
    stdin_example_ok = '???+ "Input"' in text and '???+ success "Output"' in text
    file_input_example_ok = bool(re.search(r'\?\?\?\+\s+"[^"]+\.(?:INP)"', text, flags=re.IGNORECASE))
    file_output_example_ok = bool(re.search(r'\?\?\?\+\s+success\s+"[^"]+\.(?:OUT)"', text, flags=re.IGNORECASE))
    example_ok = '!!! question' in text and "```sample" in text and ((file_input_example_ok and file_output_example_ok) if has_file_io else stdin_example_ok)
    add("Format Example", example_ok, "Example dùng đúng admonition và code block `sample`." if example_ok else "Example cần dùng `!!! question`, `???+ \"Input\"`, `???+ success \"Output\"` và code block `sample`.")
    if has_file_io:
        file_structure_ok = bool(re.search(r"\.INP\b", text, flags=re.IGNORECASE)) and bool(re.search(r"\.OUT\b", text, flags=re.IGNORECASE))
        add("Cấu trúc đọc ghi file", file_structure_ok, "Đã nêu rõ file `.INP` và `.OUT`." if file_structure_ok else "Bài đọc ghi file phải nêu rõ cả file `.INP` và `.OUT`.")
    else:
        lower_text = text.lower()
        stdio_structure_ok = any(token in lower_text for token in ("stdin", "bàn phím", "ban phim", "dòng", "dong"))
        add("Cấu trúc stdin/stdout", stdio_structure_ok, "Bài không đọc ghi file có mô tả Input/Output theo stdin/stdout." if stdio_structure_ok else "Bài không đọc ghi file nên mô tả dữ liệu đọc từ stdin/bàn phím.")
    meta = {key: header[key] for key in ("name", "code", "points", "tags")}
    meta["valid"] = all(row["ok"] for row in checks)
    meta["normalized_markdown"] = normalize_statement_for_target(text, target)
    return checks, meta


def selected_parts_text(options: dict) -> str:
    parts = []
    if options.get("statement", True):
        parts.append("- Chuẩn hóa đề bài Markdown theo đúng format HNCode/HNOJ.")
    if options.get("metadata", True):
        parts.append("- Đề xuất `points`, `tags`, `allows_partial_points`, `memory_limit_mb`, `allowed_languages`.")
    if options.get("solution", False):
        parts.append("- Viết/cập nhật phần Solutions gồm tóm tắt, nhận xét, thuật toán, độ phức tạp và code C++ mẫu.")
    if options.get("test_review", True):
        parts.append("- Nhận xét bộ test hiện có và đề xuất số lượng/nhóm test cần bổ sung nếu thiếu.")
    return "\n".join(parts) or "- Chỉ rà soát và báo cáo vấn đề."


def extract_numbered_section(reference_text: str, start_heading: str, next_heading: str, max_chars: int = 12000) -> str:
    text = str(reference_text or "")
    start = text.find(start_heading)
    if start < 0:
        return ""
    end = text.find(next_heading, start + 1)
    section = text[start : end if end >= 0 else len(text)].strip()
    if len(section) > max_chars:
        section = section[:max_chars].rstrip() + "\n..."
    return section


def extract_statement_guidelines(reference_text: str, max_chars: int = 16000) -> str:
    section_3 = extract_numbered_section(reference_text, "## 3. Việc 1: Chuẩn hoá đề bài", "\n## 4.", max_chars)
    section_4 = extract_numbered_section(reference_text, "## 4. Việc 2: Kiểm tra tính đúng đắn của đề", "\n## 5.", max_chars)
    joined = "\n\n".join(part for part in (section_3, section_4) if part)
    if len(joined) > max_chars:
        joined = joined[:max_chars].rstrip() + "\n..."
    return joined


def extract_points_guidelines(reference_text: str, max_chars: int = 12000) -> str:
    text = str(reference_text or "")
    start = text.find("## 6. Việc 4: Points")
    if start < 0:
        start = text.find("## 6.")
    if start < 0:
        return ""
    end = text.find("\n## 7.", start + 1)
    section = text[start : end if end >= 0 else len(text)].strip()
    if len(section) > max_chars:
        section = section[:max_chars].rstrip() + "\n..."
    return section


def build_hncode_normalization_prompt(reference_text: str, snapshot: dict, options: dict) -> str:
    target = options.get("target") or "hncode"
    target_label = "HNCode" if target == "hncode" else "HNOJ"
    code = snapshot.get("code") or ""
    name = snapshot.get("name") or ""
    statement = snapshot.get("statement") or ""
    solution = snapshot.get("solution") or ""
    test_summary = snapshot.get("test_summary") or ""
    statement_guidelines = extract_statement_guidelines(reference_text)
    points_guidelines = extract_points_guidelines(reference_text)
    return f"""Bạn là trợ lý chuẩn hóa bài lập trình cho {target_label}.

Hãy xử lý bài `{code}` - `{name}` theo tài liệu chuẩn hóa bên dưới.

Phần cần làm:
{selected_parts_text(options)}

Yêu cầu trả về:
- Chỉ trả về JSON hợp lệ, không bọc ```json.
- Không bọc `statement_markdown` trong ```markdown.
- Nếu có LaTeX/backslash trong JSON string thì phải escape đúng JSON, ví dụ dùng `\\leq`, `\\times`, `\\n`.
- JSON có đúng các field:
  - `code`: mã bài.
  - `name`: tên bài chuẩn.
  - `statement_markdown`: đề bài Markdown chuẩn.
  - `points`: điểm/độ khó đề xuất.
  - `tags`: mảng tag chuẩn.
  - `allows_partial_points`: true/false.
  - `memory_limit_mb`: số MB.
  - `allowed_languages`: mảng ngôn ngữ.
  - `solution_markdown`: nội dung Solutions, để chuỗi rỗng nếu không được yêu cầu hoặc chưa đủ chắc.
  - `test_review`: nhận xét bộ test.
  - `issues`: mảng vấn đề cần giáo viên kiểm tra.
  - `confidence`: `high`, `medium` hoặc `low`.
- Nếu thiếu dữ kiện, không tự bịa; ghi rõ trong `issues`.
- Với HNCode dùng `$...$` cho công thức. Với HNOJ dùng `~...~`.
- Khi viết `statement_markdown`, bắt buộc tuân thủ quy tắc chuẩn hoá đề bài bên dưới.
- `statement_markdown` phải có dòng đầu metadata, rồi phần thân đề có `**Yêu cầu:**`, `#### Input`, `#### Output`, `#### Example`.
- Example trên HNCode phải dùng admonition `!!! question`, `???+ "Input"`, `???+ success "Output"` và code block ```sample.
- Nếu bài có nhiều ví dụ, mỗi ví dụ là một khối `!!! question "Test k"`.
- Khi đánh giá `points`, bắt buộc dùng quy tắc Points bên dưới: đây là độ khó kiểu Codeforces/rating, không phải điểm contest.
- `points` nên chọn mốc gần nhất trong các mốc 800, 900, 1000, ..., 2800+.
- Không được chỉ nhìn tag để gán points; phải xét độ khó hiểu đề, nhận xét, thuật toán, cài đặt, case biên, chứng minh và giới hạn dữ liệu.
- Trong `test_review` hoặc `issues`, nếu điểm chỉ là tạm thời do thiếu đề/giới hạn/lời giải, hãy ghi rõ.

Quy tắc chuẩn hoá đề bài:
```text
Quy tắc bổ sung bắt buộc:
- Không viết `# Đề bài`, `## Đề bài`, `# Statement` ở đầu `statement_markdown`; sau dòng metadata đi thẳng vào mô tả bài.
- Không tạo field/phần `Dịch`, `Translation`, `Vietnamese translation`; chỉ trả về nội dung đề chính trong `statement_markdown`.
- Nếu bài không đọc ghi file: `#### Input`/`#### Output` mô tả dữ liệu từ stdin/stdout, example dùng nhãn `Input` và `Output`.
- Nếu bài đọc ghi file: giữ đúng tên file `.INP`/`.OUT` trong `#### Input`/`#### Output`, example dùng nhãn `TENFILE.INP` và `TENFILE.OUT`; solution C++ phải dùng `freopen` đúng tên file.

{statement_guidelines}
```

Quy tắc đánh giá Points:
```text
{points_guidelines}
```

Tài liệu chuẩn hóa:
```text
{reference_text[:30000]}
```

Dữ liệu bài hiện tại:
```text
Mã bài: {code}
Tên bài: {name}
Points hiện tại: {snapshot.get("points") or ""}
Partial hiện tại: {snapshot.get("partial")}
Time limit: {snapshot.get("time_limit") or ""}
Memory limit: {snapshot.get("memory_limit") or ""} {snapshot.get("memory_unit") or ""}
Test summary:
{test_summary}

Đề bài hiện tại:
{statement}

Solutions hiện tại:
{solution}
```
""".strip()


def gemini_generate(
    *,
    api_key: str,
    prompt: str,
    model: str = DEFAULT_GEMINI_MODEL,
    files: list[dict] | None = None,
    timeout: int = 120,
) -> str:
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("Ch?a nh?p Google AI API key.")
    model_name = (model or DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    parts = [{"text": prompt}]
    for item in files or []:
        data = item.get("data") or b""
        if not data:
            continue
        mime_type = item.get("mime_type") or "application/octet-stream"
        parts.append({"inline_data": {"mime_type": mime_type, "data": base64.b64encode(data).decode("ascii")}})
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.9,
            "responseMimeType": "application/json",
        },
    }
    models_to_try: list[str] = []
    for candidate in [model_name, *GEMINI_FALLBACK_MODELS]:
        candidate = (candidate or "").strip()
        if candidate and candidate not in models_to_try:
            models_to_try.append(candidate)
    attempts: list[str] = []
    response = None
    for candidate in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent"
        response = requests.post(url, params={"key": key}, json=payload, timeout=timeout)
        if response.ok:
            break
        detail = response.text[:800]
        attempts.append(f"{candidate}: HTTP {response.status_code}: {detail}")
        lower_detail = detail.lower()
        retryable_404 = response.status_code == 404 and (
            "no longer available" in lower_detail
            or "not found" in lower_detail
            or "not_found" in lower_detail
        )
        if not retryable_404:
            raise RuntimeError(f"Google AI API l?i HTTP {response.status_code}: {detail}")
    if response is None or not response.ok:
        raise RuntimeError("Google AI API khong dung duoc cac model da thu:\n" + "\n".join(attempts))
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Google AI kh?ng tr? candidate n?o.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Google AI tr? n?i dung r?ng.")
    return text


def openrouter_generate(
    *,
    api_key: str,
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    files: list[dict] | None = None,
    timeout: int = 120,
) -> str:
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("Chưa nhập OpenRouter API key.")
    model_name = (model or DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL
    effective_prompt = prompt
    if files:
        names = ", ".join(str(item.get("filename") or "file") for item in files if item)
        effective_prompt += (
            "\n\nGhi chú: Provider OpenRouter/model hiện tại của tool chỉ gửi nội dung text. "
            f"Các file đính kèm đã chuẩn bị nhưng không gửi trực tiếp qua OpenRouter: {names}. "
            "Nếu đây là ảnh/PDF scan chưa có text OCR, hãy dùng Google AI/Gemini hoặc dán nội dung OCR vào nguồn text."
        )
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": effective_prompt}],
        "temperature": 0.2,
        "top_p": 0.9,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hncode.edu.vn",
        "X-OpenRouter-Title": "Tool HNCode",
    }
    response = None
    last_error = ""
    for attempt in range(2):
        try:
            response = requests.post(
                OPENROUTER_CHAT_COMPLETIONS_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt == 0:
                time.sleep(2)
                continue
            raise RuntimeError(f"OpenRouter không phản hồi sau khi thử lại: {last_error}") from exc
        if response.ok:
            break
        last_error = f"HTTP {response.status_code}: {response.text[:800]}"
        if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt > 0:
            raise RuntimeError(f"OpenRouter API lỗi {last_error}")
        time.sleep(2)
    if response is None or not response.ok:
        raise RuntimeError(f"OpenRouter API không dùng được sau khi thử lại: {last_error}")
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter không trả choice nào.")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content).strip()
    else:
        text = str(content).strip()
    if not text:
        raise RuntimeError("OpenRouter trả nội dung rỗng.")
    return text


def ai_generate(
    *,
    provider: str,
    api_key: str,
    prompt: str,
    model: str = "",
    files: list[dict] | None = None,
    timeout: int = 120,
) -> str:
    provider_key = (provider or "google").strip().lower()
    if provider_key in {"openrouter", "open-router"}:
        return openrouter_generate(
            api_key=api_key,
            model=model or DEFAULT_OPENROUTER_MODEL,
            prompt=prompt,
            files=files,
            timeout=timeout,
        )
    return gemini_generate(
        api_key=api_key,
        model=model or DEFAULT_GEMINI_MODEL,
        prompt=prompt,
        files=files,
        timeout=timeout,
    )


def parse_ai_json(text: str) -> dict:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I).strip()
    raw = re.sub(r"\s*```$", "", raw).strip()
    latex_commands = {
        "alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda", "mu", "pi", "sigma", "phi", "omega",
        "le", "leq", "ge", "geq", "neq", "ne", "times", "cdot", "div", "pm", "mp",
        "frac", "sqrt", "text", "mathrm", "mathbf", "mathit", "underline", "overline",
        "left", "right", "lfloor", "rfloor", "lceil", "rceil", "infty",
        "sum", "prod", "min", "max", "log", "ln", "mod", "bmod", "pmod",
        "in", "notin", "subset", "supset", "cup", "cap", "to", "rightarrow", "leftarrow",
        "ldots", "cdots", "dots", "nabla",
    }

    def repair_json_string_escapes(value: str) -> str:
        result: list[str] = []
        in_string = False
        escaped = False
        index = 0
        while index < len(value):
            char = value[index]
            if not in_string:
                result.append(char)
                if char == '"':
                    in_string = True
                index += 1
                continue
            if escaped:
                result.append(char)
                escaped = False
                index += 1
                continue
            if char == '"':
                result.append(char)
                in_string = False
                index += 1
                continue
            if char == "\\":
                command = re.match(r"\\([A-Za-z]+)", value[index:])
                if command and command.group(1) in latex_commands:
                    result.append("\\\\")
                    index += 1
                    continue
                next_char = value[index + 1] if index + 1 < len(value) else ""
                if next_char in {'"', "\\", "/", "b", "f", "n", "r", "t"}:
                    result.append(char)
                    escaped = True
                    index += 1
                    continue
                if next_char == "u" and re.fullmatch(r"[0-9a-fA-F]{4}", value[index + 2 : index + 6] or ""):
                    result.append(char)
                    escaped = True
                    index += 1
                    continue
                result.append("\\\\")
                index += 1
                continue
            result.append(char)
            index += 1
        return "".join(result)

    def loads_tolerant(value: str) -> dict:
        value = repair_json_string_escapes(value)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # Gemini sometimes returns LaTeX commands with a single backslash.
            # Those are invalid JSON escapes unless the backslash is doubled.
            repaired = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", value)
            return json.loads(repaired)

    try:
        data = loads_tolerant(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            raise RuntimeError("AI kh?ng tr? JSON h?p l?.")
        data = loads_tolerant(match.group(0))
    if not isinstance(data, dict):
        raise RuntimeError("JSON AI tr? v? ph?i l? object.")
    tags = data.get("tags")
    if isinstance(tags, str):
        data["tags"] = [item.strip() for item in re.split(r"[,;|]", tags) if item.strip()]
    if not isinstance(data.get("tags"), list):
        data["tags"] = []
    if not isinstance(data.get("issues"), list):
        data["issues"] = []
    if not isinstance(data.get("allowed_languages"), list):
        data["allowed_languages"] = []
    return data


def file_payload(filename: str, data: bytes) -> dict:
    mime_type = mimetypes.guess_type(filename or "")[0] or "application/octet-stream"
    return {"filename": filename, "mime_type": mime_type, "data": data}
