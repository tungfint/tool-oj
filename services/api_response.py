"""Small helpers for consistent JSON API responses."""

from __future__ import annotations

from flask import jsonify


def api_success(
    *,
    message: str = "",
    rows: list | None = None,
    log: str = "",
    errors: list | None = None,
    meta: dict | None = None,
    status: int = 200,
    **extra,
):
    payload = {
        "ok": True,
        "message": message,
        "rows": rows or [],
        "log": log,
        "errors": errors or [],
        "meta": meta or {},
    }
    payload.update(extra)
    return jsonify(payload), status


def api_error(
    message: str,
    *,
    errors: list | None = None,
    log: str = "",
    meta: dict | None = None,
    status: int = 400,
    **extra,
):
    payload = {
        "ok": False,
        "message": message,
        "error": message,
        "rows": [],
        "log": log,
        "errors": errors or [],
        "meta": meta or {},
    }
    payload.update(extra)
    return jsonify(payload), status

