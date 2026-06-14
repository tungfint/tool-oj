#!/usr/bin/env python3
"""Create HNOJ problems directly from a bundled local zip."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

from transfer_tinhoctre_to_hncode import (
    ProblemInfo,
    TestCase,
    TransferError,
    create_hncode_problem,
    destination_problem_exists,
    login_hncode,
    upload_hncode_tests,
)
from upload_tinhoctre_batch import discover_bundles, generate_tests, statement_body_text


DEFAULT_BASE_URL = "https://hnoj.edu.vn"
DEFAULT_TYPE_ID = "1"  # Chua phan loai
DEFAULT_GROUP_ID = "1"  # Chua phan loai
DEFAULT_LANGUAGE_IDS = "4,7,9,12"  # C++17, Pascal, Python 3, Scratch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def require(condition: object, message: str) -> None:
    if not condition:
        raise TransferError(message)


def extract_zip(zip_path: Path, source_dir: Path) -> None:
    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(source_dir)


def test_cases_from_files(input_files: list[str], output_files: list[str]) -> list[TestCase]:
    return [
        TestCase(order=index, kind="C", input_file=inp, output_file=out, points="1")
        for index, (inp, out) in enumerate(zip(input_files, output_files), 1)
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload new HNOJ problems from a local zip package")
    parser.add_argument("zip_path", type=Path, help="Input package zip")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--username", default=os.getenv("HNOJ_USER", "hncode"))
    parser.add_argument("--password", default=os.getenv("HNOJ_PASS"))
    parser.add_argument("--type-id", default=DEFAULT_TYPE_ID)
    parser.add_argument("--group-id", default=DEFAULT_GROUP_ID)
    parser.add_argument("--time-limit", default="1.0")
    parser.add_argument("--memory-limit", default="1048576")
    parser.add_argument("--memory-unit", default="KB")
    parser.add_argument("--points", default="100")
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--no-all-languages", action="store_true")
    parser.add_argument("--allowed-language-ids", default=DEFAULT_LANGUAGE_IDS)
    parser.add_argument("--if-exists", choices=["fail", "skip-create"], default="fail")
    parser.add_argument("--skip-create", action="store_true", help="Do not create/update problem statement")
    parser.add_argument("--skip-upload-tests", action="store_true", help="Do not upload/apply test data")
    parser.add_argument("--no-submit", action="store_true", help="Accepted for UI symmetry; HNOJ upload does not submit")
    parser.add_argument("--only", nargs="*", help="Optional problem codes to process")
    parser.add_argument("--out-dir", type=Path, default=Path("hnoj_upload_artifacts"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    require(args.zip_path.exists(), f"Zip not found: {args.zip_path}")
    require(args.password or args.dry_run, "Missing password. Set HNOJ_PASS or pass --password.")

    source_dir = args.out_dir / "source"
    build_root = args.out_dir / "generated"
    args.out_dir.mkdir(parents=True, exist_ok=True)
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
        sol_note = "has solution" if bundle.solution else "no solution"
        print(f"Prepared {bundle.code}: {bundle.name}, {len(tests.input_files)} tests, {sol_note}, {tests.zip_path}")

    if args.dry_run:
        print("Dry run completed; no HTTP changes were made.")
        return 0

    dest = login_hncode(args.base_url, args.username, args.password)
    for bundle in bundles:
        info = ProblemInfo(
            code=bundle.code,
            name=bundle.name,
            description=statement_body_text(bundle.statement.read_text(encoding="utf-8"), skip_title_line=True).replace("$", "~"),
            points=args.points,
            partial=True,
            time_limit=args.time_limit,
            memory_limit=args.memory_limit,
            memory_unit=args.memory_unit,
        )
        exists = destination_problem_exists(dest, args.base_url, bundle.code)
        if args.skip_create:
            print(f"Skipping create by request: {bundle.code}")
        elif exists and args.if_exists == "fail":
            raise TransferError(f"Destination problem already exists: {bundle.code}")
        elif not exists:
            print(f"Creating HNOJ problem {bundle.code}")
            change_url = create_hncode_problem(
                dest,
                args.base_url,
                info,
                dest_code=bundle.code,
                type_id=args.type_id,
                group_id=args.group_id,
                public=args.public,
                allow_all_languages=not args.no_all_languages,
                allowed_language_ids=parse_id_list(args.allowed_language_ids),
            )
            print(f"Created: {change_url}")
        else:
            print(f"Problem exists; skipping create: {bundle.code}")

        if args.skip_upload_tests:
            print(f"Skipping test upload by request: {bundle.code}")
        else:
            tests = generated[bundle.code]
            print(f"Uploading tests for {bundle.code}")
            yaml_url = upload_hncode_tests(
                dest,
                args.base_url,
                bundle.code,
                tests.zip_path,
                test_cases_from_files(tests.input_files, tests.output_files),
            )
            print(f"Verified test YAML: {yaml_url}")
    print("Done.")
    return 0


def parse_id_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.replace(",", " ").split() if part.strip()]


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except TransferError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
