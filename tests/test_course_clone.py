import unittest
from pathlib import Path
from unittest.mock import patch

import web_app
from services import course as course_service


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200, url: str = "https://hncode.edu.vn/"):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.ok = 200 <= status_code < 400
        self.headers = {}


class FakeSession:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    def get(self, url, *args, **kwargs):
        url = str(url)
        if url.endswith("/edit_lessons"):
            slug = url.rstrip("/").split("/")[-2]
            return FakeResponse(self.pages[f"{slug}:lessons"], 200, url)
        if url.endswith("/contests"):
            slug = url.rstrip("/").split("/")[-2]
            return FakeResponse(self.pages[f"{slug}:contests"], 200, url)
        return FakeResponse("", 404, url)


class CourseCloneTests(unittest.TestCase):
    def test_parse_course_lessons_from_html(self):
        html = (FIXTURE_DIR / "hncode_course_lessons.html").read_text(encoding="utf-8")

        rows = course_service.parse_course_lessons_from_html(html)

        self.assertEqual([row["key"] for row in rows], ["926", "927"])
        self.assertEqual(rows[0]["title"], "Nhập xuất cơ bản")
        self.assertEqual(rows[1]["order"], "2")
        self.assertEqual(rows[1]["points"], "80")

    def test_parse_course_contests_from_html(self):
        html = (FIXTURE_DIR / "hncode_course_contests.html").read_text(encoding="utf-8")

        rows = course_service.parse_course_contests_from_html(html)

        self.assertEqual([row["key"] for row in rows], ["ccb_kiemtratonghop_01", "ccb_kiemtratonghop_02"])
        self.assertEqual(rows[0]["title"], "Kiểm tra tổng hợp 01")
        self.assertEqual(rows[0]["points"], "100")

    def test_default_clone_contest_key(self):
        self.assertEqual(
            course_service.default_clone_contest_key("ccb_kiemtra", "ngs_cpp_cb_01"),
            "ccb_kiemtra_ngs_cpp_cb_01",
        )
        self.assertEqual(course_service.default_clone_contest_key("ccb_kiemtra", "dest", "v2"), "ccb_kiemtra_v2")
        self.assertEqual(course_service.default_clone_contest_key("ccb_kiemtra", "dest", "_v2"), "ccb_kiemtra_v2")
        self.assertEqual(course_service.default_clone_contest_key("ABC.Kiem Tra", "dest", ""), "abc_kiem_tra_dest")

    def test_build_course_clone_rows(self):
        source_lessons = [
            {"kind": "lesson", "key": "926", "title": "Nhập xuất cơ bản", "order": "1", "points": "100"},
            {"kind": "lesson", "key": "927", "title": "Biến và kiểu dữ liệu", "order": "2", "points": "80"},
        ]
        source_contests = [
            {"kind": "contest", "key": "ccb_ready", "title": "Ready", "order": "1", "points": "100"},
            {"kind": "contest", "key": "ccb_exists", "title": "Exists", "order": "2", "points": "90"},
            {"kind": "contest", "key": "ccb_global", "title": "Global", "order": "3", "points": "80"},
        ]
        dest_lessons = [{"kind": "lesson", "key": "3000", "title": "Nhập xuất cơ bản", "order": "1", "points": "100"}]
        dest_contests = [{"kind": "contest", "key": "ccb_exists_dest", "title": "Exists", "order": "1", "points": "90"}]

        rows, logs = course_service.build_course_clone_rows(
            source_lessons,
            source_contests,
            dest_lessons,
            dest_contests,
            "dest",
            contest_exists=lambda key: key == "ccb_global_dest",
        )

        by_key = {row["key"]: row for row in rows}
        self.assertFalse(by_key["926"]["selected"])
        self.assertEqual(by_key["926"]["status"], "Đã có lesson cùng tên ở đích")
        self.assertTrue(by_key["927"]["selected"])
        self.assertTrue(by_key["ccb_ready"]["selected"])
        self.assertEqual(by_key["ccb_ready"]["new_key"], "ccb_ready_dest")
        self.assertEqual(by_key["ccb_exists"]["status"], "Đã có contest đích trong course")
        self.assertEqual(by_key["ccb_global"]["status"], "Mã contest đích đã tồn tại trên HNCode")
        self.assertGreaterEqual(len(logs), 5)

    def test_prepare_course_clone_api_with_mock_session(self):
        lessons = (FIXTURE_DIR / "hncode_course_lessons.html").read_text(encoding="utf-8")
        contests = (FIXTURE_DIR / "hncode_course_contests.html").read_text(encoding="utf-8")
        empty_lessons = "<html><body><ul></ul></body></html>"
        empty_contests = "<html><body><ul></ul></body></html>"
        session = FakeSession(
            {
                "source:lessons": lessons,
                "source:contests": contests,
                "dest:lessons": empty_lessons,
                "dest:contests": empty_contests,
            }
        )

        with patch.object(web_app, "login_hncode", return_value=session), \
             patch.object(web_app, "hncode_course_admin_id", return_value="123"), \
             patch.object(web_app, "admin_contest_change_url", return_value=None):
            response = web_app.app.test_client().post(
                "/api/prepare-course-clone",
                json={
                    "source_url": "https://hncode.edu.vn/course/source",
                    "dest_url": "https://hncode.edu.vn/course/dest",
                    "contest_suffix": "",
                    "include_lessons": True,
                    "include_contests": True,
                    "account": {"username": "fake", "password": "fake"},
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["can_clone"])
        self.assertEqual(len(data["rows"]), 4)
        self.assertEqual(data["rows"][2]["new_key"], "ccb_kiemtratonghop_01_dest")


if __name__ == "__main__":
    unittest.main()
