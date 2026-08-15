"""Shared problem transfer helpers.

This module keeps target-neutral transfer decisions outside Flask routes while
still accepting callbacks for site-specific form submission code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from transfer_tinhoctre_to_hncode import ProblemInfo
from upload_tinhoctre_batch import GeneratedTests, ProblemBundle
from services.problem_upload import infer_fileio_names


def selected_count(rows: list[dict]) -> int:
    return len([row for row in rows if row.get("selected")])


def make_prepare_transfer_row(
    *,
    original_code: str,
    info: ProblemInfo,
    zip_path: Path,
    cases: list,
    source_base_url: str,
    dest: str,
    settings: dict,
    normalize_problem_code_for_target: Callable[[str, str], str],
    test_data_url: Callable[[str, str], str],
) -> dict:
    source_code = info.code or original_code
    dest_code = normalize_problem_code_for_target(source_code, dest)
    return {
        "original_code": original_code,
        "code": dest_code,
        "name": info.name,
        "time_limit": info.time_limit or settings.get("time_limit") or "1.0",
        "memory_limit": info.memory_limit or settings.get("memory_limit") or "1048576",
        "source_time_limit": info.time_limit or "1.0",
        "source_memory_limit": info.memory_limit or "1048576",
        "test_file": zip_path.name,
        "test_link": test_data_url(source_base_url, original_code),
        "test_count": len(cases),
        "status": "Đã đọc",
    }


def make_failed_prepare_transfer_row(
    *,
    code: str,
    source_base_url: str,
    settings: dict,
    test_data_url: Callable[[str, str], str],
) -> dict:
    return {
        "original_code": code,
        "code": code,
        "name": "",
        "time_limit": settings.get("time_limit") or "1.0",
        "memory_limit": settings.get("memory_limit") or "1048576",
        "source_time_limit": "1.0",
        "source_memory_limit": "1048576",
        "test_file": "Lỗi khi đọc nguồn",
        "test_link": test_data_url(source_base_url, code),
        "test_count": 0,
        "status": "✗ Lỗi đọc nguồn",
    }


def apply_transfer_row_to_info(info: ProblemInfo, row: dict, settings: dict) -> ProblemInfo:
    if row.get("name"):
        info.name = row["name"]
    info.time_limit = row.get("time_limit") or settings.get("time_limit") or info.time_limit or "1.0"
    info.memory_limit = row.get("memory_limit") or settings.get("memory_limit") or info.memory_limit or "1048576"
    return info


def upload_transfer_to_dmoj(
    *,
    session,
    dest: str,
    dest_code: str,
    info: ProblemInfo,
    zip_path: Path,
    cases: list,
    row: dict,
    language_ids: list[str],
    log_lines: list[str],
    target_info: dict,
    problem_info_for_target: Callable[[ProblemInfo, str], ProblemInfo],
    destination_problem_exists: Callable,
    problem_url: Callable[[str, str], str],
    create_problem: Callable,
    upload_hncode_tests: Callable,
    upload_hnoj_tests: Callable,
    generated_tests_cls=GeneratedTests,
    problem_already_exists_cls=RuntimeError,
) -> None:
    base_url = target_info["base_url"]
    exists = destination_problem_exists(session, base_url, dest_code)
    if exists:
        raise problem_already_exists_cls(f"Mã bài {dest_code} đã tồn tại tại {problem_url(base_url, dest_code)}")
    if row.get("upload_statement") and not exists:
        dest_info = problem_info_for_target(info, dest)
        create_problem(
            session,
            base_url,
            dest_info,
            dest_code=dest_code,
            type_id=target_info["type_id"],
            group_id=target_info["group_id"],
            public=False,
            allow_all_languages=False,
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{dest_code}: đã tạo đề.")
    else:
        log_lines.append(f"{dest_code}: bỏ qua tạo đề.")
    if row.get("upload_tests"):
        if dest == "hnoj":
            tests = generated_tests_cls(zip_path, [case.input_file for case in cases], [case.output_file for case in cases])
            upload_hnoj_tests(session, base_url, dest_code, tests)
        else:
            fileio_input, fileio_output = infer_fileio_names(info.description)
            upload_hncode_tests(
                session,
                base_url,
                dest_code,
                zip_path,
                cases,
                fileio_input=fileio_input,
                fileio_output=fileio_output,
            )
        log_lines.append(f"{dest_code}: đã upload test.")
    else:
        log_lines.append(f"{dest_code}: không upload test.")


def upload_transfer_to_tinhoctre(
    *,
    session,
    dest: str,
    dest_code: str,
    info: ProblemInfo,
    zip_path: Path,
    cases: list,
    row: dict,
    out_dir: Path,
    language_ids: list[str],
    log_lines: list[str],
    target_info: dict,
    problem_info_for_target: Callable[[ProblemInfo, str], ProblemInfo],
    problem_exists: Callable,
    problem_url: Callable[[str, str], str],
    create_problem: Callable,
    upload_tests: Callable,
    generated_tests_cls=GeneratedTests,
    problem_bundle_cls=ProblemBundle,
    problem_already_exists_cls=RuntimeError,
) -> None:
    base_url = target_info["base_url"]
    statement = out_dir / f"{dest_code}.md"
    dest_info = problem_info_for_target(info, dest)
    statement.write_text(dest_info.description, encoding="utf-8")
    problem_bundle_cls(0, dest_code, info.name, statement, None, zip_path, None)
    tests = generated_tests_cls(zip_path, [case.input_file for case in cases], [case.output_file for case in cases])
    exists = problem_exists(session, base_url, dest_code)
    if exists:
        raise problem_already_exists_cls(f"Mã bài {dest_code} đã tồn tại tại {problem_url(base_url, dest_code)}")
    if row.get("upload_statement") and not exists:
        create_problem(
            session,
            base_url,
            dest_info,
            dest_code=dest_code,
            type_id=target_info["type_id"],
            group_id=target_info["group_id"],
            allowed_language_ids=language_ids,
        )
        log_lines.append(f"{dest_code}: đã tạo đề.")
    else:
        log_lines.append(f"{dest_code}: bỏ qua tạo đề.")
    if row.get("upload_tests"):
        upload_tests(session, base_url, dest_code, tests)
        log_lines.append(f"{dest_code}: đã upload test.")
    else:
        log_lines.append(f"{dest_code}: không upload test.")
