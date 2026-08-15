import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import web_app


class FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200, url: str = "https://hncode.edu.vn/"):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.ok = 200 <= status_code < 400
        self.headers = {}


class FakeSession:
    def __init__(self, fixture: str):
        self.fixture = fixture

    def get(self, url, *args, **kwargs):
        url = str(url)
        if "/ranking" in url:
            return FakeResponse("", 404, url)
        if "/contest/" in url:
            return FakeResponse(self.fixture, 200, url)
        return FakeResponse("", 404, url)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        warnings.simplefilter("ignore", ResourceWarning)

    def setUp(self):
        self.client = web_app.app.test_client()

    def assert_standard_response_shape(self, data):
        for key in ["ok", "message", "rows", "log", "errors", "meta"]:
            self.assertIn(key, data)

    def test_index_loads_static_modules(self):
        response = self.client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for filename in ["api.js", "progress.js", "app.js", "upload.js", "transfer.js", "contest.js", "lesson.js", "misc.js"]:
            self.assertIn(f"/static/{filename}", html)

    def test_static_modules_load(self):
        for filename in ["api.js", "progress.js", "upload.js", "transfer.js", "contest.js", "lesson.js", "misc.js"]:
            response = self.client.get(f"/static/{filename}")
            self.assertEqual(response.status_code, 200, filename)
            self.assertGreater(len(response.get_data()), 20, filename)

    def test_prepare_upload_sample_uses_standard_response_shape(self):
        response = self.client.post(
            "/api/prepare-upload",
            json={
                "target": "hncode",
                "zip_path": "samples/bo_mau_1_bai_tonghaiso.zip",
                "time_limit": "1.0",
                "memory_limit": "1048576",
                "points": "100",
                "partial": True,
            },
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assert_standard_response_shape(data)
        self.assertIn("message", data)
        self.assertIn("rows", data)
        self.assertIn("log", data)
        self.assertIn("errors", data)
        self.assertIn("meta", data)
        self.assertTrue(data["prepare_id"])
        self.assertEqual(len(data["rows"]), 1)

    def test_hncode_tag_fallback_defaults_to_uncategorized_591(self):
        tags, warning = web_app.normalize_tags_for_target("", "hncode")

        self.assertEqual(tags, "Chưa phân loại")
        self.assertIn("591", warning)
        self.assertEqual(web_app.type_ids_from_tags(tags, "hncode"), ["591"])

        tags, warning = web_app.normalize_tags_for_target("tag khong co", "hncode")
        self.assertEqual(tags, "Chưa phân loại")
        self.assertIn("chưa nhận diện", warning)

        tags, warning = web_app.normalize_tags_for_target("implementation, math", "hncode")
        self.assertEqual(tags, "implementation, math")
        self.assertEqual(warning, "")

    def test_list_problem_codes_uses_fixture_without_live_login(self):
        fixture = (Path(__file__).parent / "fixtures" / "hncode_contest_new.html").read_text(encoding="utf-8")
        with patch.object(web_app, "login_hncode", return_value=FakeSession(fixture)):
            response = self.client.post(
                "/api/misc/list-problem-codes",
                json={
                    "site": "hncode",
                    "source_type": "contest",
                    "url": "https://hncode.edu.vn/contest/tht26_a",
                    "account": {"username": "fake", "password": "fake"},
                },
            )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assert_standard_response_shape(data)
        self.assertEqual([row["code"] for row in data["rows"]], ["new_square", "new_path"])
        self.assertEqual(data["codes_text"], "new_square\nnew_path")
        self.assertEqual(data["meta"]["count"], 2)

    def test_prioritized_api_errors_use_standard_shape_without_live_login(self):
        cases = [
            ("/api/prepare-transfer", {"source": "hnoj", "dest": "hncode", "codes": []}),
            ("/api/prepare-contest-transfer", {"source": "hnoj", "dest": "hncode", "codes": []}),
            ("/api/confirm-contest-transfer", {"source": "hnoj", "dest": "hncode", "prepare_id": "missing", "rows": []}),
            ("/api/confirm-contest-to-lesson", {"prepare_id": "missing", "rows": []}),
            ("/api/confirm-course-clone", {"prepare_id": "missing", "rows": []}),
            ("/api/confirm-hncode-grading", {"prepare_id": "missing", "rows": []}),
        ]
        for url, payload in cases:
            with self.subTest(url=url):
                response = self.client.post(url, json=payload)
                data = response.get_json()

                self.assertEqual(response.status_code, 400)
                self.assertFalse(data["ok"])
                self.assert_standard_response_shape(data)
                self.assertTrue(data["error"])

    def test_confirm_transfer_same_source_dest_keeps_legacy_200_with_standard_shape(self):
        response = self.client.post(
            "/api/confirm-transfer",
            json={
                "source": "hncode",
                "dest": "hncode",
                "rows": [{"selected": True, "code": "abc"}],
                "settings": {},
            },
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(data["ok"])
        self.assert_standard_response_shape(data)
        self.assertEqual(len(data["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
