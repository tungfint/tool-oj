from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import web_app
from transfer_tinhoctre_to_hncode import ProblemInfo


class LqdojTransferRulesTests(TestCase):
    def setUp(self):
        self.client = web_app.app.test_client()

    @patch("web_app.problem_exists_for_target", return_value=True)
    @patch("web_app.fetch_source_problem")
    @patch("web_app.login_target_account", return_value=object())
    @patch("web_app.login_problem_source", return_value=object())
    def test_problem_prepare_requires_explicit_overwrite(
        self, _login_source, _login_dest, fetch_source, _exists
    ):
        fetch_source.return_value = (
            ProblemInfo("abc_1", "Bài mẫu", "Nội dung", "100", True, "1.0", "256", "MB"),
            Path("abc_1.zip"),
            [],
            "",
        )
        response = self.client.post(
            "/api/prepare-transfer",
            json={
                "source": "hncode",
                "dest": "lqdoj",
                "codes": ["abc_1"],
                "source_account": {},
                "dest_account": {},
                "settings": {},
            },
        )
        self.assertEqual(response.status_code, 200)
        row = response.get_json()["rows"][0]
        self.assertEqual(row["code"], "abc1")
        self.assertEqual(row["memory_limit"], "256")
        self.assertEqual(row["source_memory_limit"], "256")
        self.assertTrue(row["dest_exists"])
        self.assertFalse(row["overwrite"])
        self.assertIn("chọn Ghi đè", row["status"])

    def test_transfer_memory_is_entered_in_mb_and_sent_in_kb(self):
        info = ProblemInfo("abc", "Bài mẫu", "Nội dung", "100", True, "1.0", "256", "MB")

        web_app.apply_transfer_resource_limits(info, {"memory_limit": "1024"}, {})

        self.assertEqual(info.memory_limit, "1048576")
        self.assertEqual(info.memory_unit, "KB")

    @patch("web_app.admin_problem_id", return_value="42")
    @patch("web_app.admin_contest_change_url", return_value="https://lqdoj.edu.vn/admin/judge/contest/1/change/")
    @patch("web_app.fetch_contest_info")
    @patch("web_app.login_target_account", return_value=object())
    def test_contest_prepare_reuses_existing_destination_problem_and_contest(
        self, _login, fetch_contest, _contest_exists, _problem_exists
    ):
        fetch_contest.return_value = {
            "key": "contest_1",
            "name": "Contest mẫu",
            "start_time": "",
            "end_time": "",
            "problems": [
                {"code": "abc_1", "title": "Bài mẫu", "points": "100", "order": 1}
            ],
        }
        response = self.client.post(
            "/api/prepare-contest-transfer",
            json={
                "source": "hncode",
                "dest": "lqdoj",
                "codes": ["contest_1"],
                "source_account": {},
                "dest_account": {},
            },
        )
        self.assertEqual(response.status_code, 200)
        row = response.get_json()["rows"][0]
        self.assertEqual(row["key"], "contest1")
        self.assertTrue(row["can_transfer"])
        self.assertIn("bổ sung bài", row["status"])
        problem = row["problems"][0]
        self.assertEqual(problem["source_code"], "abc_1")
        self.assertEqual(problem["dest_code"], "abc1")
        self.assertIn("dùng lại", problem["status"])
