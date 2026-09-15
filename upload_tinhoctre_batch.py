#!/usr/bin/env python3
"""Create TinHocTre problems from a bundled zip, upload tests, and submit sols.

Input zip layout expected from the attached package:

    1_tht26_tongbi.md
    gentest_1_tht26_tongbi.py
    sol_1_tht26_tongbi.py

The generator scripts create a zip containing test files. This script posts the
generated zip and explicit case mapping to the TinHocTre/VNOJ-style forms.
If no generator exists, an existing test zip in the package is used instead.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from urllib.parse import urljoin

import requests


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)

DEFAULT_BASE_URL = "https://tinhoctre.vn"
DEFAULT_TYPE_ID = "1"  # Chua phan loai
DEFAULT_GROUP_ID = "1"  # Chua phan loai
DEFAULT_PYTHON3_LANGUAGE_ID = "17"  # PyPy 3 on tinhoctre.vn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class UploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProblemBundle:
    index: int
    code: str
    name: str
    statement: Path
    generator: Path | None
    test_zip: Path | None
    solution: Path | None
    solution_cpp: Path | None = None
    pdf_statement: Path | None = None
    python_solutions: tuple[Path, ...] = ()
    cpp_solutions: tuple[Path, ...] = ()
    test_directory: Path | None = None

    def all_python_solutions(self) -> tuple[Path, ...]:
        return unique_paths((*self.python_solutions, self.solution) if self.solution else self.python_solutions)

    def all_cpp_solutions(self) -> tuple[Path, ...]:
        return unique_paths((*self.cpp_solutions, self.solution_cpp) if self.solution_cpp else self.cpp_solutions)


@dataclass(frozen=True)
class GeneratedTests:
    zip_path: Path
    input_files: list[str]
    output_files: list[str]


def require(condition: object, message: str) -> None:
    if not condition:
        raise UploadError(message)


def csrf_token(page: str) -> str:
    patterns = [
        r"name=[\"']csrfmiddlewaretoken[\"'][^>]*value=[\"']([^\"']+)",
        r"value=[\"']([^\"']+)[\"'][^>]*name=[\"']csrfmiddlewaretoken[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, page)
        if match:
            return html.unescape(match.group(1))
    raise UploadError("Could not find csrfmiddlewaretoken")


def read_text_smart(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def input_value(page: str, name: str, default: str = "") -> str:
    pattern = r"<input\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>"
    match = re.search(pattern, page, re.S)
    if not match:
        return default
    value = re.search(r"value=[\"']([^\"']*)", match.group(0))
    return html.unescape(value.group(1)) if value else default


def form_errors(page: str) -> list[str]:
    errors: list[str] = []
    for match in re.finditer(r'<ul class="errorlist"[^>]*>(.*?)</ul>', page, re.S):
        text = html.unescape(re.sub(r"<.*?>", " ", match.group(1))).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            errors.append(text)
    return errors


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def login(base_url: str, username: str, password: str, next_path: str) -> requests.Session:
    s = session()
    login_url = urljoin(base_url, f"/accounts/login/?next={next_path}")
    page = s.get(login_url, timeout=30)
    require(page.ok, f"Login page failed: HTTP {page.status_code}")
    payload = {
        "username": username,
        "password": password,
        "csrfmiddlewaretoken": csrf_token(page.text),
        "next": next_path,
    }
    result = s.post(
        login_url,
        data=payload,
        headers={"Referer": login_url},
        allow_redirects=True,
        timeout=30,
    )
    require(result.ok, f"Login failed: HTTP {result.status_code}")
    require("sessionid" in s.cookies.get_dict(), "Login did not create a session")
    return s


def discover_bundles(source_dir: Path) -> list[ProblemBundle]:
    bundles: list[ProblemBundle] = []
    markdowns = sorted(
        (
            path
            for path in source_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".md", ".txt"}
            and path.stem.lower() not in {"readme", "summary"}
            and not path.stem.lower().startswith(("sol_", "solution_"))
        ),
        key=lambda path: path.relative_to(source_dir).as_posix().lower(),
    )
    pdfs = sorted(
        (
            path
            for path in source_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() == ".pdf"
            and not path.stem.lower().startswith(("sol_", "solution_"))
        ),
        key=lambda path: path.relative_to(source_dir).as_posix().lower(),
    )
    used_pdfs: set[Path] = set()
    statement_sources: list[tuple[Path | None, Path | None]] = [(path, None) for path in markdowns]
    statement_sources.extend((None, path) for path in pdfs)
    single_problem_package = len(statement_sources) == 1
    if len(markdowns) == 1 and len(pdfs) == 1:
        markdown_key = parse_statement_filename(markdowns[0])
        pdf_key = parse_statement_filename(pdfs[0])
        single_problem_package = bool(markdown_key and pdf_key and markdown_key[1].lower() == pdf_key[1].lower())

    for markdown, candidate_pdf in statement_sources:
        statement_source = markdown or candidate_pdf
        if statement_source is None:
            continue
        if candidate_pdf is not None and candidate_pdf.resolve() in used_pdfs:
            continue
        statement = markdown or statement_source
        parsed = parse_statement_filename(statement)
        if not parsed:
            continue
        index, fallback_code = parsed
        title_code = parse_statement_title_code(statement) if markdown else None
        code = title_code[1] if title_code else fallback_code
        search_dirs = [statement_source.parent]
        if statement_source.parent != source_dir:
            search_dirs.append(source_dir)
        pdf_statement = candidate_pdf
        if markdown:
            pdf_statement = find_statement_pdf(search_dirs, index, code, markdown)
        if pdf_statement:
            used_pdfs.add(pdf_statement.resolve())
        generator = find_named_file(search_dirs, ["gentest"], index, code, ".py")
        allow_generic_solutions = single_problem_package or statement_source.parent != source_dir
        python_solutions = find_solution_files(
            search_dirs, index, code, ".py", allow_generic=allow_generic_solutions
        )
        cpp_solutions = find_solution_files(
            search_dirs, index, code, ".cpp", allow_generic=allow_generic_solutions
        )
        solution = python_solutions[0] if python_solutions else None
        solution_cpp = cpp_solutions[0] if cpp_solutions else None
        test_zip = find_existing_test_zip(search_dirs, index, code)
        test_directory = find_existing_test_directory(
            search_dirs,
            code,
            allow_generic=single_problem_package or statement_source.parent != source_dir,
        )
        if generator is None and test_zip is None and test_directory is None and title_code is None and pdf_statement is None:
            continue
        require(
            generator is not None or test_zip is not None or test_directory is not None,
            f"Missing test source for {code}: expected gentest_{code}.py, a .zip test archive, or a directory of .inp/.out pairs",
        )
        if markdown is None:
            placeholder_dir = source_dir / ".tool_statements"
            placeholder_dir.mkdir(parents=True, exist_ok=True)
            statement = placeholder_dir / f"{index}_{code}.md" if index else placeholder_dir / f"{code}.md"
            if not statement.exists():
                statement.write_text(f"{problem_name_from_code(code)} | {code}\n", encoding="utf-8")
        name = title_code[0] if title_code else extract_problem_name(generator, statement, index, code)
        bundles.append(
            ProblemBundle(
                index,
                code,
                name,
                statement,
                generator,
                test_zip,
                solution,
                solution_cpp,
                pdf_statement,
                python_solutions,
                cpp_solutions,
                test_directory,
            )
        )
    if not bundles:
        sample_files = [
            path.relative_to(source_dir).as_posix()
            for path in sorted(source_dir.rglob("*"), key=lambda item: item.as_posix().lower())
            if path.is_file()
        ][:20]
        hint = (
            "Không tìm thấy file đề bài .md, .txt hoặc .pdf hợp lệ trong zip. "
            "Mỗi bài cần có <ma_bai>.md, <ma_bai>.txt, <ma_bai>.pdf hoặc một tổ hợp các file này; "
            "có thể thêm tiền tố <stt>_."
        )
        if sample_files:
            hint += " Một số file đã giải nén: " + ", ".join(sample_files)
        raise UploadError(hint)
    return bundles


def parse_statement_filename(statement: Path) -> tuple[int, str] | None:
    match = re.fullmatch(r"(\d+)_(.+)\.(?:md|txt|pdf)", statement.name, flags=re.I)
    if match:
        return int(match.group(1)), match.group(2)
    match = re.fullmatch(r"(.+)\.(?:md|txt|pdf)", statement.name, flags=re.I)
    if match:
        return 0, match.group(1)
    return None


def find_statement_pdf(search_dirs: list[Path], index: int, code: str, markdown: Path) -> Path | None:
    names = [f"{markdown.stem}.pdf", f"{code}.pdf"]
    if index:
        names.insert(1, f"{index}_{code}.pdf")
    lower_to_path: dict[str, Path] = {}
    for directory in search_dirs:
        iterator = directory.rglob("*") if directory == search_dirs[-1] else directory.glob("*")
        for path in iterator:
            if path.is_file() and path.suffix.lower() == ".pdf":
                lower_to_path.setdefault(path.name.lower(), path)
    for name in names:
        found = lower_to_path.get(name.lower())
        if found and not found.stem.lower().startswith(("sol_", "solution_")):
            return found
    return None


def parse_statement_title_code(statement: Path) -> tuple[str, str] | None:
    for line in read_text_smart(statement).splitlines():
        text = line.strip().strip("#* ")
        if not text:
            continue
        if "|" not in text:
            return None
        parts = [part.strip() for part in text.split("|")]
        title = parts[0] if parts else ""
        code = parts[1] if len(parts) > 1 else ""
        if title and code:
            return title[:100], code
        return None
    return None


def find_named_file(source_dir: Path | list[Path], prefixes: list[str], index: int, code: str, suffix: str) -> Path | None:
    names: list[str] = []
    for prefix in prefixes:
        if index:
            names.append(f"{prefix}_{index}_{code}{suffix}")
        names.append(f"{prefix}_{code}{suffix}")
    search_dirs = source_dir if isinstance(source_dir, list) else [source_dir]
    lower_to_path: dict[str, Path] = {}
    for directory in search_dirs:
        iterator = directory.rglob("*") if directory == search_dirs[-1] else directory.glob("*")
        for path in iterator:
            if path.is_file() and path.suffix.lower() == suffix.lower():
                lower_to_path.setdefault(path.name.lower(), path)
    for name in names:
        found = lower_to_path.get(name.lower())
        if found:
            return found
    return None


def unique_paths(paths: Iterable[Path | None]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        if path is None:
            continue
        key = str(path.resolve()).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return tuple(result)


def find_solution_files(
    source_dir: Path | list[Path],
    index: int,
    code: str,
    suffix: str,
    *,
    allow_generic: bool = False,
) -> tuple[Path, ...]:
    """Find every submission source belonging to one problem, in stable name order."""
    search_dirs = source_dir if isinstance(source_dir, list) else [source_dir]
    files: list[Path] = []
    for directory_index, directory in enumerate(search_dirs):
        iterator = directory.rglob("*") if directory_index == len(search_dirs) - 1 else directory.glob("*")
        for path in iterator:
            if not path.is_file() or path.suffix.lower() != suffix.lower():
                continue
            stem = path.stem.lower()
            if not stem.startswith(("sol_", "solution_")):
                continue
            if code.lower() in stem or allow_generic and path.parent == search_dirs[0]:
                files.append(path)

    def sort_key(path: Path) -> tuple[int, str]:
        stem = path.stem.lower()
        exact_names = {f"sol_{code.lower()}", f"solution_{code.lower()}"}
        return (0 if stem in exact_names else 1, path.name.lower())

    return unique_paths(sorted(files, key=sort_key))


def extract_problem_name(generator: Path | None, statement: Path, index: int, code: str) -> str:
    if generator is None:
        return extract_name_from_statement(statement) or problem_name_from_code(code)
    text = read_text_smart(generator)
    pattern = rf"Sinh test cho Bài\s+{index}\.\s*(.*?)\s*\|\s*{re.escape(code)}"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return extract_name_from_statement(statement) or problem_name_from_code(code)


def extract_name_from_statement(statement: Path) -> str:
    for line in read_text_smart(statement).splitlines():
        text = line.strip().strip("#* ")
        if text:
            return text[:100]
    return ""


def problem_name_from_code(code: str) -> str:
    short = re.sub(r"^tht\d+_", "", code)
    short = re.sub(r"^tht\d+[a-z]*_", "", short)
    return short.replace("_", " ").strip() or code


def find_existing_test_zip(source_dir: Path | list[Path], index: int, code: str) -> Path | None:
    short = re.sub(r"^tht\d+_", "", code)
    candidates = [
        f"{index}_{code}.zip",
        f"{code}.zip",
        f"{short}.zip",
        f"{code}_test.zip",
        f"{short}_test.zip",
        f"{code}_tests.zip",
        f"{short}_tests.zip",
    ]
    search_dirs = source_dir if isinstance(source_dir, list) else [source_dir]
    zip_paths: list[Path] = []
    for directory in search_dirs:
        iterator = directory.rglob("*") if directory == search_dirs[-1] else directory.glob("*")
        zip_paths.extend(path for path in iterator if path.is_file() and path.suffix.lower() == ".zip")
    lower_to_path = {path.name.lower(): path for path in zip_paths}
    for candidate in candidates:
        path = lower_to_path.get(candidate.lower())
        if path:
            return path
    matching = [path for path in zip_paths if short.lower() in path.stem.lower()]
    return sorted(matching, key=lambda path: (len(path.name), path.name.lower()))[0] if matching else None


def test_pairs_in_directory(directory: Path, *, recursive: bool = True) -> list[tuple[Path, Path]]:
    iterator = directory.rglob("*") if recursive else directory.glob("*")
    files = [path for path in iterator if path.is_file()]
    by_relative_name = {path.relative_to(directory).as_posix().lower(): path for path in files}
    pairs: list[tuple[Path, Path]] = []
    for input_path in sorted(
        (path for path in files if path.suffix.lower() == ".inp"),
        key=lambda path: path.relative_to(directory).as_posix().lower(),
    ):
        relative_input = input_path.relative_to(directory).as_posix()
        expected_output = re.sub(r"\.inp$", ".out", relative_input, flags=re.I).lower()
        output_path = by_relative_name.get(expected_output)
        if output_path is None:
            return []
        pairs.append((input_path, output_path))
    return pairs


def find_existing_test_directory(
    source_dir: Path | list[Path],
    code: str,
    *,
    allow_generic: bool = True,
) -> Path | None:
    search_dirs = source_dir if isinstance(source_dir, list) else [source_dir]
    candidates: list[Path] = []
    generic_names = {"test", "tests", "testdata", "test_data", "data"}
    for position, directory in enumerate(search_dirs):
        allowed_names = {code.lower()}
        if allow_generic and position == 0:
            allowed_names.update(generic_names)
        candidates.extend(
            path
            for path in directory.iterdir()
            if path.is_dir() and path.name.lower() in allowed_names
        )
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        if test_pairs_in_directory(candidate):
            return candidate
    if allow_generic and search_dirs and test_pairs_in_directory(search_dirs[0], recursive=False):
        return search_dirs[0]
    return None


def clean_statement(markdown: str) -> str:
    # Some generated files contain an actual tab before "imes" where LaTeX
    # intended "\times".
    return markdown.replace("\times", r"\times").strip()


def statement_body_text(markdown: str, *, skip_title_line: bool = True) -> str:
    text = markdown.replace("\times", r"\times")
    if skip_title_line:
        lines = text.splitlines()
        first_index = next((index for index, line in enumerate(lines) if line.strip()), None)
        if first_index is not None and "|" in lines[first_index]:
            del lines[first_index]
            text = "\n".join(lines)
    return text.strip()


def generate_tests(bundle: ProblemBundle, build_root: Path) -> GeneratedTests:
    build_dir = build_root / bundle.code
    build_dir.mkdir(parents=True, exist_ok=True)
    if bundle.test_zip is not None:
        zip_path = build_dir / bundle.test_zip.name
        shutil.copy2(bundle.test_zip, zip_path)
        input_files, output_files = zip_case_files(zip_path)
        require(input_files, f"No .inp files in existing zip for {bundle.code}")
        require(len(input_files) == len(output_files), f"Input/output count mismatch for {bundle.code}")
        return GeneratedTests(zip_path, input_files, output_files)
    if bundle.test_directory is not None:
        zip_path = zip_existing_test_directory(bundle.test_directory, build_dir, bundle.code)
        input_files, output_files = zip_case_files(zip_path)
        return GeneratedTests(zip_path, input_files, output_files)

    require(bundle.generator is not None, f"No generator, test zip, or test directory for {bundle.code}")

    copy_generator_support_files(bundle.generator, build_dir)
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    try:
        configured_timeout = int(os.getenv("TOOL_OJ_GENERATOR_TIMEOUT", "300"))
    except (TypeError, ValueError):
        configured_timeout = 300
    timeout_seconds = max(30, min(configured_timeout, 1800))
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", bundle.generator.name],
            cwd=build_dir,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise UploadError(
            f"Generator timed out for {bundle.code} after {timeout_seconds} seconds. "
            "Set TOOL_OJ_GENERATOR_TIMEOUT to increase the limit."
        ) from exc
    require(
        result.returncode == 0,
        f"Generator failed for {bundle.code}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
    )
    expected_zip = find_generated_zip(build_dir, bundle)
    if expected_zip is None:
        expected_zip = zip_generated_test_directory(build_dir, bundle.code)
    require(
        expected_zip is not None,
        f"Generator did not create a recognizable test zip or any .inp/.out pairs for {bundle.code}",
    )
    input_files, output_files = zip_case_files(expected_zip)
    require(input_files, f"No .inp files in generated zip for {bundle.code}")
    require(len(input_files) == len(output_files), f"Input/output count mismatch for {bundle.code}")
    return GeneratedTests(expected_zip, input_files, output_files)


def copy_generator_support_files(generator: Path, build_dir: Path) -> None:
    """Recreate the generator's local file context without copying old test archives."""
    excluded_directories = {"test", "tests", "__pycache__", ".git"}
    excluded_suffixes = {".zip", ".pdf", ".exe", ".inp", ".out"}
    resolved_build_dir = build_dir.resolve()
    for source_path in generator.parent.rglob("*"):
        resolved_source = source_path.resolve()
        if resolved_source == resolved_build_dir or resolved_build_dir in resolved_source.parents:
            continue
        relative_path = source_path.relative_to(generator.parent)
        if any(part.lower() in excluded_directories for part in relative_path.parts[:-1]):
            continue
        if not source_path.is_file() or source_path.suffix.lower() in excluded_suffixes:
            continue
        destination = build_dir / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)


