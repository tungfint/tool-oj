import shutil
import unittest
from unittest.mock import patch

import web_app


class FakeResponse:
    ok = True
    status_code = 200
    text = "<form></form>"


class FakeSession:
    def get(self, _url, **_kwargs):
        return FakeResponse()


class LessonCreateTests(unittest.TestCase):
    def test_parse_problem_codes_and_links_keeps_order(self):
        value = """
        1. first_problem
        https://hncode.edu.vn/problem/second_problem
        https://hncode.edu.vn/contest/demo/problems/third_problem
        first_problem
        """

        self.assertEqual(
            web_app.parse_hncode_problem_inputs(value),
            ["first_problem", "second_problem", "third_problem"],
        )

    def test_build_rows_marks_existing_and_missing_problems(self):
        resolved = {
            "new_problem": ("201", "Bài mới"),
            "old_problem": ("101", "Bài cũ"),
            "missing_problem": ("", "missing_problem"),
        }

        rows = web_app.build_lesson_problem_list_rows(
            ["new_problem", "old_problem", "missing_problem"],
            default_score="80",
            existing_problem_ids={"101"},
            resolve_problem=lambda code: resolved[code],
        )

        self.assertTrue(rows[0]["selected"])
        self.assertEqual(rows[0]["score"], "80")
        self.assertEqual(rows[1]["status"], "Đã có trong Lesson")
        self.assertFalse(rows[1]["selected"])
        self.assertIn("Không tìm thấy", rows[2]["status"])

    @patch("web_app.admin_problem_code_name_by_id")
    @patch("web_app.admin_problem_id")
    @patch("web_app.lesson_problem_rows_from_page", return_value=[{"problem": "101"}])
    @patch("web_app.login_target_account", return_value=FakeSession())
    def test_prepare_and_confirm_lesson_from_list(
        self,
        _login,
        _lesson_rows,
        admin_problem_id,
        admin_problem_name,
    ):
        ids = {"new_problem": "201", "old_problem": "101"}
        names = {"201": ("new_problem", "Bài mới"), "101": ("old_problem", "Bài cũ")}
        admin_problem_id.side_effect = lambda _session, _base, code: ids.get(code, "")
        admin_problem_name.side_effect = lambda _session, _base, problem_id: names[problem_id]
        client = web_app.app.test_client()

        prepared_response = client.post(
            "/api/prepare-lesson-from-list",
            json={
                "lesson_url": "https://hncode.edu.vn/course/demo/lesson/3123",
                "problems": "new_problem\nold_problem\nmissing_problem",
                "default_score": "70",
                "account": {},
            },
        )
        prepared = prepared_response.get_json()
        prepare_id = prepared["prepare_id"]
        self.addCleanup(
            shutil.rmtree,
            web_app.RUNTIME / f"lesson_update_{prepare_id}",
            True,
        )

        self.assertEqual(prepared_response.status_code, 200)
        self.assertTrue(prepared["ok"])
        self.assertTrue(prepared["can_add"])
        self.assertEqual(prepared["rows"][0]["score"], "70")
        self.assertEqual(prepared["rows"][1]["status"], "Đã có trong Lesson")
        self.assertIn("Không tìm thấy", prepared["rows"][2]["status"])

        web_app.prepared_lesson_updates.pop(prepare_id, None)
        with patch(
            "web_app.copy_hncode_contest_to_lesson",
            return_value="https://hncode.edu.vn/course/demo/lesson/3123",
        ):
            confirmed_response = client.post(
                "/api/confirm-lesson-from-list",
                json={
                    "prepare_id": prepare_id,
                    "account": {},
                    "rows": [
                        {"code": "new_problem", "selected": True, "score": "60"},
                        {"code": "old_problem", "selected": False, "score": "70"},
                        {"code": "missing_problem", "selected": False, "score": "70"},
                    ],
                },
            )

        confirmed = confirmed_response.get_json()
        self.assertEqual(confirmed_response.status_code, 200)
        self.assertTrue(confirmed["ok"])
        self.assertEqual(confirmed["rows"][0]["status"], "✓ Đã thêm")
        self.assertEqual(confirmed["rows"][0]["score"], "60")
        self.assertEqual(confirmed["rows"][0]["link"], confirmed["link"])


if __name__ == "__main__":
    unittest.main()
