"""Quiz markdown parsing and validation helpers."""

from __future__ import annotations

import re
import unicodedata


QUESTION_TYPE_ALIASES = {
    "trắc nghiệm 1 đáp án": "MC",
    "trac nghiem 1 dap an": "MC",
    "trắc nghiệm một đáp án": "MC",
    "trac nghiem mot dap an": "MC",
    "single choice": "MC",
    "mc": "MC",
    "trắc nghiệm nhiều đáp án": "MA",
    "trac nghiem nhieu dap an": "MA",
    "multiple choice": "MA",
    "ma": "MA",
    "trả lời ngắn": "SA",
    "tra loi ngan": "SA",
    "short answer": "SA",
    "sa": "SA",
    "đúng / sai": "TF",
    "dung / sai": "TF",
    "đúng sai": "TF",
    "dung sai": "TF",
    "true false": "TF",
    "tf": "TF",
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
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


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
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
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


def prepare_quiz_items(text: str) -> tuple[list[dict], list[dict]]:
    rows = []
    valid_questions = []
    blocks = split_quiz_blocks(text)
    if not blocks:
        raise RuntimeError("Chưa có câu hỏi nào trong nội dung quiz.")
    for index, block in enumerate(blocks, 1):
        try:
            question = parse_quiz_markdown(block)[0]
            question["index"] = index
            valid_questions.append(question)
            rows.append({"index": index, "title": question["title"], "type": question["type"], "status": "✓ Hợp lệ", "error": "", "can_upload": True})
        except Exception as exc:
            rows.append({"index": index, "title": f"Câu {index}", "type": "", "status": "✗ Lỗi", "error": str(exc), "can_upload": False})
    return valid_questions, rows
