import unittest
from unittest.mock import patch

import web_app
from services import lesson as lesson_service


LESSON_EDIT_HTML = """
<html><body>
<form>
  <input type="hidden" name="problems_3123-TOTAL_FORMS" value="1">
  <input type="hidden" name="problems_3123-INITIAL_FORMS" value="1">
  <input type="hidden" name="problems_3123-0-id" value="10">
  <input type="hidden" name="problems_3123-0-lesson" value="3123">
  <select name="problems_3123-0-problem"><option value="101" selected>old_problem</option></select>
  <input name="problems_3123-0-score" value="50">
  <input name="problems_3123-0-order" value="1">
</form>
</body></html>
"""


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.url = "https://hncode.edu.vn/course/demo/edit_lessons_new/3123"
        self.headers = {}


class FakeSession:
    def get(self, url, *args, **kwargs):
        return FakeResponse(LESSON_EDIT_HTML)


class ContestLessonTests(unittest.TestCase):
    def test_parse_lesson_problem_rows(self):
        rows = lesson_service.parse_lesson_problem_rows(LESSON_EDIT_HTML, "3123")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["problem"], "101")
        self.assertEqual(rows[0]["score"], "50")

    def test_build_contest_to_lesson_rows(self):
        contest_rows = [
            {"code": "abc_one", "title": "ABC One", "points": "100", "order": 1},
            {"code": "abc_two", "title": "ABC Two", "points": "80", "order": 2},
            {"code": "abc_old", "title": "ABC Old", "points": "60", "order": 3},
        ]
        ids = {"abc_one": "201", "abc_old": "101"}

        rows = lesson_service.build_contest_to_lesson_rows(
            contest_rows,
            source="hncode",
            existing_problem_ids={"101"},
            normalize_problem_code=lambda code, target: code,
            admin_problem_id=lambda code: ids.get(code, ""),
        )

        self.assertEqual(rows[0]["status"], "✓ Sẵn sàng")
        self.assertTrue(rows[0]["selected"])
        self.assertIn("Không tìm thấy", rows[1]["status"])
        self.assertFalse(rows[1]["selected"])
        self.assertEqual(rows[2]["status"], "Đã có trong lesson")
        self.assertFalse(rows[2]["selected"])

    def test_build_problem_list_rows(self):
        resolved = {
            "new_problem": ("201", "Bài mới"),
            "old_problem": ("101", "Bài đã có"),
            "missing_problem": ("", "missing_problem"),
        }

        rows = lesson_service.build_problem_list_rows(
            ["new_problem", "old_problem", "missing_problem"],
            default_score="80",
            existing_problem_ids={"101"},
            resolve_problem=lambda code: resolved[code],
        )

        self.assertEqual([row["index"] for row in rows], [1, 2, 3])
        self.assertEqual(rows[0]["title"], "Bài mới")
        self.assertEqual(rows[0]["score"], "80")
        self.assertTrue(rows[0]["selected"])
        self.assertEqual(rows[1]["status"], "Đã có trong lesson")
        self.assertFalse(rows[1]["selected"])
        self.assertIn("Không tìm thấy", rows[2]["status"])
        self.assertFalse(rows[2]["selected"])

    def test_merge_requested_lesson_copy_rows(self):
        saved = [
            {"code": "a", "score": "100", "problem_id": "1", "selected": True, "status": "✓ Sẵn sàng"},
            {"code": "b", "score": "80", "problem_id": "", "selected": True, "status": "Thiếu trên HNCode, sẽ chuyển khi xác nhận"},
        ]
        requested = [
            {"code": "a", "score": "70", "selected": True},
            {"code": "b", "score": "60", "selected": True},
        ]

        rows, selected = lesson_service.merge_requested_lesson_copy_rows(saved, requested)

        self.assertEqual(rows[0]["score"], "70")
        self.assertEqual(rows[0]["status"], "Đang thêm...")
        self.assertEqual(rows[1]["status"], "Cần chuyển/tìm problem_id")
        self.assertEqual([row["code"] for row in selected], ["a"])

    def test_prepare_contest_to_lesson_api_with_mock_session(self):
        contest_rows = [
            {"code": "abc_one", "title": "ABC One", "points": "100", "order": 1},
            {"code": "abc_old", "title": "ABC Old", "points": "50", "order": 2},
        ]

        def fake_admin_problem_id(_session, _base_url, code):
            return {"abc_one": "201", "abc_old": "101"}.get(code, "")

        with patch.object(web_app, "login_hncode", return_value=FakeSession()), \
             patch.object(web_app, "hncode_contest_problem_rows", return_value=contest_rows), \
             patch.object(web_app, "admin_problem_id", side_effect=fake_admin_problem_id):
            response = web_app.app.test_client().post(
                "/api/prepare-contest-to-lesson",
                json={
                    "source": "hncode",
                    "contest_url": "https://hncode.edu.vn/contest/demo",
                    "lesson_url": "https://hncode.edu.vn/course/demo/lesson/3123",
                    "account": {"username": "fake", "password": "fake"},
                    "source_account": {"username": "fake", "password": "fake"},
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        for key in ["message", "rows", "log", "errors", "meta"]:
            self.assertIn(key, data)
        self.assertTrue(data["can_copy"])
        self.assertEqual(data["rows"][0]["status"], "✓ Sẵn sàng")
        self.assertEqual(data["rows"][1]["status"], "Đã có trong lesson")

    def test_prepare_lesson_from_problem_list_api_with_mock_session(self):
        ids = {"new_problem": "201", "old_problem": "101"}
        names = {"201": ("new_problem", "Bài mới"), "101": ("old_problem", "Bài cũ")}

        with patch.object(web_app, "login_hncode", return_value=FakeSession()), \
             patch.object(web_app, "admin_problem_id", side_effect=lambda _session, _base, code: ids.get(code, "")), \
             patch.object(web_app, "admin_problem_code_name_by_id", side_effect=lambda _session, _base, problem_id: names.get(problem_id, ("", ""))):
            response = web_app.app.test_client().post(
                "/api/prepare-lesson-from-list",
                json={
                    "lesson_url": "https://hncode.edu.vn/course/demo/lesson/3123",
                    "problems": "https://hncode.edu.vn/problem/new_problem\nold_problem\nmissing_problem",
                    "default_score": "70",
                    "account": {"username": "fake", "password": "fake"},
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["can_add"])
        self.assertEqual([row["code"] for row in data["rows"]], ["new_problem", "old_problem", "missing_problem"])
        self.assertEqual(data["rows"][0]["score"], "70")
        self.assertEqual(data["rows"][1]["status"], "Đã có trong lesson")
        self.assertIn("Không tìm thấy", data["rows"][2]["status"])

    def test_confirm_lesson_from_problem_list_api_without_live_admin(self):
        ids = {"new_problem": "201"}
        client = web_app.app.test_client()
        with patch.object(web_app, "login_hncode", return_value=FakeSession()), \
             patch.object(web_app, "admin_problem_id", side_effect=lambda _session, _base, code: ids.get(code, "")), \
             patch.object(web_app, "admin_problem_code_name_by_id", return_value=("new_problem", "Bài mới")):
            prepared = client.post(
                "/api/prepare-lesson-from-list",
                json={
                    "lesson_url": "https://hncode.edu.vn/course/demo/lesson/3123",
                    "problems": "new_problem",
                    "default_score": "60",
                    "account": {"username": "fake", "password": "fake"},
                },
            ).get_json()

        with patch.object(web_app, "login_hncode", return_value=FakeSession()), \
             patch.object(web_app, "copy_hncode_contest_to_lesson", return_value="https://hncode.edu.vn/course/demo/lesson/3123"):
            response = client.post(
                "/api/confirm-lesson-from-list",
                json={
                    "prepare_id": prepared["prepare_id"],
                    "account": {"username": "fake", "password": "fake"},
                    "rows": [{"code": "new_problem", "selected": True, "score": "60"}],
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["rows"][0]["status"], "✓ Đã thêm")
        self.assertEqual(data["rows"][0]["score"], "60")
        self.assertEqual(data["rows"][0]["link"], "https://hncode.edu.vn/course/demo/lesson/3123")


if __name__ == "__main__":
    unittest.main()
