import json
import unittest
from unittest.mock import patch

import web_app
from services import ai_assistant as ai_service


class AiAssistantServiceTests(unittest.TestCase):
    def test_build_prompt_contains_reference_snapshot_and_options(self):
        prompt = ai_service.build_hncode_normalization_prompt(
            "Quy tắc chuẩn hóa",
            {
                "code": "tonghaiso",
                "name": "Tổng hai số",
                "statement": "Cho $a,b$.",
                "points": "800",
                "partial": True,
                "time_limit": "1.0",
                "memory_limit": "1024",
                "memory_unit": "MB",
                "test_summary": "10 test",
                "solution": "",
            },
            {"target": "hncode", "statement": True, "metadata": True, "solution": True, "test_review": True},
        )

        self.assertIn("tonghaiso", prompt)
        self.assertIn("Quy tắc chuẩn hóa", prompt)
        self.assertIn("solution_markdown", prompt)
        self.assertIn("$...$", prompt)

    def test_validate_statement_markdown_for_hncode_and_hnoj(self):
        hncode = "Tổng hai số | tonghaiso | 800 | implementation\n\nCho $a,b$.\n"
        hnoj = "Tổng hai số | tonghaiso | 800 | implementation\n\nCho ~a,b~.\n"

        _checks, hncode_meta = ai_service.validate_statement_markdown(hncode, "hncode")
        _checks, hnoj_meta = ai_service.validate_statement_markdown(hnoj, "hnoj")

        self.assertTrue(hncode_meta["valid"])
        self.assertTrue(hnoj_meta["valid"])
        self.assertEqual(hncode_meta["code"], "tonghaiso")

    def test_parse_ai_json_accepts_fenced_json_and_string_tags(self):
        parsed = ai_service.parse_ai_json(
            '```json\n{"code":"a","name":"A","statement_markdown":"A | a\\n\\nBody","tags":"math, dp","issues":"none"}\n```'
        )

        self.assertEqual(parsed["tags"], ["math", "dp"])
        self.assertEqual(parsed["issues"], [])


class AiAssistantApiTests(unittest.TestCase):
    def setUp(self):
        self.client = web_app.app.test_client()

    def test_prepare_file_text(self):
        response = self.client.post(
            "/api/ai/prepare-file",
            data={"source_file": (self._bytes("Tổng hai số | tonghaiso\n\nCho a b."), "de.md")},
            content_type="multipart/form-data",
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertIn("Cho a b", data["source_text"])
        self.assertIn("file_base64", data)

    def test_prepare_and_normalize_file_with_mocked_gemini(self):
        prepare = self.client.post(
            "/api/ai/prepare-normalize",
            json={
                "source_mode": "file",
                "target": "hncode",
                "source_text": "Tổng hai số | tonghaiso\n\nCho a b.",
                "problem_code": "tonghaiso",
                "problem_name": "Tổng hai số",
                "points": "800",
                "tags": "implementation, math",
            },
        )
        prepare_data = prepare.get_json()
        fake_ai = json.dumps(
            {
                "code": "tonghaiso",
                "name": "Tổng hai số",
                "statement_markdown": "Tổng hai số | tonghaiso | 800 | implementation, math\n\nCho $a,b$.",
                "points": 800,
                "tags": ["implementation", "math"],
                "allows_partial_points": True,
                "memory_limit_mb": 1024,
                "allowed_languages": ["C++17", "C++20", "Python 3", "Pypy3"],
                "solution_markdown": "",
                "test_review": "Cần 10 test.",
                "issues": [],
                "confidence": "high",
            }
        )
        with patch.object(web_app.ai_service, "gemini_generate", return_value=fake_ai):
            response = self.client.post(
                "/api/ai/normalize",
                json={
                    "prepare_id": prepare_data["prepare_id"],
                    "api_key": "fake-key",
                    "model": "gemini-2.5-flash",
                    "options": {"target": "hncode", "statement": True, "metadata": True, "solution": False, "test_review": True},
                    "rows": prepare_data["rows"],
                },
            )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["rows"][0]["status"], "✓ Đã chuẩn hóa")
        self.assertIn("$a,b$", data["rows"][0]["statement_markdown"])

    def test_validate_statement_endpoint(self):
        response = self.client.post(
            "/api/ai/validate-statement",
            json={"target": "hncode", "markdown": "Bài | bai | 100 | math\n\nCho $n$."},
        )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["meta"]["valid"])

    @staticmethod
    def _bytes(text: str):
        import io

        return io.BytesIO(text.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
