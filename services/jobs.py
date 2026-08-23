"""Small file-backed job/progress store used by long-running UI actions."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


JOB_ID_RE = re.compile(r"[0-9a-f]{32}")


def valid_job_id(job_id: str | None) -> str | None:
    if job_id and JOB_ID_RE.fullmatch(job_id):
        return job_id
    return None


def job_path(progress_dir: Path, job_id: str) -> Path:
    return progress_dir / f"{job_id}.json"


def waiting_payload() -> dict[str, Any]:
    return {
        "job_id": "",
        "phase": "waiting",
        "done": 0,
        "total": 0,
        "rows": [],
        "log": "",
        "message": "",
        "status": "waiting",
        "finished": False,
        "ok": None,
    }


def normalize_payload(job_id: str, current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    payload = dict(current or {})
    payload.update(updates)
    payload.setdefault("created_at", now)
    payload["updated_at"] = now
    payload["job_id"] = job_id
    payload.setdefault("phase", "")
    payload.setdefault("done", 0)
    payload.setdefault("total", 0)
    payload.setdefault("rows", [])
    payload.setdefault("log", "")
    payload.setdefault("message", "")

    if payload.get("finished"):
        payload["status"] = "done" if payload.get("ok") else "failed"
    else:
        payload.setdefault("status", "running")
    return payload


def read_job(progress_dir: Path, job_id: str | None) -> dict[str, Any]:
    job_id = valid_job_id(job_id)
    if not job_id:
        raise ValueError("progress_id không hợp lệ")
    path = job_path(progress_dir, job_id)
    if not path.exists():
        data = waiting_payload()
        data["job_id"] = job_id
        return data
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = waiting_payload()
        data["job_id"] = job_id
        data["status"] = "failed"
        data["finished"] = True
        data["ok"] = False
        data["message"] = "Không đọc được file tiến độ."
        return data


def update_job(progress_dir: Path, job_id: str | None, **updates: Any) -> dict[str, Any] | None:
    job_id = valid_job_id(job_id)
    if not job_id:
        return None
    progress_dir.mkdir(parents=True, exist_ok=True)
    path = job_path(progress_dir, job_id)
    current: dict[str, Any] = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    payload = normalize_payload(job_id, current, updates)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return payload


def finish_job(progress_dir: Path, job_id: str | None, ok: bool, message: str = "") -> dict[str, Any] | None:
    return update_job(progress_dir, job_id, finished=True, ok=ok, message=message)
