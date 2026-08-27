"""Prepare the latest OJ submission for every account/problem pair."""

from __future__ import annotations

import csv
import io
import json
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests


SUBMISSION_NAME_RE = re.compile(r"^(?P<id>\d+)_(?P<username>.+)\.(?P<language>[^.]+)$")
EXPORTED_SUBMISSION_NAME_RE = re.compile(
    r"^(?P<username>.+?)__sub(?P<id>\d+)(?:__.*)?\.(?P<language>[^.]+)$",
    re.IGNORECASE,
)
PROBLEM_LINK_RE = re.compile(
    r"<a\b[^>]*href=[\"'](?:https?://[^/]+)?/problem/(?P<code>[A-Za-z0-9_-]+)(?:/)?[\"'][^>]*>(?P<name>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class SubmissionArchiveEntry:
    member: str
    submission_id: int
    username: str
    language: str


@dataclass(frozen=True)
class SubmissionMetadata:
    submission_id: int
    problem_code: str
    problem_name: str = ""


@dataclass(frozen=True)
class ResolvedSubmission:
    entry: SubmissionArchiveEntry
    metadata: SubmissionMetadata


@dataclass(frozen=True)
class SubmissionPackage:
    entries: list[SubmissionArchiveEntry]
    metadata_by_id: dict[int, SubmissionMetadata]


def parse_submission_filename(name: str) -> SubmissionArchiveEntry | None:
    """Parse supported raw and exported OJ source filenames."""
    basename = Path(name.replace("\\", "/")).name
    match = SUBMISSION_NAME_RE.fullmatch(basename)
    if not match:
        match = EXPORTED_SUBMISSION_NAME_RE.fullmatch(basename)
    if not match:
        return None
    username = match.group("username").strip()
    language = match.group("language").strip()
    if not username or not language:
        return None
    return SubmissionArchiveEntry(
        member=name,
        submission_id=int(match.group("id")),
        username=username,
        language=language,
    )


def _problem_from_manifest(data: dict, row: dict) -> tuple[str, str]:
    problem = row.get("problem") or data.get("problem") or {}
    code = str(row.get("problem_code") or row.get("code") or "").strip()
    name = str(row.get("problem_name") or "").strip()
    if isinstance(problem, dict):
        code = code or str(problem.get("code") or "").strip()
        name = name or str(problem.get("name") or problem.get("title") or "").strip()
    elif problem:
        code = code or str(problem).strip()
    return code, name


def _archive_member_for_file(member_names: list[str], manifest_name: str, filename: str) -> str:
    normalized_file = str(filename or "").replace("\\", "/").strip().lstrip("/")
    if not normalized_file:
        return ""
    if normalized_file in member_names:
        return normalized_file
    manifest_parent = str(Path(manifest_name.replace("\\", "/")).parent).replace("\\", "/")
    preferred = f"{manifest_parent}/sources/{Path(normalized_file).name}".lstrip("./")
    if preferred in member_names:
        return preferred
    basename = Path(normalized_file).name.casefold()
    matches = [name for name in member_names if Path(name.replace("\\", "/")).name.casefold() == basename]
    return matches[0] if len(matches) == 1 else ""


def _read_json_manifest(
    archive: zipfile.ZipFile,
    manifest_name: str,
    member_names: list[str],
) -> SubmissionPackage:
    data = json.loads(archive.read(manifest_name).decode("utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("submissions"), list):
        raise ValueError(f"Manifest {manifest_name} không có danh sách submissions hợp lệ.")
    entries: list[SubmissionArchiveEntry] = []
    metadata_by_id: dict[int, SubmissionMetadata] = {}
    for row in data["submissions"]:
        if not isinstance(row, dict):
            continue
        filename = str(row.get("file") or row.get("filename") or row.get("source_file") or "")
        member = _archive_member_for_file(member_names, manifest_name, filename)
        if not member:
            continue
        parsed = parse_submission_filename(member)
        try:
            submission_id = int(row.get("submission_id") or row.get("id") or (parsed.submission_id if parsed else 0))
        except (TypeError, ValueError):
            continue
        username = str(row.get("username") or row.get("user") or (parsed.username if parsed else "")).strip()
        extension = Path(member.replace("\\", "/")).suffix.lstrip(".")
        language = extension or str(row.get("language") or (parsed.language if parsed else "")).strip()
        if not submission_id or not username or not language:
            continue
        entries.append(SubmissionArchiveEntry(member, submission_id, username, language))
        code, name = _problem_from_manifest(data, row)
        if code:
            metadata_by_id[submission_id] = SubmissionMetadata(submission_id, code, name)
    return SubmissionPackage(entries, metadata_by_id)


def _infer_problem_code(zip_path: Path) -> str:
    stem = zip_path.stem.strip()
    stem = re.sub(r"^export[-_]", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[-_](?:last[-_])?submissions?$", "", stem, flags=re.IGNORECASE)
    return stem if re.fullmatch(r"[A-Za-z0-9_-]+", stem) else ""


def _read_csv_manifest(
    archive: zipfile.ZipFile,
    manifest_name: str,
    member_names: list[str],
    fallback_problem_code: str,
) -> SubmissionPackage:
    text = archive.read(manifest_name).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    entries: list[SubmissionArchiveEntry] = []
    metadata_by_id: dict[int, SubmissionMetadata] = {}
    for row in reader:
        filename = str(row.get("file") or row.get("filename") or row.get("source_file") or "")
        member = _archive_member_for_file(member_names, manifest_name, filename)
        if not member:
            continue
        parsed = parse_submission_filename(member)
        try:
            submission_id = int(row.get("submission_id") or row.get("id") or (parsed.submission_id if parsed else 0))
        except (TypeError, ValueError):
            continue
        username = str(row.get("username") or row.get("user") or (parsed.username if parsed else "")).strip()
        extension = Path(member.replace("\\", "/")).suffix.lstrip(".")
        language = extension or str(row.get("language") or (parsed.language if parsed else "")).strip()
        if not submission_id or not username or not language:
            continue
        entries.append(SubmissionArchiveEntry(member, submission_id, username, language))
        code = str(row.get("problem_code") or row.get("problem") or fallback_problem_code).strip()
        name = str(row.get("problem_name") or row.get("problem_title") or "").strip()
        if code:
            metadata_by_id[submission_id] = SubmissionMetadata(submission_id, code, name)
    return SubmissionPackage(entries, metadata_by_id)


def read_submission_package(zip_path: Path) -> SubmissionPackage:
    """Read raw exports or manifest-based exports without assuming one directory layout."""
    with zipfile.ZipFile(zip_path) as archive:
        member_names = [info.filename for info in archive.infolist() if not info.is_dir()]
        json_manifests = [
            name for name in member_names if Path(name.replace("\\", "/")).name.casefold() == "submissions.json"
        ]
        if json_manifests:
            packages = []
            for name in json_manifests:
                try:
                    packages.append(_read_json_manifest(archive, name, member_names))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    continue
            entries = [entry for package in packages for entry in package.entries]
            metadata = {
                submission_id: item
                for package in packages
                for submission_id, item in package.metadata_by_id.items()
            }
            if entries:
                return SubmissionPackage(sorted(entries, key=lambda item: item.submission_id), metadata)

        csv_manifests = [
            name for name in member_names if Path(name.replace("\\", "/")).name.casefold() == "submissions.csv"
        ]
        if csv_manifests:
            fallback_code = _infer_problem_code(zip_path)
            packages = [
                _read_csv_manifest(archive, name, member_names, fallback_code)
                for name in csv_manifests
            ]
            entries = [entry for package in packages for entry in package.entries]
            metadata = {
                submission_id: item
                for package in packages
                for submission_id, item in package.metadata_by_id.items()
            }
            if entries:
                return SubmissionPackage(sorted(entries, key=lambda item: item.submission_id), metadata)

        entries = []
        for member in member_names:
            parsed = parse_submission_filename(member)
            if parsed:
                entries.append(parsed)
        return SubmissionPackage(sorted(entries, key=lambda item: item.submission_id), {})


def read_submission_archive(zip_path: Path) -> list[SubmissionArchiveEntry]:
    """Backward-compatible helper returning only source entries."""
    return read_submission_package(zip_path).entries


def parse_submission_page(page: str, submission_id: int) -> SubmissionMetadata:
    """Read the problem link from a DMOJ-compatible submission page."""
    for match in PROBLEM_LINK_RE.finditer(page):
        code = unescape(match.group("code")).strip()
        if not code:
            continue
        raw_name = TAG_RE.sub("", match.group("name"))
        problem_name = re.sub(r"\s+", " ", unescape(raw_name)).strip()
        return SubmissionMetadata(submission_id, code, problem_name)
    raise ValueError(f"Không tìm thấy mã bài trên trang submission {submission_id}.")


def _copy_session(source: requests.Session) -> requests.Session:
    session = requests.Session()
    session.headers.update(source.headers)
    session.cookies.update(source.cookies)
    return session


def _fetch_one(
    source_session: requests.Session,
    base_url: str,
    submission_id: int,
    retries: int,
    timeout: float,
) -> SubmissionMetadata:
    url = urljoin(base_url.rstrip("/") + "/", f"submission/{submission_id}")
    last_error = ""
    for attempt in range(retries + 1):
        session = _copy_session(source_session)
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            if response.status_code in RETRY_STATUSES and attempt < retries:
                last_error = f"HTTP {response.status_code}"
                time.sleep(min(1.5 * (attempt + 1), 5.0))
                continue
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}")
            final_path = response.url.lower()
            if "/login" in final_path or "/accounts/login" in final_path:
                raise RuntimeError("Phiên đăng nhập đã hết hạn hoặc không có quyền xem submission")
            return parse_submission_page(response.text, submission_id)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(1.5 * (attempt + 1), 5.0))
                continue
            break
    raise RuntimeError(last_error or "Không đọc được submission")


def resolve_submission_metadata(
    session: requests.Session,
    base_url: str,
    entries: list[SubmissionArchiveEntry],
    *,
    workers: int = 5,
    retries: int = 2,
    timeout: float = 30.0,
) -> tuple[dict[int, SubmissionMetadata], dict[int, str]]:
    """Resolve submission IDs concurrently while retaining per-ID errors."""
    submission_ids = sorted({entry.submission_id for entry in entries})
    metadata: dict[int, SubmissionMetadata] = {}
    errors: dict[int, str] = {}
    if not submission_ids:
        return metadata, errors
    max_workers = max(1, min(workers, len(submission_ids)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_one, session, base_url, submission_id, retries, timeout): submission_id
            for submission_id in submission_ids
        }
        for future in as_completed(futures):
            submission_id = futures[future]
            try:
                metadata[submission_id] = future.result()
            except Exception as exc:
                errors[submission_id] = str(exc)
    return metadata, errors


def select_latest_submissions(
    entries: list[SubmissionArchiveEntry],
    metadata_by_id: dict[int, SubmissionMetadata],
) -> tuple[list[ResolvedSubmission], list[SubmissionArchiveEntry]]:
    latest: dict[tuple[str, str], ResolvedSubmission] = {}
    unresolved: list[SubmissionArchiveEntry] = []
    for entry in entries:
        metadata = metadata_by_id.get(entry.submission_id)
        if not metadata:
            unresolved.append(entry)
            continue
        key = (entry.username.casefold(), metadata.problem_code.casefold())
        candidate = ResolvedSubmission(entry, metadata)
        current = latest.get(key)
        if current is None or entry.submission_id > current.entry.submission_id:
            latest[key] = candidate
    selected = sorted(
        latest.values(),
        key=lambda item: (item.entry.username.casefold(), item.metadata.problem_code.casefold()),
    )
    return selected, unresolved


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", value.strip())
    cleaned = cleaned.rstrip(". ")
    return cleaned or "unknown"


def write_result_archive(
    source_zip: Path,
    output_zip: Path,
    selected: list[ResolvedSubmission],
    unresolved: list[SubmissionArchiveEntry],
    errors_by_id: dict[int, str] | None = None,
) -> dict:
    errors_by_id = errors_by_id or {}
    report_buffer = io.StringIO(newline="")
    writer = csv.writer(report_buffer)
    writer.writerow(
        [
            "username",
            "problem_code",
            "problem_name",
            "submission_id",
            "language",
            "source_file",
            "output_file",
            "status",
            "error",
        ]
    )
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_zip) as source, zipfile.ZipFile(
        output_zip, "w", compression=zipfile.ZIP_DEFLATED
    ) as output:
        used_names: set[str] = set()
        for item in selected:
            entry = item.entry
            metadata = item.metadata
            extension = _safe_component(entry.language)
            relative_name = (
                f"{_safe_component(entry.username)}/"
                f"{_safe_component(metadata.problem_code)}.{extension}"
            )
            normalized_name = relative_name.casefold()
            if normalized_name in used_names:
                relative_name = (
                    f"{_safe_component(entry.username)}/"
                    f"{_safe_component(metadata.problem_code)}_{entry.submission_id}.{extension}"
                )
            used_names.add(relative_name.casefold())
            output.writestr(relative_name, source.read(entry.member))
            writer.writerow(
                [
                    entry.username,
                    metadata.problem_code,
                    metadata.problem_name,
                    entry.submission_id,
                    entry.language,
                    entry.member,
                    relative_name,
                    "ok",
                    "",
                ]
            )
        for entry in unresolved:
            writer.writerow(
                [
                    entry.username,
                    "",
                    "",
                    entry.submission_id,
                    entry.language,
                    entry.member,
                    "",
                    "error",
                    errors_by_id.get(entry.submission_id, "Không xác định được mã bài"),
                ]
            )
        output.writestr("report.csv", "\ufeff" + report_buffer.getvalue())

    return {
        "mode": "oj",
        "total_submissions": len(selected) + len(unresolved),
        "selected": len(selected),
        "accounts": len({item.entry.username.casefold() for item in selected}),
        "problems": len({item.metadata.problem_code.casefold() for item in selected}),
        "unresolved": len(unresolved),
    }