def zip_existing_test_directory(test_directory: Path, build_dir: Path, code: str) -> Path:
    pairs = test_pairs_in_directory(test_directory)
    require(pairs, f"No complete .inp/.out pairs in test directory for {code}")
    zip_path = build_dir / f"{code}.zip"
    prefix = test_directory.name if test_directory.name.lower() in {"test", "tests", "testdata", "test_data"} else ""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for input_path, output_path in pairs:
            for path in (input_path, output_path):
                relative = path.relative_to(test_directory).as_posix()
                archive_name = f"{prefix}/{relative}" if prefix else relative
                archive.write(path, archive_name)
    return zip_path


def find_generated_zip(build_dir: Path, bundle: ProblemBundle) -> Path | None:
    candidates = []
    if bundle.index:
        candidates.append(build_dir / f"{bundle.index}_{bundle.code}.zip")
    candidates.append(build_dir / f"{bundle.code}.zip")
    short = re.sub(r"^tht\d+[a-z]*_", "", bundle.code)
    candidates.append(build_dir / f"{short}.zip")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    zips = sorted(build_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


def zip_generated_test_directory(build_dir: Path, code: str) -> Path | None:
    pairs = test_pairs_in_directory(build_dir)
    if not pairs:
        return None
    zip_path = build_dir / f"{code}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for input_path, output_path in pairs:
            archive.write(input_path, input_path.relative_to(build_dir).as_posix())
            archive.write(output_path, output_path.relative_to(build_dir).as_posix())
    return zip_path


def zip_case_files(zip_path: Path) -> tuple[list[str], list[str]]:
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/"))
    input_files = [name for name in names if name.lower().endswith(".inp")]
    lower_to_real_name = {name.lower(): name for name in names}
    output_files = []
    missing = []
    for input_name in input_files:
        expected_output = re.sub(r"\.inp$", ".out", input_name, flags=re.I)
        real_output = lower_to_real_name.get(expected_output.lower())
        if real_output:
            output_files.append(real_output)
        else:
            missing.append(expected_output)
    require(not missing, f"Generated zip is missing output files: {missing}")
    return input_files, output_files


def problem_exists(s: requests.Session, base_url: str, code: str) -> bool:
    page = s.get(urljoin(base_url, f"/problem/{code}"), timeout=30)
    return page.status_code == 200 and code in page.text


def create_problem(
    s: requests.Session,
    base_url: str,
    bundle: ProblemBundle,
    *,
    type_id: str,
    group_id: str,
    time_limit: str,
    memory_limit: str,
    points: str,
) -> None:
    create_url = urljoin(base_url, "/problems/create")
    page = s.get(create_url, timeout=30)
    require(page.ok, f"Create page failed: HTTP {page.status_code}")
    statement = statement_body_text(read_text_smart(bundle.statement), skip_title_line=True).replace("$", "~")
    data: list[tuple[str, str]] = [
        ("csrfmiddlewaretoken", csrf_token(page.text)),
        ("code", bundle.code),
        ("name", bundle.name),
        ("description", statement),
        ("time_limit", time_limit),
        ("memory_limit", memory_limit),
        ("points", points),
        ("partial", "on"),
        ("types", type_id),
        ("group", group_id),
        ("testcase_visibility_mode", "O"),
        ("_continue", "Save and continue editing"),
    ]
    result = s.post(
        create_url,
        data=data,
        headers={"Referer": create_url},
        allow_redirects=True,
        timeout=30,
    )
    require(result.ok, f"Create problem failed for {bundle.code}: HTTP {result.status_code}")
    errors = form_errors(result.text)
    require(not errors, f"Create form errors for {bundle.code}:\n" + "\n".join(errors))
    require(
        f"/problem/{bundle.code}" in result.url or bundle.code in result.text,
        f"Create did not appear to save {bundle.code}; final URL: {result.url}",
    )


def upload_tests(s: requests.Session, base_url: str, code: str, tests: GeneratedTests) -> None:
    test_url = urljoin(base_url, f"/problem/{code}/test_data")
    page = s.get(test_url, timeout=30)
    require(page.ok, f"Test data page failed for {code}: HTTP {page.status_code}")
    initial_forms = int(input_value(page.text, "cases-INITIAL_FORMS", "0") or "0")
    total_forms = initial_forms + len(tests.input_files)
    data: list[tuple[str, str]] = [
        ("csrfmiddlewaretoken", csrf_token(page.text)),
        ("cases-TOTAL_FORMS", str(total_forms)),
        ("cases-INITIAL_FORMS", str(initial_forms)),
        ("cases-MIN_NUM_FORMS", "0"),
        ("cases-MAX_NUM_FORMS", "1"),
        ("problem-data-grader", "standard"),
        ("problem-data-io_method", "standard"),
        ("problem-data-io_input_file", ""),
        ("problem-data-io_output_file", ""),
        ("problem-data-grader_args", "{}"),
        ("problem-data-checker", "standard"),
        ("problem-data-checker_type", "testlib"),
        ("problem-data-output_limit", ""),
        ("problem-data-checker_args", ""),
        ("signature-graders-TOTAL_FORMS", "3"),
        ("signature-graders-INITIAL_FORMS", "0"),
        ("signature-graders-MIN_NUM_FORMS", "0"),
        ("signature-graders-MAX_NUM_FORMS", "3"),
    ]
    for idx in range(3):
        data.extend([(f"signature-graders-{idx}-id", ""), (f"signature-graders-{idx}-language", "")])

    for idx in range(initial_forms):
        data.extend(
            [
                (f"cases-{idx}-id", input_value(page.text, f"cases-{idx}-id")),
                (f"cases-{idx}-order", input_value(page.text, f"cases-{idx}-order", str(idx + 1))),
                (f"cases-{idx}-type", "C"),
                (f"cases-{idx}-input_file", input_value(page.text, f"cases-{idx}-input_file")),
                (f"cases-{idx}-output_file", input_value(page.text, f"cases-{idx}-output_file")),
                (f"cases-{idx}-points", input_value(page.text, f"cases-{idx}-points", "1")),
                (f"cases-{idx}-DELETE", "on"),
            ]
        )

    offset = initial_forms
    for idx, (inp, out) in enumerate(zip(tests.input_files, tests.output_files), offset):
        data.extend(
            [
                (f"cases-{idx}-id", ""),
                (f"cases-{idx}-order", str(idx - offset + 1)),
                (f"cases-{idx}-type", "C"),
                (f"cases-{idx}-input_file", inp),
                (f"cases-{idx}-output_file", out),
                (f"cases-{idx}-points", "1"),
            ]
        )
    with tests.zip_path.open("rb") as fh:
        result = s.post(
            test_url,
            data=data,
            files={"problem-data-zipfile": (tests.zip_path.name, fh, "application/zip")},
            headers={"Referer": test_url},
            allow_redirects=True,
            timeout=60,
        )
    require(result.ok, f"Upload tests failed for {code}: HTTP {result.status_code}")
    errors = form_errors(result.text)
    require(not errors, f"Test data form errors for {code}:\n" + "\n".join(errors))
    after = s.get(test_url, timeout=30)
    require(after.ok, f"Test data page reload failed for {code}: HTTP {after.status_code}")
    require(re.search(r'href=[\"\'][^\"\']+\.zip[\"\']', after.text), f"Uploaded zip link is missing for {code}")
    verify = s.get(urljoin(base_url, f"/problem/{code}/test_data/init"), timeout=30)
    require(verify.ok, f"Test YAML verification failed for {code}: HTTP {verify.status_code}")
    for inp, out in zip(tests.input_files, tests.output_files):
        require(inp in verify.text, f"YAML for {code} is missing {inp}")
        require(out in verify.text, f"YAML for {code} is missing {out}")


def submit_solution(
    s: requests.Session,
    base_url: str,
    bundle: ProblemBundle,
    *,
    language_id: str,
    poll_seconds: int,
) -> str:
    submit_url = urljoin(base_url, f"/problem/{bundle.code}/submit")
    page = s.get(submit_url, timeout=30)
    require(page.ok, f"Submit page failed for {bundle.code}: HTTP {page.status_code}")
    require(bundle.solution is not None, f"No sample solution file for {bundle.code}")
    source = bundle.solution.read_text(encoding="utf-8")
    result = s.post(
        submit_url,
        data={
            "csrfmiddlewaretoken": csrf_token(page.text),
            "source": source,
            "language": language_id,
            "judge": "",
        },
        headers={"Referer": submit_url},
        allow_redirects=True,
        timeout=30,
    )
    require(result.ok, f"Submit failed for {bundle.code}: HTTP {result.status_code}")
    submission_url = result.url
    if poll_seconds > 0:
        wait_for_submission(s, submission_url, poll_seconds)
    return submission_url


def wait_for_submission(s: requests.Session, submission_url: str, poll_seconds: int) -> None:
    deadline = time.time() + poll_seconds
    pending_words = ("Queued", "Compiling", "Running", "Đang chờ", "Đang chấm", "Biên dịch")
    while time.time() < deadline:
        page = s.get(submission_url, timeout=30)
        if page.ok and not any(word in page.text for word in pending_words):
            return
        time.sleep(3)


def extract_zip(zip_path: Path, source_dir: Path) -> None:
    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(source_dir)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload new TinHocTre problems from a zip package")
    parser.add_argument("zip_path", type=Path, help="Input package zip")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=os.getenv("TINHOCTRE_USER", "admin"))
    parser.add_argument("--password", default=os.getenv("TINHOCTRE_PASS"))
    parser.add_argument("--type-id", default=DEFAULT_TYPE_ID, help="Default 1: Chua phan loai")
    parser.add_argument("--group-id", default=DEFAULT_GROUP_ID, help="Default 1: Chua phan loai")
    parser.add_argument("--time-limit", default="1.0")
    parser.add_argument("--memory-limit", default="1048576")
    parser.add_argument("--points", default="100")
    parser.add_argument("--language-id", default=DEFAULT_PYTHON3_LANGUAGE_ID, help="Default 17: PyPy 3")
    parser.add_argument("--out-dir", type=Path, default=Path("tinhoctre_upload_artifacts"))
    parser.add_argument("--if-exists", choices=["fail", "skip-create", "upload-tests"], default="fail")
    parser.add_argument("--only", nargs="*", help="Optional problem codes to process")
    parser.add_argument("--skip-create", action="store_true", help="Do not create/update problem statement")
    parser.add_argument("--skip-upload-tests", action="store_true", help="Do not upload/apply test data")
    parser.add_argument("--no-submit", action="store_true", help="Do not submit sample solution after upload")
    parser.add_argument("--submit-delay", type=int, default=5, help="Seconds to wait after test upload before submit")
    parser.add_argument("--poll-seconds", type=int, default=60, help="Poll each submission for this many seconds")
    parser.add_argument("--dry-run", action="store_true", help="Generate tests and print actions without posting")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    require(args.zip_path.exists(), f"Zip not found: {args.zip_path}")
    require(args.password or args.dry_run, "Missing password. Set TINHOCTRE_PASS or pass --password.")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_dir = args.out_dir / "source"
    build_root = args.out_dir / "generated"
    extract_zip(args.zip_path, source_dir)
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

    bundles = discover_bundles(source_dir)
    if args.only:
        wanted = set(args.only)
        bundles = [bundle for bundle in bundles if bundle.code in wanted]
        require(bundles, "No requested problem codes found")

    print(f"Found {len(bundles)} problem(s): " + ", ".join(bundle.code for bundle in bundles))
    generated = {bundle.code: generate_tests(bundle, build_root) for bundle in bundles}
    for bundle in bundles:
        tests = generated[bundle.code]
        source = "generator" if bundle.generator else f"existing zip {bundle.test_zip.name if bundle.test_zip else ''}"
        print(f"Prepared {bundle.code}: {bundle.name}, {len(tests.input_files)} tests from {source}, {tests.zip_path}")

    if args.dry_run:
        print("Dry run completed; no HTTP changes were made.")
        return 0

    s = login(args.base_url, args.username, args.password, "/problems/create")
    for bundle in bundles:
        exists = problem_exists(s, args.base_url, bundle.code)
        if args.skip_create:
            print(f"Skipping create by request: {bundle.code}")
        elif exists and args.if_exists == "fail":
            raise UploadError(f"Problem already exists: {bundle.code}")
        elif not exists:
            print(f"Creating {bundle.code}")
            create_problem(
                s,
                args.base_url,
                bundle,
                type_id=args.type_id,
                group_id=args.group_id,
                time_limit=args.time_limit,
                memory_limit=args.memory_limit,
                points=args.points,
            )
        else:
            print(f"Problem exists; skipping create: {bundle.code}")
        if not args.skip_upload_tests:
            print(f"Uploading tests for {bundle.code}")
            upload_tests(s, args.base_url, bundle.code, generated[bundle.code])
        if not args.no_submit:
            if bundle.solution is None:
                print(f"No sample solution for {bundle.code}; skipping submit")
                continue
            if not args.skip_upload_tests and args.submit_delay > 0:
                time.sleep(args.submit_delay)
            print(f"Submitting solution for {bundle.code}")
            submission_url = submit_solution(
                s,
                args.base_url,
                bundle,
                language_id=args.language_id,
                poll_seconds=args.poll_seconds,
            )
            print(f"Submitted {bundle.code}: {submission_url}")
    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except UploadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
