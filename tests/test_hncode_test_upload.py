import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import requests

from transfer_tinhoctre_to_hncode import (
    hncode_zip_upload_timeout,
    upload_hncode_zip_with_retry,
)


class _UploadSession:
    def __init__(self):
        self.calls = []

    def post(self, _endpoint, **kwargs):
        file_handle = kwargs["files"]["qqfile"][1]
        content = file_handle.read()
        self.calls.append(
            {
                "content": content,
                "timeout": kwargs["timeout"],
                "uuid": kwargs["data"]["qquuid"],
            }
        )
        if len(self.calls) == 1:
            raise requests.Timeout("simulated slow upload")
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"success": true}'
        return response


class HncodeTestUploadTests(TestCase):
    def test_retry_reopens_zip_and_uses_long_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "tests.zip"
            payload = b"test-data" * 1000
            zip_path.write_bytes(payload)
            session = _UploadSession()

            with patch("transfer_tinhoctre_to_hncode.time.sleep"):
                response = upload_hncode_zip_with_retry(
                    session,
                    "https://hncode.edu.vn/problem/demo/test_data/upload",
                    "https://hncode.edu.vn/problem/demo/test_data",
                    "csrf",
                    zip_path,
                    "demo",
                )

            self.assertTrue(response.ok)
            self.assertEqual(len(session.calls), 2)
            self.assertEqual(session.calls[0]["content"], payload)
            self.assertEqual(session.calls[1]["content"], payload)
            self.assertEqual(session.calls[0]["uuid"], session.calls[1]["uuid"])
            self.assertEqual(session.calls[0]["timeout"], 600)

    def test_large_zip_gets_dynamic_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "large.zip"
            zip_path.write_bytes(b"")
            with patch.object(Path, "stat") as stat:
                stat.return_value.st_size = 80 * 1024 * 1024
                self.assertGreater(hncode_zip_upload_timeout(zip_path), 600)
