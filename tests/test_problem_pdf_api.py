import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import web_app


def nested_test_zip() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("01.inp", "1 2\n")
        archive.writestr("01.out", "3\n")
    return stream.getvalue()


class ProblemPdfApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.temp.name)
        self.runtime_patch = patch.object(web_app, "RUNTIME", self.runtime)
        self.runtime_patch.start()
        web_app.prepared_single_uploads.clear()
        web_app.prepared_uploads.clear()
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()

    def tearDown(self):
        self.runtime_patch.stop()
        self.temp.cleanup()

    def test_prepare_single_upload_accepts_pdf_statement(self):
        payload = {
            "target": "hncode",
            "code": "pdfdemo",
            "name": "Bài PDF",
            "statement_text": "",
            "points": "100",
        }
        response = self.client.post(
            "/api/prepare-single-upload",
            data={
                "payload": json.dumps(payload),
                "statement_pdf": (io.BytesIO(b"%PDF-1.7\nfixture"), "statement.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        row = response.get_json()["rows"][0]
        self.assertEqual(row["statement_file"], "pdfdemo.pdf")
        self.assertTrue(row["upload_statement_default"])
        prepare_id = response.get_json()["prepare_id"]
        bundle = web_app.prepared_single_uploads[prepare_id]["bundles"]["pdfdemo"]
        self.assertEqual(bundle.pdf_statement.name, "pdfdemo.pdf")

    def test_prepare_multi_upload_accepts_pdf_only_problem(self):
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("pdfdemo.pdf", b"%PDF-1.7\nfixture")
            archive.writestr("pdfdemo.zip", nested_test_zip())
        package.seek(0)
        response = self.client.post(
            "/api/prepare-upload",
            data={
                "payload": json.dumps({"points": "100", "partial": True}),
                "zip_file": (package, "package.zip"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        row = response.get_json()["rows"][0]
        self.assertIn("pdfdemo.pdf", row["statement_file"])
        self.assertTrue(row["upload_statement_default"])
        self.assertEqual(row["test_count"], 1)


if __name__ == "__main__":
    unittest.main()
