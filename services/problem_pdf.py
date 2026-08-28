"""PDF statement discovery, download, and upload helpers for supported OJ sites."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests


PDF_CONTENT_TYPE = "application/pdf"
HNOJ_MAX_PDF_SIZE = 5 * 1024 * 1024


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[list[tuple[str, str]]] = []
        self.current: list[tuple[str, str]] | None = None
        self.select: dict | None = None
        self.textarea: dict | None = None

    @staticmethod
    def _attrs(attrs) -> dict[str, str]:
        return {str(key): "" if value is None else str(value) for key, value in attrs}

    def handle_starttag(self, tag: str, attrs) -> None:
        values = self._attrs(attrs)
        if tag == "form":
            self.current = []
            return
        if self.current is None:
            return
        if tag == "input":
            name = values.get("name", "")
            input_type = values.get("type", "text").lower()
            if not name or "disabled" in values or input_type in {"file", "submit", "button", "image", "reset"}:
                return
            if input_type in {"checkbox", "radio"}:
                if "checked" in values:
                    self.current.append((name, values.get("value") or "on"))
                return
            self.current.append((name, values.get("value", "")))
            return
        if tag == "select":
            self.select = {
                "name": values.get("name", ""),
                "multiple": "multiple" in values,
                "disabled": "disabled" in values,
                "options": [],
            }
            return
        if tag == "option" and self.select is not None:
            self.select["options"].append(
                {"value": values.get("value", ""), "selected": "selected" in values}
            )
            return
        if tag == "textarea":
            self.textarea = {
                "name": values.get("name", ""),
                "disabled": "disabled" in values,
                "parts": [],
            }

    def handle_data(self, data: str) -> None:
        if self.textarea is not None:
            self.textarea["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None
            return
        if self.current is None:
            return
        if tag == "select" and self.select is not None:
            options = self.select.get("options") or []
            selected = [option for option in options if option.get("selected")]
            if not selected and not self.select.get("multiple") and options:
                selected = [options[0]]
            name = str(self.select.get("name") or "")
            if name and not self.select.get("disabled"):
                self.current.extend((name, str(option.get("value") or "")) for option in selected)
            self.select = None
            return
        if tag == "textarea" and self.textarea is not None:
            name = str(self.textarea.get("name") or "")
            if name and not self.textarea.get("disabled"):
                self.current.append((name, "".join(self.textarea.get("parts") or [])))
            self.textarea = None


def _csrf_token(page: str) -> str:
    patterns = [
        r'name=["\']csrfmiddlewaretoken["\'][^>]*value=["\']([^"\']+)',
        r'value=["\']([^"\']+)["\'][^>]*name=["\']csrfmiddlewaretoken["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, page, re.I)
        if match:
            return html.unescape(match.group(1))
    raise RuntimeError("Không tìm thấy CSRF token trên form PDF.")


def _form_errors(page: str) -> list[str]:
    errors: list[str] = []
    patterns = [
        r'<ul\b[^>]*class=["\'][^"\']*errorlist[^"\']*["\'][^>]*>(.*?)</ul>',
        r'<div\b[^>]*class=["\'][^"\']*(?:alert-error|errornote)[^"\']*["\'][^>]*>(.*?)</div>',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, page, re.I | re.S):
            value = re.sub(r"\s+", " ", html.unescape(re.sub(r"<.*?>", " ", match.group(1)))).strip()
            if value:
                errors.append(value)
    return errors


def _json_error(response: requests.Response, action: str) -> RuntimeError:
    try:
        payload = response.json()
        detail = payload.get("error") or payload.get("message") or json.dumps(payload, ensure_ascii=False)
    except Exception:
        detail = re.sub(r"\s+", " ", response.text or "").strip()[:500]
    return RuntimeError(f"{action} lỗi HTTP {response.status_code}: {detail or 'không có nội dung'}")


def _input_value(page: str, name: str) -> str:
    match = re.search(
        r'<input\b(?=[^>]*\bname=["\']' + re.escape(name) + r'["\'])[^>]*>',
        page,
        re.I | re.S,
    )
    if not match:
        return ""
    value = re.search(r'value=["\']([^"\']*)', match.group(0), re.I)
    return html.unescape(value.group(1)) if value else ""


def find_problem_pdf_url(base_url: str, problem_code: str, public_page: str, edit_page: str = "") -> str:
    """Find a directly downloadable PDF URL from public/edit problem HTML."""
    combined = public_page + "\n" + edit_page
    patterns = [
        r'(?:href|src|data)=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
        r'(https?://[^"\'<>\s]+\.pdf(?:\?[^"\'<>\s]+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, combined, re.I)
        if match:
            return urljoin(base_url, html.unescape(match.group(1)))
    pdf_url = _input_value(edit_page, "pdf_url")
    if pdf_url:
        return urljoin(base_url, pdf_url)
    pdf_key = _input_value(edit_page, "pdf_description")
    if pdf_key:
        return urljoin(base_url, f"/problem/{problem_code}/data/statement.pdf")
    return ""


def download_problem_pdf(
    session: requests.Session,
    base_url: str,
    problem_code: str,
    output_dir: Path,
    *,
    public_page: str = "",
    edit_page: str = "",
) -> Path | None:
    if not public_page:
        response = session.get(urljoin(base_url, f"/problem/{problem_code}"), timeout=30)
        if response.ok:
            public_page = response.text
    pdf_url = find_problem_pdf_url(base_url, problem_code, public_page, edit_page)
    if not pdf_url:
        return None
    response = session.get(pdf_url, timeout=60, allow_redirects=True)
    if not response.ok:
        raise RuntimeError(f"Tải PDF nguồn {problem_code} lỗi HTTP {response.status_code}.")
    content = response.content
    if not content.lstrip().startswith(b"%PDF"):
        content_type = response.headers.get("Content-Type", "")
        raise RuntimeError(
            f"Link PDF nguồn {problem_code} không trả dữ liệu PDF (Content-Type: {content_type or 'không rõ'})."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{problem_code}.pdf"
    path.write_bytes(content)
    return path


def _direct_upload_widget(page: str) -> dict[str, str]:
    for match in re.finditer(r"<div\b([^>]*)>", page, re.I | re.S):
        attrs_text = match.group(1)
        if "data-direct-upload" not in attrs_text or (
            "data-widget-type=\"pdf\"" not in attrs_text
            and "data-widget-type='pdf'" not in attrs_text
        ):
            continue
        attrs = {
            key.lower(): html.unescape(value)
            for key, _quote, value in re.findall(r"([\w-]+)\s*=\s*([\"'])(.*?)\2", attrs_text, re.S)
        }
        if attrs.get("data-upload-token"):
            return attrs
    raise RuntimeError("Không tìm thấy widget upload PDF trên form sửa bài.")


def _upload_direct_pdf(
    session: requests.Session,
    base_url: str,
    problem_code: str,
    pdf_path: Path,
) -> str:
    edit_url = urljoin(base_url, f"/problem/{problem_code}/edit")
    page = session.get(edit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form PDF của {problem_code}: HTTP {page.status_code}")
    widget = _direct_upload_widget(page.text)
    max_size = int(widget.get("data-max-size") or 0)
    if max_size and pdf_path.stat().st_size > max_size:
        raise RuntimeError(
            f"PDF {pdf_path.name} có dung lượng {pdf_path.stat().st_size} byte, vượt giới hạn {max_size} byte."
        )
    csrf = _csrf_token(page.text)
    config_url = urljoin(base_url, widget.get("data-config-url") or "/api/upload/config/")
    config_response = session.post(
        config_url,
        json={
            "upload_token": widget["data-upload-token"],
            "filename": pdf_path.name,
            "content_type": PDF_CONTENT_TYPE,
            "file_size": pdf_path.stat().st_size,
        },
        headers={"X-CSRFToken": csrf, "Referer": edit_url},
        timeout=30,
    )
    if not config_response.ok:
        raise _json_error(config_response, "Lấy cấu hình upload PDF")
    config = config_response.json()
    upload_url = urljoin(base_url, str(config.get("upload_url") or ""))
    if not upload_url:
        raise RuntimeError("Cấu hình upload PDF không có upload_url.")
    with pdf_path.open("rb") as source:
        if config.get("storage_type") == "s3":
            upload_response = requests.put(
                upload_url,
                data=source,
                headers={"Content-Type": str(config.get("content_type") or PDF_CONTENT_TYPE)},
                timeout=120,
            )
        else:
            upload_response = session.post(
                upload_url,
                files={"file": (pdf_path.name, source, PDF_CONTENT_TYPE)},
                headers={
                    "X-Upload-Token": str(config.get("token") or ""),
                    "X-CSRFToken": csrf,
                    "Referer": edit_url,
                },
                timeout=120,
            )
    if not upload_response.ok:
        raise _json_error(upload_response, "Upload file PDF")
    file_key = str(config.get("file_key") or "")
    if not file_key:
        raise RuntimeError("Cấu hình upload PDF không có file_key.")
    save_url = urljoin(base_url, widget.get("data-save-url") or "/api/upload/save/")
    save_response = session.post(
        save_url,
        json={"file_key": file_key, "upload_token": widget["data-upload-token"]},
        headers={"X-CSRFToken": csrf, "Referer": edit_url},
        timeout=30,
    )
    if not save_response.ok:
        raise _json_error(save_response, "Lưu PDF vào bài")
    verify = session.get(edit_url, timeout=30)
    saved_key = _input_value(verify.text, "pdf_description") if verify.ok else ""
    if saved_key and saved_key != file_key:
        raise RuntimeError(f"PDF đã upload nhưng khóa lưu không khớp: {saved_key!r} != {file_key!r}")
    if not saved_key:
        raise RuntimeError("PDF đã upload nhưng form sửa bài chưa hiển thị file đã lưu.")
    return urljoin(base_url, f"/problem/{problem_code}/data/statement.pdf")


def _upload_hnoj_pdf(
    session: requests.Session,
    base_url: str,
    problem_code: str,
    pdf_path: Path,
) -> str:
    if pdf_path.stat().st_size > HNOJ_MAX_PDF_SIZE:
        raise RuntimeError(
            f"HNOJ chỉ nhận PDF tối đa {HNOJ_MAX_PDF_SIZE} byte; file {pdf_path.name} có {pdf_path.stat().st_size} byte."
        )
    edit_url = urljoin(base_url, f"/problem/{problem_code}/edit")
    page = session.get(edit_url, timeout=30)
    if not page.ok:
        raise RuntimeError(f"Không mở được form PDF HNOJ của {problem_code}: HTTP {page.status_code}")
    if not re.search(r'name=["\']statement_file["\']', page.text, re.I):
        raise RuntimeError("Form sửa bài HNOJ không có trường statement_file.")
    parser = _FormParser()
    parser.feed(page.text)
    data = next(
        (form for form in parser.forms if any(name == "code" for name, _value in form)),
        None,
    )
    if not data:
        raise RuntimeError("Không đọc được form sửa bài HNOJ.")
    with pdf_path.open("rb") as source:
        result = session.post(
            edit_url,
            data=data,
            files={"statement_file": (pdf_path.name, source, PDF_CONTENT_TYPE)},
            headers={"Referer": edit_url},
            allow_redirects=True,
            timeout=120,
        )
    if not result.ok:
        raise RuntimeError(f"Upload PDF HNOJ lỗi HTTP {result.status_code}")
    errors = _form_errors(result.text)
    if errors:
        raise RuntimeError("Form PDF HNOJ báo lỗi: " + "; ".join(errors))
    if "/accounts/login" in result.url or "/admin/login" in result.url:
        raise RuntimeError("Upload PDF HNOJ bị chuyển về trang đăng nhập.")
    return result.url


def upload_problem_pdf(
    session: requests.Session,
    target: str,
    base_url: str,
    problem_code: str,
    pdf_path: Path,
) -> str:
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise RuntimeError(f"File đề PDF không hợp lệ: {pdf_path}")
    if target == "hnoj":
        return _upload_hnoj_pdf(session, base_url, problem_code, pdf_path)
    if target in {"hncode", "tinhoctre"}:
        return _upload_direct_pdf(session, base_url, problem_code, pdf_path)
    raise RuntimeError(f"Web đích không hỗ trợ PDF: {target}")
