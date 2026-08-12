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

    def test_parse_ai_json_repairs_latex_backslash_escapes(self):
        parsed = ai_service.parse_ai_json(
            r'{"code":"b","name":"B","statement_markdown":"B | b | 100 | math\n\nCho $1 \leq n \leq 10^5$.","tags":["math"]}'
        )

        self.assertIn(r"\leq", parsed["statement_markdown"])

    def test_parse_ai_json_repairs_latex_u_and_text_escapes(self):
        parsed = ai_service.parse_ai_json(
            r'{"code":"c","name":"C","statement_markdown":"C | c | 100 | math\n\nTính $a \underline{+} b$ và $x \text{ mod } y \geq 0$.","tags":["math"]}'
        )

        self.assertIn(r"\underline", parsed["statement_markdown"])
        self.assertIn(r"\text", parsed["statement_markdown"])
        self.assertIn(r"\geq", parsed["statement_markdown"])

    def test_ensure_statement_header_strips_fence_and_prepends_metadata(self):
        statement = ai_service.ensure_statement_header(
            "```markdown\n## Nội dung\n\nCho $n$.\n```",
            name="Chuyến đi siêu thị",
            code="chuyendisieuthip",
            points="100",
            tags=["math", "greedy"],
        )

        self.assertTrue(statement.startswith("Chuyến đi siêu thị | chuyendisieuthip | 100 | math, greedy"))
        self.assertNotIn("```", statement)

    def test_gemini_generate_falls_back_when_legacy_model_is_404(self):
        class FakeResponse:
            def __init__(self, ok: bool, status_code: int, text: str, data: dict | None = None):
                self.ok = ok
                self.status_code = status_code
                self.text = text
                self._data = data or {}

            def json(self):
                return self._data

        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            if "gemini-2.5-flash" in url:
                return FakeResponse(False, 404, '{"error":{"message":"This model models/gemini-2.5-flash is no longer available to new users","status":"NOT_FOUND"}}')
            return FakeResponse(
                True,
                200,
                "{}",
                {"candidates": [{"content": {"parts": [{"text": '{"code":"ok"}'}]}}]},
            )

        with patch.object(ai_service.requests, "post", side_effect=fake_post):
            text = ai_service.gemini_generate(api_key="fake", prompt="prompt", model="gemini-2.5-flash")

        self.assertEqual(text, '{"code":"ok"}')
        self.assertIn("gemini-2.5-flash", calls[0])
        self.assertIn("gemini-3.5-flash", calls[1])


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
        self.assertIn("statement_link", prepare_data["rows"][0])
        file_response = self.client.get(prepare_data["rows"][0]["statement_link"])
        self.assertEqual(file_response.status_code, 200)
        self.assertIn("Cho a b", file_response.get_data(as_text=True))
        file_response.close()
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
        self.assertIn("statement_link", data["rows"][0])

    def test_apply_normalize_uses_mocked_hncode_updates(self):
        prepare = self.client.post(
            "/api/ai/prepare-normalize",
            json={
                "source_mode": "file",
                "target": "hncode",
                "source_text": "Tổng hai số | tonghaiso | 100 | math\n\nCho $a,b$.",
                "problem_code": "tonghaiso",
                "problem_name": "Tổng hai số",
                "points": "100",
                "tags": "math",
            },
        )
        prepare_data = prepare.get_json()
        rows = prepare_data["rows"]
        rows[0].update(
            {
                "selected": True,
                "statement_markdown": "Tổng hai số | tonghaiso | 200 | math\n\nCho $a,b$.",
                "solution_markdown": "# Lời giải\n\nCộng hai số.",
                "points": "200",
            }
        )
        with (
            patch.object(web_app, "login_hncode", return_value=object()),
            patch.object(web_app, "update_hncode_statement_markdown", return_value="https://hncode.edu.vn/problem/tonghaiso/edit") as statement_update,
            patch.object(web_app, "update_hncode_problem_metadata", return_value="https://hncode.edu.vn/problem/tonghaiso/edit") as metadata_update,
            patch.object(web_app, "update_problem_solution_markdown", return_value="https://hncode.edu.vn/problem/tonghaiso/editorial") as solution_update,
        ):
            response = self.client.post(
                "/api/ai/apply-normalize",
                json={
                    "prepare_id": prepare_data["prepare_id"],
                    "target": "hncode",
                    "options": {"statement": True, "metadata": True, "solution": True},
                    "account": {"username": "hncode", "password": "secret"},
                    "rows": rows,
                },
            )
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["rows"][0]["status"], "✓ Đã cập nhật web")
        self.assertEqual(data["rows"][0]["link"], "https://hncode.edu.vn/problem/tonghaiso")
        statement_update.assert_called_once()
        metadata_update.assert_called_once()
        solution_update.assert_called_once()

    def test_hncode_snapshot_counts_test_cases_without_name_error(self):
        class FakeResponse:
            def __init__(self, text: str, ok: bool = True, status_code: int = 200):
                self.text = text
                self.ok = ok
                self.status_code = status_code
                self.url = "https://hncode.edu.vn/problem/chuyendisieuthip/edit"

        class FakeSession:
            def get(self, url: str, timeout: int = 30):
                if url.endswith("/edit"):
                    return FakeResponse(
                        """
                        <input name="code" value="chuyendisieuthip">
                        <input name="name" value="Chuyen di sieu thi">
                        <textarea name="description">Cho $n$.</textarea>
                        <input name="points" value="100">
                        <input type="checkbox" name="partial" checked>
                        <input name="time_limit" value="1.0">
                        <input name="memory_limit" value="1024">
                        <select name="memory_unit"><option value="MB" selected>MB</option></select>
                        <select name="types" multiple><option value="1" selected>math</option></select>
                        """
                    )
                if url.endswith("/test_data"):
                    return FakeResponse(
                        """
                        <input name="cases-0-order" value="1">
                        <input name="cases-0-input_file" value="01.inp">
                        <input name="cases-0-output_file" value="01.out">
                        <input name="cases-0-points" value="1">
                        <select name="cases-0-type"><option value="C" selected>C</option></select>
                        <input name="cases-1-order" value="2">
                        <input name="cases-1-input_file" value="02.inp">
                        <input name="cases-1-output_file" value="02.out">
                        <input name="cases-1-points" value="1">
                        <select name="cases-1-type"><option value="C" selected>C</option></select>
                        """
                    )
                if url.endswith("/edit/solutions"):
                    return FakeResponse('<textarea name="content"># Loi giai</textarea>')
                return FakeResponse("", False, 404)

        snapshot = web_app.hncode_problem_snapshot(FakeSession(), "chuyendisieuthip")

        self.assertEqual(snapshot["code"], "chuyendisieuthip")
        self.assertEqual(snapshot["test_count"], 2)
        self.assertIn("2 test", snapshot["test_summary"])

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
