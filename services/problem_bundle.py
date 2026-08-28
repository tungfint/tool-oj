"""Problem bundle preparation helpers for upload workflows."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
import os
from pathlib import Path

from upload_tinhoctre_batch import (
    GeneratedTests,
    ProblemBundle,
    discover_bundles,
    extract_zip,
    find_named_file,
    generate_tests,
    read_text_smart,
    zip_case_files,
)


def statement_header_parts(statement_path: Path) -> list[str]:
    for line in read_text_smart(statement_path).splitlines():
        text = line.strip().strip("#* ")
        if not text:
            continue
        return [part.strip() for part in text.split("|")]
    return []


def metadata_from_statement(statement_path: Path, defaults: dict) -> dict:
    parts = statement_header_parts(statement_path)
    points = parts[2] if len(parts) > 2 and parts[2] else str(defaults.get("points") or "100")
    tags = parts[3] if len(parts) > 3 and parts[3] else str(defaults.get("tags") or "")
    return {
        "points": points,
        "tags": tags,
        "partial": bool(defaults.get("partial", True)),
    }


def split_combined_markdown_bundles(markdown_path: Path, source_dir: Path) -> list[ProblemBundle]:
    text = read_text_smart(markdown_path)
    matches = list(re.finditer(r"(?m)^#\s*(?:(?:Bài|BÃ i)\s+(\d+)\.\s*)?(.+?)\s*\|\s*([A-Za-z0-9_-]+)(?P<meta>\s*\|.*)?\s*$", text))
    if not matches:
        raise RuntimeError("Không tìm thấy bài nào. Mỗi bài cần bắt đầu dạng: # Bài 1. Tên bài | ma_bai | điểm | tags")
    bundles: list[ProblemBundle] = []
    seen: set[str] = set()
    for idx, match in enumerate(matches):
        number = int(match.group(1) or idx + 1)
        name = match.group(2).strip()
        code = match.group(3).strip()
        extra_meta = (match.group("meta") or "").strip()
        if code in seen:
            raise RuntimeError(f"Mã bài bị trùng trong file Markdown: {code}")
        seen.add(code)
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        statement_path = source_dir / f"{number}_{code}.md"
        statement_path.write_text(f"{name} | {code}{(' ' + extra_meta) if extra_meta else ''}\n\n{body}\n", encoding="utf-8")
        bundles.append(ProblemBundle(number, code, name, statement_path, None, None, None, None))
    return bundles


def prepare_multi_upload_source(source_path: Path, source_dir: Path, build_root: Path, defaults: dict) -> dict:
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
    solutions_md: dict[str, Path | None] = {}
    metadata: dict[str, dict] = {}
    is_markdown_source = source_path.suffix.lower() == ".md"
    for bundle in bundles:
        generated = tests.get(bundle.code)
        source = "Markdown tổng hợp"
        if bundle.generator or bundle.test_zip:
            generated = generate_tests(bundle, build_root)
            tests[bundle.code] = generated
            source = "gentest" if bundle.generator else "zip có sẵn"
        meta = metadata_from_statement(bundle.statement, defaults)
        metadata[bundle.code] = meta
        solution_md = find_named_file(source_dir, ["sol"], bundle.index, bundle.code, ".md") if not is_markdown_source else None
        solutions_md[bundle.code] = solution_md
        rows.append(
            {
                "original_code": bundle.code,
                "code": bundle.code,
                "name": bundle.name,
                "points": meta["points"],
                "tags": meta["tags"],
                "time_limit": defaults.get("time_limit") or "1.0",
                "memory_limit": defaults.get("memory_limit") or "1048576",
                "partial": meta["partial"],
                "statement_file": " + ".join(
                    name
                    for name in [bundle.statement.name, bundle.pdf_statement.name if bundle.pdf_statement else ""]
                    if name
                ),
                "upload_statement_default": bool(bundle.statement or bundle.pdf_statement),
                "test_file": generated.zip_path.name if generated else "Không có test",
                "test_count": len(generated.input_files) if generated else 0,
                "upload_tests_default": bool(generated),
                "upload_solution_default": bool(solution_md),
            }
        )
        test_text = f"{len(generated.input_files)} test" if generated else "không có test"
        solution_text = ", có lời giải Markdown" if solution_md else ""
        log_lines.append(f"- {bundle.code}: {bundle.name}, điểm {meta['points']}, tags {meta['tags'] or 'trống'}, {test_text}, nguồn {source}{solution_text}.")

    return {
        "bundles": bundles,
        "tests": tests,
        "solutions": solutions_md,
        "metadata": metadata,
        "rows": rows,
        "log_lines": log_lines,
        "source_name": source_name,
    }


def repair_python_main_guard(text: str) -> str:
    return text.replace("if **name** == \"**main**\":", "if __name__ == \"__main__\":")


def find_generated_zip_for_single(build_dir: Path, bundle: ProblemBundle) -> Path | None:
    from upload_tinhoctre_batch import find_generated_zip

    return find_generated_zip(build_dir, bundle)


def zip_generated_case_files(build_dir: Path, code: str) -> Path:
    candidates = sorted(path for path in build_dir.rglob("*.inp") if path.is_file() and "__pycache__" not in path.parts)
    if not candidates:
        raise RuntimeError("Generator đã chạy xong nhưng không tạo zip test hoặc file .inp/.out.")
    zip_path = build_dir / f"{code}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for inp in candidates:
            rel = inp.relative_to(build_dir).as_posix()
            out = inp.with_suffix(".out")
            if not out.exists():
                raise RuntimeError(f"Thiếu file output tương ứng: {out.name}")
            archive.write(inp, rel)
            archive.write(out, out.relative_to(build_dir).as_posix())
    return zip_path


def generate_tests_from_cpp_generator(generator_path: Path, build_root: Path, code: str) -> GeneratedTests:
    build_dir = build_root / code
    build_dir.mkdir(parents=True, exist_ok=True)
    local_source = build_dir / generator_path.name
    shutil.copy2(generator_path, local_source)
    exe_name = "generator.exe" if sys.platform == "win32" else "generator"
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    compile_result = subprocess.run(
        ["g++", "-O2", local_source.name, "-o", exe_name],
        cwd=build_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        timeout=120,
    )
    if compile_result.returncode != 0:
        raise RuntimeError(f"C++ generator compile failed for {code}\nSTDOUT:\n{compile_result.stdout}\nSTDERR:\n{compile_result.stderr}")
    run_cmd = [str(build_dir / exe_name)] if sys.platform == "win32" else [f"./{exe_name}"]
    run_result = subprocess.run(
        run_cmd,
        cwd=build_dir,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        timeout=120,
    )
    if run_result.returncode != 0:
        raise RuntimeError(f"C++ generator failed for {code}\nSTDOUT:\n{run_result.stdout}\nSTDERR:\n{run_result.stderr}")
    dummy_bundle = ProblemBundle(1, code, code, generator_path, None, None, None, None)
    zip_path = find_generated_zip_for_single(build_dir, dummy_bundle)
    if zip_path is None:
        zip_path = zip_generated_case_files(build_dir, code)
    input_files, output_files = zip_case_files(zip_path)
    if not input_files:
        raise RuntimeError(f"C++ generator không tạo file .inp nào cho {code}.")
    return GeneratedTests(zip_path, input_files, output_files)
