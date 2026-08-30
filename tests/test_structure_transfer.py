import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import web_app


class FakeResponse:
    def __init__(
        self,
        text="",
        status_code=200,
        url="https://example.test/form",
        payload=None,
        headers=None,
        content=b"",
    ):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.ok = 200 <= status_code < 400
        self._payload = payload
        self.headers = headers or {}
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.posts = []

    def get(self, _url, **_kwargs):
        return self.response

    def post(self, url, data=None, **kwargs):
        self.posts.append((url, data, kwargs))
        return FakeResponse(url=url, payload={"success": True})


class StructureTransferTests(TestCase):
    def test_structure_content_uploads_source_image_and_uses_relative_links(self):
        class DestinationSession:
            cookies = {"csrftoken": "token"}

            def post(self, _url, **_kwargs):
                return FakeResponse(
                    payload={"success": True, "url": "https://lqdoj.edu.vn/media/copied.png"}
                )

        source = FakeSession(
            FakeResponse(
                headers={"Content-Type": "image/png"},
                content=b"png-bytes",
            )
        )
        content = (
            "![Ảnh](https://hncode.edu.vn/media/source.png) "
            "[Bài](https://hncode.edu.vn/problem/abc)"
        )

        migrated = web_app.migrate_structure_content(
            source, DestinationSession(), "hncode", "lqdoj", content, []
        )

        self.assertIn("![Ảnh](/media/copied.png)", migrated)
        self.assertIn("[Bài](/problem/abc)", migrated)
        self.assertNotIn("hncode.edu.vn", migrated)

    @patch("web_app.create_destination_course", return_value="122")
    def test_missing_destination_course_is_created(self, create_course):
        session = FakeSession(FakeResponse(status_code=404))

        course_id, created = web_app.ensure_destination_course(
            session,
            session,
            "lqdoj",
            "hncode",
            "cp-dong",
            {"name": "Rank Đồng", "about": ""},
            [],
        )

        self.assertEqual(course_id, "122")
        self.assertTrue(created)
        create_course.assert_called_once()

    def test_problem_links_are_rewritten_to_destination_codes(self):
        content = (
            "[A](/problem/source_code) "
            "[B](/contest/source/problems/source_code)"
        )
        rewritten = web_app.rewrite_internal_problem_links(
            content, {"source_code": "sourcecode"}
        )

        self.assertEqual(
            rewritten,
            "[A](/problem/sourcecode) [B](/problem/sourcecode)",
        )

    def test_structure_url_detects_lqdoj_and_reports_selection_mismatch(self):
        self.assertEqual(
            web_app.structure_target_from_url("https://lqdoj.edu.vn/course/cp-dong"),
            "lqdoj",
        )
        with self.assertRaisesRegex(RuntimeError, "LQDOJ.*HNCode"):
            web_app.validate_structure_target_url(
                "https://lqdoj.edu.vn/course/cp-dong", "hncode", "Course đích"
            )

    def test_course_prepare_rejects_wrong_selected_site_before_login(self):
        response = web_app.app.test_client().post(
            "/api/prepare-course-clone",
            json={
                "source": "hncode",
                "dest": "hncode",
                "source_url": "https://hncode.edu.vn/course/source",
                "dest_url": "https://lqdoj.edu.vn/course/cp-dong",
                "include_lessons": True,
                "include_contests": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("LQDOJ", response.get_json()["error"])
        self.assertIn("HNCode", response.get_json()["error"])

    def test_problem_copy_report_continues_after_one_failure(self):
        log = []

        def copier(code, _problem):
            if code == "bad":
                raise RuntimeError("test archive is invalid")
            return code + "_dest", "42"

        refs, rows = web_app.copy_problem_refs_with_report(
            [{"code": "first"}, {"code": "bad"}, {"code": "last"}], copier, log
        )

        self.assertEqual([row["code"] for row in refs], ["first_dest", "last_dest"])
        self.assertEqual(len(rows), 3)
        self.assertIn("test archive is invalid", rows[1]["error"])
        self.assertTrue(rows[2]["status"].startswith("✓"))
        self.assertIn("Tiếp tục bài kế tiếp", "\n".join(log))

    def test_course_contest_parser_reads_relation_points_and_order(self):
        page = """
        <ul>
          <li class="sortable-item" data-id="91">
            <span class="item-order">2.</span>
            <a href="/contest/c_one">Contest One</a>
            <input class="inline-points-edit" data-cc-id="91" value="250">
          </li>
        </ul>
        """
        rows = web_app.hncode_course_contests(
            FakeSession(FakeResponse(page)), "course_one", "hncode"
        )

        self.assertEqual(rows[0]["relation_id"], "91")
        self.assertEqual(rows[0]["key"], "c_one")
        self.assertEqual(rows[0]["points"], "250")
        self.assertEqual(rows[0]["order"], "2")

    def test_course_contest_relation_updates_points_and_order(self):
        page = """
        <form><input name="csrfmiddlewaretoken" value="token"></form>
        <ul>
          <li class="sortable-item" data-id="11"><span class="item-order">1.</span><a href="/contest/a">A</a><input class="inline-points-edit" value="100"></li>
          <li class="sortable-item" data-id="22"><span class="item-order">2.</span><a href="/contest/b">B</a><input class="inline-points-edit" value="100"></li>
        </ul>
        """
        session = FakeSession(FakeResponse(page))

        web_app.sync_course_contest_relation(session, "course", "hncode", "b", "350", "1")

        self.assertEqual(session.posts[0][1]["action"], "update_points")
        self.assertEqual(session.posts[0][1]["cc_id"], "22")
        self.assertEqual(session.posts[0][1]["points"], "350")
        self.assertEqual(session.posts[1][1]["action"], "reorder_contests")
        self.assertEqual(json.loads(session.posts[1][1]["order_data"]), ["22", "11"])

    @patch("web_app.copy_hncode_contest_to_lesson")
    @patch("web_app.update_lesson_metadata")
    @patch("web_app.find_hncode_course_lesson_url", return_value="https://lqdoj.edu.vn/course/dest/lesson/88")
    @patch("web_app.ensure_problem_for_copy")
    @patch("web_app.admin_problem_code_name_by_id")
    @patch("web_app.lesson_problem_rows_from_page")
    def test_cross_site_lesson_keeps_metadata_and_continues_problem_errors(
        self,
        problem_rows,
        code_by_id,
        ensure_problem,
        _find_lesson,
        update_metadata,
        copy_items,
    ):
        source_html = """
        <form>
          <input name="title" value="Lesson sample">
          <input name="points" value="120">
          <input name="order" value="3">
          <textarea name="content">![image](/media/sample.png)</textarea>
        </form>
        """
        problem_rows.return_value = [
            {"problem": "1", "score": "40"},
            {"problem": "2", "score": "60"},
        ]
        code_by_id.side_effect = [("bad", "Bad"), ("good", "Good")]
        ensure_problem.side_effect = [RuntimeError("bad tests"), ("good", "202")]
        report = []

        link = web_app.clone_course_lesson_between_sites(
            FakeSession(FakeResponse(source_html)),
            object(),
            "hncode",
            "lqdoj",
            "source",
            "7",
            "Fallback",
            "dest",
            Path("runtime"),
            [],
            report,
        )

        self.assertEqual(link, "https://lqdoj.edu.vn/course/dest/lesson/88")
        self.assertEqual(len(report), 2)
        self.assertEqual(report[0]["status"], "✗ Lỗi")
        self.assertTrue(report[1]["status"].startswith("✓"))
        self.assertIn("/media/sample.png", update_metadata.call_args.args[6])
        self.assertNotIn("hncode.edu.vn", update_metadata.call_args.args[6])
        copied_refs = copy_items.call_args.args[3]
        self.assertEqual([row["code"] for row in copied_refs], ["good"])

    @patch("web_app.clone_hncode_lesson_native")
    @patch("web_app.sync_course_metadata", return_value=("https://hncode.edu.vn/admin/course/1", []))
    @patch("web_app.login_target_account", return_value=object())
    def test_course_confirm_continues_after_one_lesson_failure(
        self, _login, _sync_metadata, clone_lesson
    ):
        prepare_id = "f" * 32
        web_app.prepared_course_clones[prepare_id] = {
            "source_slug": "source",
            "dest_slug": "dest",
            "source": "hncode",
            "dest": "hncode",
            "dest_course_id": "9",
            "rows": [
                {"kind": "lesson", "key": "1", "title": "Broken", "selected": True},
                {"kind": "lesson", "key": "2", "title": "Working", "selected": True},
            ],
        }
        clone_lesson.side_effect = [
            RuntimeError("cannot save lesson"),
            "https://hncode.edu.vn/course/dest/lesson/22",
        ]
        try:
            response = web_app.app.test_client().post(
                "/api/confirm-course-clone",
                json={
                    "prepare_id": prepare_id,
                    "source_account": {},
                    "dest_account": {},
                    "rows": [
                        {"kind": "lesson", "key": "1", "selected": True},
                        {"kind": "lesson", "key": "2", "selected": True},
                    ],
                },
            )
        finally:
            web_app.prepared_course_clones.pop(prepare_id, None)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["rows"][0]["status"], "✗ Lỗi")
        self.assertEqual(data["rows"][1]["status"], "✓ Đã clone")
        self.assertEqual(clone_lesson.call_count, 2)

    @patch("web_app.progress_finish")
    @patch("web_app.progress_update")
    @patch("web_app.create_contest", return_value="https://hncode.edu.vn/admin/judge/contest/2/change/")
    @patch(
        "web_app.copy_problem_refs_with_report",
        return_value=(
            [{"code": "good", "id": "10", "points": "100", "order": "0"}],
            [{"source_code": "good", "code": "good", "status": "✓ Đã sao chép/dùng lại"}],
        ),
    )
    @patch("web_app.login_target_account", return_value=object())
    @patch("web_app.load_prepared_contest_transfer")
    def test_contest_confirm_continues_after_one_contest_failure(
        self,
        load_state,
        _login,
        _copy_problems,
        create_contest,
        _progress_update,
        _progress_finish,
    ):
        load_state.return_value = {
            "root": Path("runtime"),
            "items": {
                "working": {
                    "key": "working",
                    "name": "Working",
                    "start_time": "",
                    "end_time": "",
                    "problems": [{"code": "good"}],
                }
            },
        }
        response = web_app.app.test_client().post(
            "/api/confirm-contest-transfer",
            json={
                "prepare_id": "e" * 32,
                "progress_id": "progress",
                "source": "hncode",
                "dest": "hncode",
                "source_account": {},
                "dest_account": {},
                "settings": {},
                "rows": [
                    {"original_key": "broken", "key": "broken", "selected": True},
                    {
                        "original_key": "working",
                        "key": "working",
                        "selected": True,
                        "problems": [{"source_code": "good", "code": "good", "selected": True}],
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["rows"][0]["status"], "✗ Lỗi")
        self.assertIn("Chưa đọc được dữ liệu", data["rows"][0]["error"])
        self.assertEqual(data["rows"][1]["status"], "✓ Thành công")
        create_contest.assert_called_once()

    @patch("web_app.public_contest_problem_codes", return_value=["sample"])
    @patch("web_app.admin_contest_change_url", return_value="https://hncode.edu.vn/admin/judge/contest/1/change/")
    def test_contest_metadata_includes_description_and_setup(self, _change_url, _codes):
        page = """
        <form>
          <input name="key" value="contest_one"><input name="name" value="Contest One">
          <textarea name="description">![diagram](/media/diagram.png)</textarea>
          <input name="start_time_0" value="2026-09-01"><input name="start_time_1" value="08:00:00">
          <input name="end_time_0" value="2026-09-01"><input name="end_time_1" value="10:00:00">
          <select name="format_name"><option value="vnoj" selected>VNOJ</option></select>
          <select name="scoreboard_visibility"><option value="H" selected>Hidden</option></select>
          <select name="view_contest_scoreboard"><option value="A" selected>All</option></select>
          <input name="points_precision" value="2"><input name="rate_limit" value="15">
          <input name="is_visible" type="checkbox" checked><input name="is_strict" type="checkbox" checked>
          <input name="strict_violation_limit" value="3"><input name="strict_grace_seconds" value="10">
          <input name="contest_problems-TOTAL_FORMS" value="1">
          <select name="contest_problems-0-problem"><option value="55" selected>Sample</option></select>
          <input name="contest_problems-0-points" value="75">
          <input name="contest_problems-0-order" value="4">
          <input name="contest_problems-0-partial" type="checkbox" checked>
        </form>
        """
        info = web_app.fetch_contest_info(
            FakeSession(FakeResponse(page)), "https://hncode.edu.vn", "contest_one"
        )

        self.assertEqual(info["rate_limit"], "15")
        self.assertEqual(info["view_contest_scoreboard"], "A")
        self.assertTrue(info["is_strict"])
        self.assertEqual(info["strict_violation_limit"], "3")
        self.assertEqual(info["problems"][0]["points"], "75")
        self.assertIn("/media/diagram.png", info["description"])
