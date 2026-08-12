import json
import re
import unittest
from pathlib import Path

from web_app import app


ROOT = Path(__file__).resolve().parents[1]


class UiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.index_html = self.client.get("/").get_data(as_text=True)

    def test_index_loads_all_static_modules(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        for script in (
            "api.js",
            "progress.js",
            "app.js",
            "upload.js",
            "transfer.js",
            "contest.js",
            "lesson.js",
            "misc.js",
        ):
            self.assertIn(f"/static/{script}", self.index_html)

    def test_js_get_element_by_id_references_exist_in_index(self):
        ids = set(re.findall(r'id=["\']([^"\']+)["\']', self.index_html))
        missing = []
        for js_path in sorted((ROOT / "static").glob("*.js")):
            text = js_path.read_text(encoding="utf-8")
            for match in re.finditer(r'document\.getElementById\(["\']([^"\']+)["\']\)', text):
                element_id = match.group(1)
                if element_id not in ids:
                    missing.append(f"{js_path.name}:{text.count(chr(10), 0, match.start()) + 1}:{element_id}")

        self.assertEqual(missing, [])

    def test_js_api_paths_exist_in_flask_routes(self):
        js = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "static").glob("*.js")))
        api_paths = sorted(set(re.findall(r'["\'](/api/[^"\']+)["\']', js)))
        rules = {str(rule) for rule in app.url_map.iter_rules()}

        missing = [path for path in api_paths if path not in rules]

        self.assertEqual(missing, [])

    def test_prepare_upload_sample_offline(self):
        sample = self.client.post("/api/sample/tonghaiso", json={}).get_json()
        response = self.client.post(
            "/api/prepare-upload",
            json={
                "target": "hncode",
                "zip_path": sample["zip_path"],
                "time_limit": "1.0",
                "memory_limit": "1048576",
                "points": "100",
                "tags": "",
                "partial": True,
            },
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertGreaterEqual(len(data["rows"]), 1)
        self.assertIn("prepare_id", data)

    def test_prepare_single_upload_offline(self):
        payload = {
            "target": "hncode",
            "code": "ui_smoke_tong",
            "name": "Tong hai so",
            "points": "100",
            "tags": "nhap xuat",
            "time_limit": "1.0",
            "memory_limit": "1024M",
            "partial": True,
            "statement_text": "Tong hai so | ui_smoke_tong\n\nCho a b, tinh tong.",
        }
        response = self.client.post(
            "/api/prepare-single-upload",
            data={"payload": json.dumps(payload)},
            content_type="multipart/form-data",
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["rows"][0]["code"], "ui_smoke_tong")
        self.assertIn("prepare_id", data)

    def test_prepare_quiz_offline(self):
        quiz_text = """
        Tieu de: Cau cong
        Loai: MC
        Noi dung:
        1 + 1 = ?
        Lua chon:
        A. 1
        B. 2
        Dap an: B
        """
        response = self.client.post("/api/prepare-quiz", json={"text": quiz_text})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["rows"]), 1)
        self.assertIn("prepare_id", data)


if __name__ == "__main__":
    unittest.main()
