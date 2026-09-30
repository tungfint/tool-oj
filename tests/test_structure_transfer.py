import json
import shutil
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
    def test_contest_list_parser_accepts_urls_and_removes_duplicates(self):
        keys = web_app.parse_contest_key_list(
            "https://hncode.edu.vn/contest/first\nsecond first"
        )

        self.assertEqual(keys, ["first", "second"])

    def test_contest_lesson_destination_accepts_lesson_or_course(self):
        self.assertEqual(
            web_app.extract_lesson_or_course_destination(
                "https://hncode.edu.vn/course/sample/lesson/123"
            ),
            ("lesson", "sample", "123"),
        )
        self.assertEqual(
            web_app.extract_lesson_or_course_destination(
                "https://hncode.edu.vn/course/sample"
            ),
            ("course", "sample", ""),
        )

    def test_course_lesson_creation_always_sends_required_content(self):
        class LessonSession:
            def __init__(self):
                self.created = False
                self.post_data = []

            def get(self, url, **_kwargs):
                if url.endswith("/lesson/create"):
                    return FakeResponse(
                        """
                        <form method="post">
                          <input name="csrfmiddlewaretoken" value="token">
                          <input name="title" value="">
                          <input name="points" value="">
                          <textarea name="content" required></textarea>
                          <input name="order" value="0">
                        </form>
                        """,
                        url=url,
                    )
                lesson = (
                    """
                    <li class="sortable-item" data-id="321">
                      <span class="item-order">1.</span>
                      <a href="/course/destination/lesson/321">Contest sample</a>
                      <span class="item-points">100p</span>
                    </li>
                    """
                    if self.created
                    else ""
                )
                return FakeResponse(lesson, url=url)

            def post(self, url, data=None, **_kwargs):
                self.post_data = list(data or [])
                self.created = True
                return FakeResponse("", status_code=302, url=url)

        session = LessonSession()
        lesson_id, link, created = web_app.ensure_contest_course_lesson(
            session, "hncode", "destination", "Contest sample", "1"
        )

        self.assertTrue(created)
        self.assertEqual(lesson_id, "321")
        self.assertTrue(link.endswith("/lesson/321"))
        posted = dict(session.post_data)
        self.assertEqual(posted["title"], "Contest sample")
        self.assertTrue(posted["content"].strip())

    @patch("web_app.admin_problem_id", side_effect=["11", "22"])
    @patch("web_app.find_hncode_course_lesson_url", return_value=None)
    @patch("web_app.hncode_course_admin_id", return_value="9")
    @patch("web_app.fetch_contest_info")
    @patch("web_app.login_target_account", return_value=object())
    def test_prepare_multiple_contests_for_course_builds_one_lesson_per_contest(
        self,
        _login,
        fetch_contest,
        _course_id,
        _find_lesson,
        _problem_id,
    ):
        fetch_contest.side_effect = [
            {
                "name": "Contest thứ nhất",
                "problems": [
                    {"code": "first_problem", "title": "Bài một", "points": "40", "order": "1"}
                ],
            },
            {
                "name": "Contest thứ hai",
                "problems": [
                    {"code": "second_problem", "title": "Bài hai", "points": "60", "order": "1"}
                ],
            },
        ]

        response = web_app.app.test_client().post(
            "/api/prepare-contest-to-lesson",
            json={
                "source": "hncode",
                "dest": "hncode",
                "source_account": {},
                "account": {},
                "contest_url": "https://hncode.edu.vn/contest/first\nsecond",
                "lesson_url": "https://hncode.edu.vn/course/destination",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["can_copy"])
        self.assertEqual([row["contest_key"] for row in data["rows"]], ["first", "second"])
        self.assertEqual(
            [row["lesson_title"] for row in data["rows"]],
            ["Contest thứ nhất", "Contest thứ hai"],
        )
        self.assertNotEqual(data["rows"][0]["row_id"], data["rows"][1]["row_id"])
        prepare_id = data["prepare_id"]
        web_app.prepared_lesson_copies.pop(prepare_id, None)
        try:
            restored = web_app.load_prepared_contest_lesson_copy(prepare_id)
            self.assertEqual(restored["contest_keys"], ["first", "second"])
            self.assertIsInstance(restored["root"], Path)
        finally:
            web_app.prepared_lesson_copies.pop(prepare_id, None)
            shutil.rmtree(
                web_app.RUNTIME / ("contest_lesson_copy_" + prepare_id),
                ignore_errors=True,
            )

    @patch("web_app.copy_hncode_contest_to_lesson")
    @patch("web_app.ensure_contest_course_lesson")
    @patch("web_app.login_target_account", return_value=object())
    def test_confirm_course_target_creates_matching_lessons(
        self, _login, ensure_lesson, copy_to_lesson
    ):
        prepare_id = "c" * 32
        rows = [
            {
                "row_id": "1:first:1:a",
                "contest_key": "first",
                "code": "a",
                "source_code": "a",
                "problem_id": "11",
                "score": "40",
                "selected": True,
                "status": "✓ Sẵn sàng",
            },
            {
                "row_id": "2:second:1:b",
                "contest_key": "second",
                "code": "b",
                "source_code": "b",
                "problem_id": "22",
                "score": "60",
                "selected": True,
                "status": "✓ Sẵn sàng",
            },
        ]
        web_app.prepared_lesson_copies[prepare_id] = {
            "source": "hncode",
            "dest": "hncode",
            "contest_keys": ["first", "second"],
            "course_slug": "destination",
            "destination_mode": "course",
            "lesson_id": "",
            "contests": [
                {"key": "first", "lesson_title": "First", "order": 1},
                {"key": "second", "lesson_title": "Second", "order": 2},
            ],
            "rows": rows,
            "root": Path("runtime"),
        }
        ensure_lesson.side_effect = [
            ("101", "https://hncode.edu.vn/course/destination/lesson/101", True),
            ("102", "https://hncode.edu.vn/course/destination/lesson/102", True),
        ]
        copy_to_lesson.side_effect = [
            "https://hncode.edu.vn/course/destination/lesson/101",
            "https://hncode.edu.vn/course/destination/lesson/102",
        ]
        try:
            response = web_app.app.test_client().post(
                "/api/confirm-contest-to-lesson",
                json={
                    "prepare_id": prepare_id,
                    "account": {},
                    "source_account": {},
                    "rows": [
                        {"row_id": row["row_id"], "selected": True, "score": row["score"]}
                        for row in rows
                    ],
                },
            )
        finally:
            web_app.prepared_lesson_copies.pop(prepare_id, None)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual([row["lesson_id"] for row in data["rows"]], ["101", "102"])
        self.assertEqual(ensure_lesson.call_count, 2)
        self.assertEqual(
            [call.args[2] for call in copy_to_lesson.call_args_list], ["101", "102"]
        )

    @patch("web_app.copy_hncode_contest_to_lesson")
    @patch("web_app.ensure_contest_course_lesson", return_value=("101", "https://hncode.edu.vn/course/destination/lesson/101", False))
    @patch("web_app.login_target_account", return_value=object())
    def test_confirm_contest_lesson_continues_after_one_problem_failure(
        self, _login, _ensure_lesson, copy_to_lesson
    ):
        prepare_id = "d" * 32
        rows = [
            {
                "row_id": f"1:first:{index}:{code}",
                "contest_key": "first",
                "code": code,
                "source_code": code,
                "problem_id": str(index),
                "score": "100",
                "selected": True,
                "status": "✓ Sẵn sàng",
            }
            for index, code in enumerate(("bad", "good"), 1)
        ]
        web_app.prepared_lesson_copies[prepare_id] = {
            "source": "hncode",
            "dest": "hncode",
            "contest_keys": ["first"],
            "course_slug": "destination",
            "destination_mode": "course",
            "lesson_id": "",
            "contests": [{"key": "first", "lesson_title": "First", "order": 1}],
            "rows": rows,
            "root": Path("runtime"),
        }
        copy_to_lesson.side_effect = [
            RuntimeError("cannot add bad problem"),
            "https://hncode.edu.vn/course/destination/lesson/101",
        ]
        try:
            response = web_app.app.test_client().post(
                "/api/confirm-contest-to-lesson",
                json={
                    "prepare_id": prepare_id,
                    "account": {},
                    "source_account": {},
                    "rows": [
                        {"row_id": row["row_id"], "selected": True, "score": "100"}
                        for row in rows
                    ],
                },
            )
        finally:
            web_app.prepared_lesson_copies.pop(prepare_id, None)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["rows"][0]["status"], "✗ Lỗi")
        self.assertEqual(data["rows"][1]["status"], "✓ Đã thêm")
        self.assertEqual(copy_to_lesson.call_count, 2)

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

    def test_parse_course_lesson_refs_keeps_order_and_removes_duplicates(self):
        refs = web_app.parse_course_lesson_refs(
            "https://hncode.edu.vn/course/tm69\\_nc2/lesson/3428\n"
            "https://hncode.edu.vn/course/tm69_nc2/lesson/3429\n"
            "https://hncode.edu.vn/course/tm69_nc2/lesson/3428"
        )

        self.assertEqual(
            [(row["source_slug"], row["lesson_id"]) for row in refs],
            [("tm69_nc2", "3428"), ("tm69_nc2", "3429")],
        )

    @patch("web_app.ensure_destination_course", return_value=("9", False))
    @patch(
        "web_app.fetch_course_metadata",
        return_value={"name": "Nguồn", "about": "", "is_public": False, "is_open": False},
    )
    @patch("web_app.hncode_course_contests", return_value=[])
    @patch("web_app.hncode_course_lessons")
    @patch("web_app.login_target_account", return_value=object())
    def test_course_prepare_accepts_selected_lesson_urls(
        self, _login, course_lessons, _contests, _metadata, _ensure_course
    ):
        def lesson_rows(_session, slug, _target):
            if slug == "tm69_nc2":
                return [
                    {"kind": "lesson", "key": "3428", "title": "Lesson A", "order": "8", "points": "100"},
                    {"kind": "lesson", "key": "3429", "title": "Lesson B", "order": "9", "points": "100"},
                ]
            if slug == "hna26_tuyenams2":
                return []
            raise AssertionError(slug)

        course_lessons.side_effect = lesson_rows
        response = web_app.app.test_client().post(
            "/api/prepare-course-clone",
            json={
                "source": "hncode",
                "dest": "hncode",
                "source_url": "https://hncode.edu.vn/course/ignored_source",
                "lesson_urls": (
                    "https://hncode.edu.vn/course/tm69_nc2/lesson/3428\n"
                    "https://hncode.edu.vn/course/tm69_nc2/lesson/3429"
                ),
                "dest_url": "https://hncode.edu.vn/course/hna26_tuyenams2",
                "include_lessons": True,
                "include_contests": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        try:
            self.assertEqual([row["key"] for row in data["rows"]], ["3428", "3429"])
            self.assertEqual([row["source_slug"] for row in data["rows"]], ["tm69_nc2", "tm69_nc2"])
            self.assertTrue(web_app.prepared_course_clones[data["prepare_id"]]["selective_lessons"])
        finally:
            web_app.prepared_course_clones.pop(data["prepare_id"], None)

    @patch("web_app.clone_hncode_lesson_native")
    @patch("web_app.sync_course_metadata")
    @patch("web_app.login_target_account", return_value=object())
    def test_selected_lessons_keep_destination_course_metadata(
        self, _login, sync_metadata, clone_lesson
    ):
        prepare_id = "a" * 32
        clone_lesson.side_effect = [
            "https://hncode.edu.vn/course/dest/lesson/81",
            "https://hncode.edu.vn/course/dest/lesson/82",
        ]
        web_app.prepared_course_clones[prepare_id] = {
            "source_slug": "source_a",
            "dest_slug": "dest",
            "source": "hncode",
            "dest": "hncode",
            "dest_course_id": "9",
            "destination_created": False,
            "selective_lessons": True,
            "rows": [
                {"kind": "lesson", "key": "11", "title": "A", "source_slug": "source_a", "selected": True},
                {"kind": "lesson", "key": "22", "title": "B", "source_slug": "source_b", "selected": True},
            ],
        }
        try:
            response = web_app.app.test_client().post(
                "/api/confirm-course-clone",
                json={
                    "prepare_id": prepare_id,
                    "source_account": {},
                    "dest_account": {},
                    "rows": [
                        {"kind": "lesson", "key": "11", "selected": True},
                        {"kind": "lesson", "key": "22", "selected": True},
                    ],
                },
            )
        finally:
            web_app.prepared_course_clones.pop(prepare_id, None)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertEqual(
            [call.args[1] for call in clone_lesson.call_args_list],
            ["source_a", "source_b"],
        )
        sync_metadata.assert_not_called()

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

    def test_hnoj_contest_problem_row_uses_numeric_output_prefix_default(self):
        page = """
        <form>
          <input name="contest_problems-TOTAL_FORMS" value="0">
          <input name="contest_problems-__prefix__-id" value="">
          <input name="contest_problems-__prefix__-contest" value="">
          <select name="contest_problems-__prefix__-problem"><option value=""></option></select>
          <input name="contest_problems-__prefix__-points" value="">
          <input name="contest_problems-__prefix__-max_submissions" value="">
          <input name="contest_problems-__prefix__-output_prefix_override" value="0">
          <input name="contest_problems-__prefix__-order" value="">
          <input name="contest_problems-__prefix__-partial" type="checkbox">
        </form>
        """
        data = []

        web_app.append_contest_problem_fields(
            data,
            page,
            [{"id": "55", "points": "100", "partial": True, "order": "0"}],
            0,
            "hnoj",
        )

        fields = dict(data)
        self.assertEqual(fields["contest_problems-0-output_prefix_override"], "0")
        self.assertEqual(fields["contest_problems-0-max_submissions"], "")
        self.assertEqual(fields["contest_problems-0-problem"], "55")

    def test_hncode_contest_problem_row_does_not_send_hnoj_only_field(self):
        page = """
        <form>
          <input name="contest_problems-TOTAL_FORMS" value="0">
          <input name="contest_problems-__prefix__-id" value="">
          <input name="contest_problems-__prefix__-contest" value="">
          <select name="contest_problems-__prefix__-problem"><option value=""></option></select>
          <select name="contest_problems-__prefix__-quiz"><option value=""></option></select>
          <input name="contest_problems-__prefix__-points" value="">
          <input name="contest_problems-__prefix__-max_submissions" value="0">
          <input name="contest_problems-__prefix__-hidden_subtasks" value="">
          <input name="contest_problems-__prefix__-order" value="">
          <input name="contest_problems-__prefix__-partial" type="checkbox">
        </form>
        """
        data = []

        web_app.append_contest_problem_fields(
            data,
            page,
            [{"id": "81", "points": "100", "partial": True, "order": "0"}],
            0,
            "hncode",
        )

        fields = dict(data)
        self.assertEqual(fields["contest_problems-0-max_submissions"], "0")
        self.assertNotIn("contest_problems-0-output_prefix_override", fields)

    def test_contest_problem_row_rejects_missing_destination_problem_id(self):
        page = '<input name="contest_problems-__prefix__-problem" value="">'

        with self.assertRaisesRegex(RuntimeError, "chưa có ID ở trang đích"):
            web_app.append_contest_problem_row([], page, 0, {"code": "sample"}, "hnoj")

    def test_existing_hncode_contest_keeps_required_setup_when_source_is_blank(self):
        page = """
        <form>
          <input name="name" value="Contest cũ">
          <textarea name="description">Mô tả cũ</textarea>
          <select name="scoreboard_visibility"><option value="V" selected>Visible</option></select>
          <select name="format_name"><option value="vnoj" selected>VNOJ</option></select>
          <select name="view_contest_scoreboard">
            <option value=""></option><option value="A" selected>All</option>
          </select>
          <input name="points_precision" value="2">
          <input name="start_time_0" value="2026-10-01"><input name="start_time_1" value="08:00:00">
          <input name="end_time_0" value="2026-10-01"><input name="end_time_1" value="10:00:00">
          <input name="strict_violation_limit" value="3">
          <input name="strict_grace_seconds" value="20">
        </form>
        """
        base_data = [
            ("view_contest_scoreboard", "A"),
            ("strict_violation_limit", "3"),
            ("strict_grace_seconds", "20"),
        ]

        result = web_app.apply_contest_metadata_to_existing_form(
            base_data,
            page,
            {
                "name": "Contest mới",
                "view_contest_scoreboard": "",
                "strict_violation_limit": "",
                "strict_grace_seconds": "",
            },
            "hncode",
        )

        fields = dict(result)
        self.assertEqual(fields["view_contest_scoreboard"], "A")
        self.assertEqual(fields["strict_violation_limit"], "3")
        self.assertEqual(fields["strict_grace_seconds"], "20")
