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
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import requests


TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


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
    text = str(markdown or "").strip()
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
    add("Phần thân đề", body_ok, "Có phần thân đề sau dòng metadata." if body_ok else "Nên có nội dung đề sau dòng đầu.")
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


def build_hncode_normalization_prompt(reference_text: str, snapshot: dict, options: dict) -> str:
    target = options.get("target") or "hncode"
    target_label = "HNCode" if target == "hncode" else "HNOJ"
    code = snapshot.get("code") or ""
    name = snapshot.get("name") or ""
    statement = snapshot.get("statement") or ""
    solution = snapshot.get("solution") or ""
    test_summary = snapshot.get("test_summary") or ""
    return f"""Bạn là trợ lý chuẩn hóa bài lập trình cho {target_label}.

Hãy xử lý bài `{code}` - `{name}` theo tài liệu chuẩn hóa bên dưới.

Phần cần làm:
{selected_parts_text(options)}

Yêu cầu trả về:
- Chỉ trả về JSON hợp lệ, không bọc ```json.
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
        raise RuntimeError("Chưa nhập Google AI API key.")
    model_name = (model or DEFAULT_GEMINI_MODEL).strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
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
    response = requests.post(url, params={"key": key}, json=payload, timeout=timeout)
    if not response.ok:
        detail = response.text[:800]
        raise RuntimeError(f"Google AI API lỗi HTTP {response.status_code}: {detail}")
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Google AI không trả candidate nào.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Google AI trả nội dung rỗng.")
    return text


def parse_ai_json(text: str) -> dict:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I).strip()
    raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            raise RuntimeError("AI không trả JSON hợp lệ.")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise RuntimeError("JSON AI trả về phải là object.")
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
