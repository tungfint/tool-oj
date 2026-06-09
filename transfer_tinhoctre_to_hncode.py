#!/usr/bin/env python3
"""Transfer a problem and its tests from tinhoctre.vn to HNCode.

The script is intentionally narrow: it targets the two Django/VNOJ-style sites
used in this workspace and the admin/test-data forms observed on 2026-06-03.
Credentials can be passed as arguments or environment variables.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)

DEFAULT_TINHOCTRE_USER = "admin"
DEFAULT_HNCODE_USER = "hncode"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class TransferError(RuntimeError):
    pass


@dataclass
class ProblemInfo:
    code: str
    name: str
    description: str
    points: str
    partial: bool
    time_limit: str
    memory_limit: str
    memory_unit: str


@dataclass
class TestCase:
    order: int
    kind: str
    input_file: str
    output_file: str
    points: str
    is_pretest: bool = False


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def require(condition: object, message: str) -> None:
    if not condition:
        raise TransferError(message)


def csrf_token(page: str) -> str:
    patterns = [
        r"name=[\"']csrfmiddlewaretoken[\"'][^>]*value=[\"']([^\"']+)",
        r"value=[\"']([^\"']+)[\"'][^>]*name=[\"']csrfmiddlewaretoken[\"']",
    ]
    for pattern in patterns:
        m = re.search(pattern, page)
        if m:
            return html.unescape(m.group(1))
    raise TransferError("Could not find csrfmiddlewaretoken")


def input_value(page: str, name: str, default: str = "") -> str:
    pattern = r"<input\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>"
    m = re.search(pattern, page, re.S)
    if not m:
        return default
    v = re.search(r"value=[\"']([^\"']*)", m.group(0))
    return html.unescape(v.group(1)) if v else default


def textarea_value(page: str, name: str, default: str = "") -> str:
    pattern = (
        r"<textarea\b[^>]*name=[\"']"
        + re.escape(name)
        + r"[\"'][^>]*>(.*?)</textarea>"
    )
    m = re.search(pattern, page, re.S)
    return html.unescape(m.group(1)).strip() if m else default


def checkbox_checked(page: str, name: str) -> bool:
    pattern = r"<input\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>"
    m = re.search(pattern, page, re.S)
    return bool(m and re.search(r"\bchecked\b", m.group(0)))


def selected_option(page: str, name: str, default: str = "") -> str:
    pattern = (
        r"<select\b[^>]*name=[\"']"
        + re.escape(name)
        + r"[\"'][^>]*>(.*?)</select>"
    )
    m = re.search(pattern, page, re.S)
    if not m:
        return default
    for option in re.finditer(r"<option\b([^>]*)>(.*?)</option>", m.group(1), re.S):
        attrs = option.group(1)
        if "selected" in attrs:
            v = re.search(r"value=[\"']([^\"']*)", attrs)
            return html.unescape(v.group(1)) if v else default
    return default


def all_input_values(page: str, name: str) -> list[str]:
    pattern = r"<input\b[^>]*name=[\"']" + re.escape(name) + r"[\"'][^>]*>"
    values: list[str] = []
    for m in re.finditer(pattern, page, re.S):
        v = re.search(r"value=[\"']([^\"']*)", m.group(0))
        if v:
            values.append(html.unescape(v.group(1)))
    return values


def login_tinhoctre(base_url: str, username: str, password: str, problem_code: str) -> requests.Session:
    s = session()
    login_url = urljoin(base_url, f"/accounts/login/?next=/problem/{problem_code}")
    page = s.get(login_url)
    require(page.ok, f"TinHocTre login page failed: HTTP {page.status_code}")
    payload = {
        "username": username,
        "password": password,
        "csrfmiddlewaretoken": csrf_token(page.text),
        "next": f"/problem/{problem_code}",
    }
    result = s.post(login_url, data=payload, headers={"Referer": login_url}, allow_redirects=True)
    require(result.ok, f"TinHocTre login failed: HTTP {result.status_code}")
    require("sessionid" in s.cookies.get_dict(), "TinHocTre login did not create a session")
    return s


def login_hncode(base_url: str, username: str, password: str) -> requests.Session:
    s = session()
    add_url = urljoin(base_url, "/admin/judge/problem/add/")
    page = s.get(add_url)
    require(page.ok, f"HNCode login page failed: HTTP {page.status_code}")
    payload = {
        "username": username,
        "password": password,
        "csrfmiddlewaretoken": csrf_token(page.text),
        "next": "/admin/judge/problem/add/",
    }
    login_url = urljoin(base_url, "/admin/login/?next=/admin/judge/problem/add/")
    result = s.post(login_url, data=payload, headers={"Referer": add_url}, allow_redirects=True)
    require(result.ok, f"HNCode login failed: HTTP {result.status_code}")
    require("sessionid" in s.cookies.get_dict(), "HNCode login did not create a session")
    return s


def fetch_source_problem(
    source: requests.Session, base_url: str, problem_code: str, out_dir: Path
) -> tuple[ProblemInfo, Path, list[TestCase], str]:
    edit_url = urljoin(base_url, f"/problem/{problem_code}/edit")
    edit = source.get(edit_url)
    require(edit.ok, f"Source edit page failed: HTTP {edit.status_code}")
    require(f'name="code"' in edit.text or "name='code'" in edit.text, "Source edit page is not editable")

    info = ProblemInfo(
        code=input_value(edit.text, "code", problem_code),
        name=input_value(edit.text, "name"),
        description=textarea_value(edit.text, "description").replace("~", "$"),
        points=input_value(edit.text, "points", "100"),
        partial=checkbox_checked(edit.text, "partial"),
        time_limit=input_value(edit.text, "time_limit", "1"),
        memory_limit=input_value(edit.text, "memory_limit", "1048576"),
        memory_unit=selected_option(edit.text, "memory_unit", "KB") or "KB",
    )
    require(info.name, "Could not read source problem name")
    require(info.description, "Could not read source problem statement")

    test_url = urljoin(base_url, f"/problem/{problem_code}/test_data")
    test_page = source.get(test_url)
    require(test_page.ok, f"Source test_data page failed: HTTP {test_page.status_code}")

    zip_match = re.search(r'href=[\"\']([^\"\']+\.zip)[\"\']', test_page.text)
    require(zip_match, "Could not find a source .zip test archive")
    zip_url = urljoin(base_url, html.unescape(zip_match.group(1)))
    zip_path = out_dir / f"{problem_code}_{Path(zip_url).name}"
    archive = source.get(zip_url)
    require(archive.ok and archive.content, f"Source test archive download failed: HTTP {archive.status_code}")
    zip_path.write_bytes(archive.content)

    cases = parse_source_cases(test_page.text)
    if not cases:
        cases = infer_cases_from_zip_paths(test_page.text)
    require(cases, "Could not read source test cases")
    return info, zip_path, cases, zip_url


def parse_source_cases(page: str) -> list[TestCase]:
    ids = sorted({int(x) for x in re.findall(r'name=[\"\']cases-(\d+)-input_file[\"\']', page)})
    cases: list[TestCase] = []
    for idx in ids:
        cases.append(
            TestCase(
                order=int(input_value(page, f"cases-{idx}-order", str(idx + 1))),
                kind=selected_option(page, f"cases-{idx}-type", "C") or "C",
                input_file=input_value(page, f"cases-{idx}-input_file"),
                output_file=input_value(page, f"cases-{idx}-output_file"),
                points=input_value(page, f"cases-{idx}-points", "1"),
                is_pretest=checkbox_checked(page, f"cases-{idx}-is_pretest"),
            )
        )
    return [case for case in cases if case.input_file and case.output_file]


def infer_cases_from_zip_paths(page: str) -> list[TestCase]:
    inputs = sorted(set(re.findall(r"[\w./-]+\.inp\b", page)))
    cases: list[TestCase] = []
    for order, inp in enumerate(inputs, 1):
        out = re.sub(r"\.inp$", ".out", inp)
        cases.append(TestCase(order=order, kind="C", input_file=inp, output_file=out, points="1"))
    return cases


def destination_problem_exists(dest: requests.Session, base_url: str, code: str) -> bool:
    page = dest.get(urljoin(base_url, f"/problem/{code}"))
    return page.status_code == 200 and code in page.text


def create_hncode_problem(
    dest: requests.Session,
    base_url: str,
    info: ProblemInfo,
    *,
    dest_code: str,
    type_id: str,
    group_id: str,
    public: bool,
    allow_all_languages: bool,
    allowed_language_ids: Iterable[str] | None = None,
) -> str:
    add_url = urljoin(base_url, "/admin/judge/problem/add/")
    page = dest.get(add_url)
    require(page.ok, f"HNCode add page failed: HTTP {page.status_code}")

    langs = all_input_values(page.text, "allowed_languages")
    data: list[tuple[str, str]] = [
        ("csrfmiddlewaretoken", csrf_token(page.text)),
        ("code", dest_code),
        ("name", info.name),
        ("admin_description", ""),
        ("description", info.description),
        ("license", ""),
        ("og_image", ""),
        ("summary", ""),
        ("types", type_id),
        ("group", group_id),
        ("points", info.points),
        ("time_limit", info.time_limit),
        ("memory_limit", info.memory_limit),
        ("memory_unit", info.memory_unit),
        ("change_message", ""),
        ("language_limits-TOTAL_FORMS", "0"),
        ("language_limits-INITIAL_FORMS", "0"),
        ("language_limits-MIN_NUM_FORMS", "0"),
        ("language_limits-MAX_NUM_FORMS", "1000"),
        ("language_templates-TOTAL_FORMS", "0"),
        ("language_templates-INITIAL_FORMS", "0"),
        ("language_templates-MIN_NUM_FORMS", "0"),
        ("language_templates-MAX_NUM_FORMS", "1000"),
        ("solution-TOTAL_FORMS", "0"),
        ("solution-INITIAL_FORMS", "0"),
        ("solution-MIN_NUM_FORMS", "0"),
        ("solution-MAX_NUM_FORMS", "1"),
        ("translations-TOTAL_FORMS", "0"),
        ("translations-INITIAL_FORMS", "0"),
        ("translations-MIN_NUM_FORMS", "0"),
        ("translations-MAX_NUM_FORMS", "1"),
        ("_continue", "Save and continue editing"),
    ]
    if public:
        data.append(("is_public", "on"))
    if info.partial:
        data.append(("partial", "on"))
    language_ids = list(allowed_language_ids or [])
    if language_ids:
        data.extend(("allowed_languages", value) for value in language_ids if value in langs)
    elif allow_all_languages:
        data.append(("allowed_languages_all", "on"))
        data.extend(("allowed_languages", value) for value in langs)

    result = dest.post(add_url, data=data, headers={"Referer": add_url}, allow_redirects=True)
    require(result.ok, f"HNCode create problem failed: HTTP {result.status_code}")
    errors = form_errors(result.text)
    require(not errors, "HNCode create problem form errors:\n" + "\n".join(errors))
    require("/change/" in result.url, f"HNCode did not redirect to a problem change page: {result.url}")
    return result.url


def form_errors(page: str) -> list[str]:
    errors: list[str] = []
    for m in re.finditer(r'<ul class="errorlist"[^>]*>(.*?)</ul>', page, re.S):
        text = html.unescape(re.sub(r"<.*?>", " ", m.group(1))).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            errors.append(text)
    return errors


def upload_hncode_tests(
    dest: requests.Session,
    base_url: str,
    problem_code: str,
    zip_path: Path,
    cases: Iterable[TestCase],
) -> str:
    test_url = urljoin(base_url, f"/problem/{problem_code}/test_data")
    page = dest.get(test_url)
    require(page.ok, f"HNCode test_data page failed: HTTP {page.status_code}")
    token = csrf_token(page.text)

    endpoint = urljoin(base_url, f"/problem/{problem_code}/test_data/upload")
    with zip_path.open("rb") as fh:
        upload = dest.post(
            endpoint,
            data={
                "csrfmiddlewaretoken": token,
                "qquuid": str(uuid.uuid4()),
                "qqfilename": zip_path.name,
                "qqtotalfilesize": str(zip_path.stat().st_size),
                "qqtotalparts": "1",
                "qqpartindex": "0",
            },
            files={"qqfile": (zip_path.name, fh, "application/zip")},
            headers={"Referer": test_url},
        )
    require(upload.ok, f"HNCode test zip upload failed: HTTP {upload.status_code}")
    try:
        upload_json = upload.json()
    except json.JSONDecodeError as exc:
        raise TransferError(f"HNCode upload response is not JSON: {upload.text[:200]}") from exc
    require(upload_json.get("success"), f"HNCode upload failed: {upload_json}")

    page = dest.get(test_url)
    token = csrf_token(page.text)
    cases = list(cases)
    data: list[tuple[str, str]] = [
        ("csrfmiddlewaretoken", token),
        ("cases-TOTAL_FORMS", str(len(cases))),
        ("cases-INITIAL_FORMS", "0"),
        ("cases-MIN_NUM_FORMS", "0"),
        ("cases-MAX_NUM_FORMS", "1"),
        ("problem-data-checker", "standard"),
        ("problem-data-fileio_input", ""),
        ("problem-data-fileio_output", ""),
        ("problem-data-checker_args", ""),
        ("signature-graders-TOTAL_FORMS", "3"),
        ("signature-graders-INITIAL_FORMS", "0"),
        ("signature-graders-MIN_NUM_FORMS", "0"),
        ("signature-graders-MAX_NUM_FORMS", "3"),
    ]
    for idx in range(3):
        data.extend(
            [
                (f"signature-graders-{idx}-id", ""),
                (f"signature-graders-{idx}-language", ""),
            ]
        )
    for idx, case in enumerate(cases):
        data.extend(
            [
                (f"cases-{idx}-id", ""),
                (f"cases-{idx}-order", str(case.order)),
                (f"cases-{idx}-type", case.kind),
                (f"cases-{idx}-input_file", case.input_file),
                (f"cases-{idx}-output_file", case.output_file),
                (f"cases-{idx}-points", case.points),
            ]
        )
        if case.is_pretest:
            data.append((f"cases-{idx}-is_pretest", "on"))

    result = dest.post(test_url, data=data, headers={"Referer": test_url}, allow_redirects=True)
    require(result.ok, f"HNCode test_data apply failed: HTTP {result.status_code}")

    yaml_url = urljoin(base_url, f"/problem/{problem_code}/test_data/init")
    yaml_page = dest.get(yaml_url)
    require(yaml_page.ok, f"HNCode YAML verification failed: HTTP {yaml_page.status_code}")
    for case in cases:
        require(case.input_file in yaml_page.text, f"YAML missing input file {case.input_file}")
        require(case.output_file in yaml_page.text, f"YAML missing output file {case.output_file}")
    return yaml_url


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transfer a problem and tests from tinhoctre.vn to oj.hncode.edu.vn"
    )
    parser.add_argument("problem_code", help="Source problem code, e.g. tht26_chiakeo")
    parser.add_argument("--dest-code", help="Destination problem code. Defaults to source code.")
    parser.add_argument("--source-base", default="https://tinhoctre.vn")
    parser.add_argument("--dest-base", default="https://oj.hncode.edu.vn")
    parser.add_argument("--source-user", default=os.getenv("TINHOCTRE_USER", DEFAULT_TINHOCTRE_USER))
    parser.add_argument("--source-pass", default=os.getenv("TINHOCTRE_PASS"))
    parser.add_argument("--dest-user", default=os.getenv("HNCODE_USER", DEFAULT_HNCODE_USER))
    parser.add_argument("--dest-pass", default=os.getenv("HNCODE_PASS"))
    parser.add_argument("--dest-type-id", default="387", help="HNCode problem type id. Default: 387 (Chưa phân loại)")
    parser.add_argument("--dest-group-id", default="105", help="HNCode problem group id. Default: 105 (Chưa phân loại)")
    parser.add_argument(
        "--allowed-language-ids",
        default="12,14,10,8,16",
        help="Comma-separated HNCode language ids. Default: C++17,C++20,Pascal,Python3,Pypy3",
    )
    parser.add_argument("--skip-create", action="store_true", help="Do not create/update destination statement")
    parser.add_argument("--skip-upload-tests", action="store_true", help="Do not upload/apply destination test data")
    parser.add_argument("--public", action="store_true", help="Make destination problem public")
    parser.add_argument(
        "--no-all-languages",
        action="store_true",
        help="Do not enable all HNCode languages on the destination problem",
    )
    parser.add_argument(
        "--if-exists",
        choices=["fail", "skip-create"],
        default="fail",
        help="What to do if destination problem already exists",
    )
    parser.add_argument("--out-dir", default="transfer_artifacts", help="Directory for downloaded artifacts")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    missing = [
        name
        for name, value in [
            ("TINHOCTRE_USER/--source-user", args.source_user),
            ("TINHOCTRE_PASS/--source-pass", args.source_pass),
            ("HNCODE_USER/--dest-user", args.dest_user),
            ("HNCODE_PASS/--dest-pass", args.dest_pass),
        ]
        if not value
    ]
    if missing:
        raise TransferError("Missing credentials: " + ", ".join(missing))

    dest_code = args.dest_code or args.problem_code
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Logging in to source {args.source_base}")
    source = login_tinhoctre(args.source_base, args.source_user, args.source_pass, args.problem_code)
    print(f"Fetching source problem {args.problem_code}")
    info, zip_path, cases, zip_url = fetch_source_problem(
        source, args.source_base, args.problem_code, out_dir
    )
    print(f"Downloaded tests: {zip_url} -> {zip_path}")
    print(f"Read problem: {info.code} / {info.name} / {len(cases)} cases")

    print(f"Logging in to destination {args.dest_base}")
    dest = login_hncode(args.dest_base, args.dest_user, args.dest_pass)
    exists = destination_problem_exists(dest, args.dest_base, dest_code)
    if exists and args.if_exists == "fail":
        raise TransferError(f"Destination problem already exists: {dest_code}")
    if args.skip_create:
        print(f"Skipping destination create by request: {dest_code}")
    elif not exists:
        print(f"Creating destination problem {dest_code}")
        change_url = create_hncode_problem(
            dest,
            args.dest_base,
            info,
            dest_code=dest_code,
            type_id=args.dest_type_id,
            group_id=args.dest_group_id,
            public=args.public,
            allow_all_languages=not args.no_all_languages,
            allowed_language_ids=parse_id_list(args.allowed_language_ids),
        )
        print(f"Created: {change_url}")
    else:
        print(f"Destination problem exists; skipping create: {dest_code}")

    if args.skip_upload_tests:
        print("Skipping test upload by request")
    else:
        print("Uploading and applying tests")
        yaml_url = upload_hncode_tests(dest, args.dest_base, dest_code, zip_path, cases)
        print(f"Verified test YAML: {yaml_url}")
    print(f"Done: {urljoin(args.dest_base, f'/problem/{dest_code}')}")
    return 0


def parse_id_list(raw: str) -> list[str]:
    return [part.strip() for part in re.split(r"[, ]+", raw) if part.strip()]


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except TransferError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
