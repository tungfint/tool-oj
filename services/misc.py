"""Offline helpers for miscellaneous tools."""

from __future__ import annotations

import re
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


CODE_EXTENSIONS = {".py", ".cpp", ".cc", ".cxx", ".c", ".pas", ".java"}


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
    report_lines = ["student_id\tstatus\toutput_file\tsource_file", *[f"{row['student_id']}\t{row['status']}\t{row['output']}\t{row['source']}" for row in rows]]
    (output_dir / "report.txt").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    found = sum(1 for row in rows if row["status"] == "ok")
    return {"rows": rows, "total": len(rows), "found": found, "missing": len(rows) - found}


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
        size = "py-compact" if features["line_count"] <= 8 else "py-structured" if features["function_count"] >= 2 or features["import_count"] >= 3 else "py-simple"
        io = "fastio" if features["fast_io"] else "plainio"
    elif features["ext"] in {".cpp", ".cc", ".cxx", ".c"}:
        size = "cpp-template" if features["macro_count"] >= 4 or features["using_alias_count"] >= 3 else "cpp-short" if features["line_count"] <= 35 else "cpp-plain"
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
    ai_phrases = ["complexity", "approach", "edge case", "edge cases", "initialize", "iterate", "we need", "we can", "time complexity", "space complexity"]
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
    features["code_ai_score"] = min(score, 45)
    features["code_reasons"] = reasons
    features["style_bucket"] = compact_style_bucket(features)
    return features


def normalized_code_tokens(text: str, ext: str) -> list[str]:
    cleaned = strip_code_comments(text, ext).lower()
    cleaned = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " STR ", cleaned)
    raw_tokens = re.findall(r"[a-z_][a-z0-9_]*|\d+(?:\.\d+)?|==|!=|<=|>=|\+\+|--|&&|\|\||[+\-*/%<>=(){}\[\],.;:]", cleaned)
    keywords = {"if", "else", "for", "while", "return", "def", "class", "import", "from", "int", "long", "double", "float", "char", "bool", "void", "const", "auto", "cin", "cout"}
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
            text = read_zip_text(zf, name)
            if not text.strip():
                continue
            local_path = str(extract_code_member(zf, name, extract_root, contest)) if extract_root is not None else ""
            records.append(
                {
                    "contest": contest,
                    "student_id": parts[0],
                    "problem": code_problem_from_name(parts[-1]),
                    "path": name,
                    "filename": parts[-1],
                    "is_history": "$History" in parts,
                    "version": history_version_from_name(parts[-1]) if "$History" in parts else 10**18,
                    "ext": ext,
                    "text": text,
                    "local_path": local_path,
                    "features": analyze_code_text(text, ext),
                }
            )
    return records
