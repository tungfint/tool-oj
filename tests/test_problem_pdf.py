import tempfile
import unittest
from pathlib import Path

from services import problem_pdf
from transfer_tinhoctre_to_hncode import fetch_source_problem


class FakeResponse:
    def __init__(self, *, text="", content=b"", status=200, url="https://example.test/result", payload=None, headers=None):
        self.text = text
        self.content = content
        self.status_code = status
        self.ok = 200 <= status < 400
        self.url = url
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class DirectUploadSession:
    def __init__(self):
        self.posts = []
        self.saved = False

    def get(self, url, **_kwargs):
        if url.endswith("/edit"):
            saved = '<input name="pdf_description" value="demo/statement.pdf">' if self.saved else ""
            return FakeResponse(
                text=(
                    '<input name="csrfmiddlewaretoken" value="csrf">'
                    '<div data-direct-upload data-widget-type="pdf" '
                    'data-config-url="/api/upload/config/" data-save-url="/api/upload/save/" '
                    'data-upload-token="upload-token" data-max-size="10485760"></div>'
                    + saved
                ),
                url=url,
            )
        raise AssertionError(url)

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if url.endswith("/api/upload/config/"):
            return FakeResponse(
                payload={
                    "storage_type": "local",
                    "upload_url": "/api/upload/file/",
                    "token": "file-token",
                    "file_key": "demo/statement.pdf",
                },
                url=url,
            )
        if url.endswith("/api/upload/file/"):
            return FakeResponse(payload={"ok": True}, url=url)
        if url.endswith("/api/upload/save/"):
            self.saved = True
            return FakeResponse(payload={"ok": True}, url=url)
        raise AssertionError(url)


class DownloadSession:
    def get(self, url, **_kwargs):
        return FakeResponse(content=b"%PDF-1.7\nfixture", headers={"Content-Type": "application/pdf"}, url=url)


class HnojSession:
    def __init__(self):
        self.post_kwargs = None

    def get(self, url, **_kwargs):
        return FakeResponse(
            text=(
                '<form method="post"><input name="csrfmiddlewaretoken" value="csrf">'
                '<input name="code" value="demo"><input name="name" value="Demo">'
                '<textarea name="description">Statement</textarea>'
                '<input type="file" name="statement_file"></form>'
            ),
            url=url,
        )

    def post(self, url, **kwargs):
        self.post_kwargs = kwargs
        return FakeResponse(text="<html>saved</html>", url=url)


class SourceProblemSession:
    def get(self, url, **_kwargs):
        if url.endswith("/problem/demo/edit"):
            return FakeResponse(
                text=(
                    '<input name="code" value="demo"><input name="name" value="Bài PDF">'
                    '<textarea name="description"></textarea><input name="points" value="100">'
                    '<input name="time_limit" value="1"><input name="memory_limit" value="1048576">'
                    '<select name="memory_unit"><option value="KB" selected>KB</option></select>'
                    '<input name="pdf_description" value="demo/statement.pdf">'
                ),
                url=url,
            )
        if url.endswith("/problem/demo"):
            return FakeResponse(
                text='<a href="/problem/demo/data/statement.pdf">PDF</a>',
                url=url,
            )
        if url.endswith("/problem/demo/data/statement.pdf"):
            return FakeResponse(
                content=b"%PDF-1.7\nfixture",
                headers={"Content-Type": "application/pdf"},
                url=url,
            )
        if url.endswith("/problem/demo/test_data"):
            return FakeResponse(
                text=(
                    '<a href="/problem/demo/test_data/archive.zip">ZIP</a>'
                    '<input name="cases-0-order" value="1">'
                    '<select name="cases-0-type"><option value="C" selected>C</option></select>'
                    '<input name="cases-0-input_file" value="01.inp">'
                    '<input name="cases-0-output_file" value="01.out">'
                    '<input name="cases-0-points" value="100">'
                ),
                url=url,
            )
        if url.endswith("/problem/demo/test_data/archive.zip"):
            return FakeResponse(content=b"PK fixture", url=url)
        raise AssertionError(url)


class ProblemPdfTests(unittest.TestCase):
    def test_find_pdf_from_public_link_and_hidden_key(self):
        self.assertEqual(
            problem_pdf.find_problem_pdf_url(
                "https://hncode.edu.vn", "demo", '<a href="/media/demo.pdf">PDF</a>'
            ),
            "https://hncode.edu.vn/media/demo.pdf",
        )
        self.assertEqual(
            problem_pdf.find_problem_pdf_url(
                "https://hncode.edu.vn",
                "demo",
                "",
                '<input name="pdf_description" value="demo/statement.pdf">',
            ),
            "https://hncode.edu.vn/problem/demo/data/statement.pdf",
        )

    def test_download_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            path = problem_pdf.download_problem_pdf(
                DownloadSession(),
                "https://hncode.edu.vn",
                "demo",
                Path(temp),
                public_page='<a href="/problem/demo/data/statement.pdf">PDF</a>',
            )
            self.assertIsNotNone(path)
            self.assertTrue(path.read_bytes().startswith(b"%PDF"))

    def test_direct_upload_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "demo.pdf"
            pdf.write_bytes(b"%PDF-1.7\nfixture")
            session = DirectUploadSession()
            result = problem_pdf.upload_problem_pdf(
                session, "hncode", "https://hncode.edu.vn", "demo", pdf
            )
            self.assertEqual(result, "https://hncode.edu.vn/problem/demo/data/statement.pdf")
            self.assertEqual(len(session.posts), 3)
            self.assertEqual(session.posts[0][1]["json"]["upload_token"], "upload-token")
            self.assertIn("file", session.posts[1][1]["files"])

    def test_hnoj_upload_preserves_edit_form(self):
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "demo.pdf"
            pdf.write_bytes(b"%PDF-1.7\nfixture")
            session = HnojSession()
            problem_pdf.upload_problem_pdf(session, "hnoj", "https://hnoj.edu.vn", "demo", pdf)
            self.assertIn(("code", "demo"), session.post_kwargs["data"])
            self.assertIn("statement_file", session.post_kwargs["files"])

    def test_transfer_source_downloads_pdf_as_part_of_problem_info(self):
        with tempfile.TemporaryDirectory() as temp:
            info, _zip_path, cases, _zip_url = fetch_source_problem(
                SourceProblemSession(), "https://hncode.edu.vn", "demo", Path(temp)
            )
            self.assertEqual(info.description, "Đề bài được cung cấp bằng file PDF.")
            self.assertIsNotNone(info.pdf_path)
            self.assertTrue(info.pdf_path.read_bytes().startswith(b"%PDF"))
            self.assertEqual(len(cases), 1)


if __name__ == "__main__":
    unittest.main()
