"""Small Quiz helpers shared by the Flask app."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin


def find_image_in_dir(img_name: str, search_dir: Path) -> Path | None:
    name_no_ext = img_name.rsplit(".", 1)[0].lower()
    name_clean = re.sub(r"[^a-z0-9]", "", name_no_ext)

    if not search_dir.exists() or not search_dir.is_dir():
        return None

    for file in search_dir.rglob("*"):
        if not file.is_file():
            continue
        file_no_ext = file.stem.lower()
        file_clean = re.sub(r"[^a-z0-9]", "", file_no_ext)
        if file_clean == name_clean or file_no_ext == name_no_ext:
            return file
    return None


def upload_quiz_image(session, base_url: str, filepath: Path) -> str | None:
    upload_url = urljoin(base_url, "/pagedown/image-upload/")
    headers = {"Referer": base_url}
    csrf_token = session.cookies.get("csrftoken")
    if csrf_token:
        headers["X-CSRFToken"] = csrf_token

    with filepath.open("rb") as file:
        response = session.post(upload_url, files={"image": file}, headers=headers, timeout=30)

    if not response.ok:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    return data.get("url") if data.get("success") else None
