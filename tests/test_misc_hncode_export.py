import unittest
from unittest.mock import patch

import web_app
from services import misc as misc_service


class HncodeMiscExportTests(unittest.TestCase):
    def setUp(self):
        self.client = web_app.app.test_client()

    def test_parse_hncode_problem_inputs_accepts_codes_and_links(self):
        text = "\n".join(
            [
                "abc_problem",
                "https://hncode.edu.vn/problem/xyz-1",
                "https://hncode.edu.vn/contest/contest_a/problems/p_with_under",
                "https://hncode.edu.vn/contest/contest_a/problem/old_style",
                "abc_problem",
            ]
        )

        self.assertEqual(
            misc_service.parse_hncode_problem_inputs(text),
            ["abc_problem", "xyz-1", "p_with_under", "old_style"],
        )

    def test_list_problem_codes_includes_links_without_live_login(self):
        rows = [
            {"code": "p_one", "title": "Problem One", "points": "100"},
            {"code": "p_two", "title": "Problem Two", "points": "100"},
        ]
        with patch.object(web_app, "login_hncode", return_value=object()), patch.object(
            web_app, "hncode_contest_problem_rows", return_value=rows
        ):
            response = self.client.post(
                "/api/misc/list-problem-codes",
                json={
                    "site": "hncode",
                    "source_type": "contest",
                    "url": "https://hncode.edu.vn/contest/demo",
                    "account": {"username": "fake", "password": "fake"},
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["links_text"], "https://hncode.edu.vn/problem/p_one\nhttps://hncode.edu.vn/problem/p_two")
        self.assertEqual(
            data["source_links_text"],
            "https://hncode.edu.vn/contest/demo/problems/p_one\nhttps://hncode.edu.vn/contest/demo/problems/p_two",
        )
        self.assertEqual(data["rows"][0]["link"], "https://hncode.edu.vn/problem/p_one")

    def test_list_problem_codes_falls_back_to_public_when_login_fails(self):
        rows = [{"code": "public_one", "title": "Public One", "points": "100"}]
        with patch.object(web_app, "login_hncode", side_effect=RuntimeError("HNCode login did not create a session")), patch.object(
            web_app, "hncode_contest_problem_rows", return_value=rows
        ):
            response = self.client.post(
                "/api/misc/list-problem-codes",
                json={
                    "site": "hncode",
                    "source_type": "contest",
                    "url": "https://hncode.edu.vn/contest/demo",
                    "account": {"username": "fake", "password": "wrong"},
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["codes_text"], "public_one")
        self.assertIn("doc trang public", data["meta"]["auth_note"])

    def test_list_problem_codes_accepts_multiple_contests_and_resets_index(self):
        def fake_rows(_session, contest_key):
            if contest_key == "contest_a":
                return [
                    {"code": "a_one", "title": "A One", "points": "100"},
                    {"code": "a_two", "title": "A Two", "points": "100"},
                ]
            return [{"code": "b_one", "title": "B One", "points": "100"}]

        with patch.object(web_app, "login_hncode", return_value=object()), patch.object(
            web_app, "hncode_contest_problem_rows", side_effect=fake_rows
        ):
            response = self.client.post(
                "/api/misc/list-problem-codes",
                json={
                    "site": "hncode",
                    "source_type": "contest",
                    "url": "https://hncode.edu.vn/contest/contest_a\nhttps://hncode.edu.vn/contest/contest_b",
                    "account": {"username": "fake", "password": "fake"},
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["meta"]["group_count"], 2)
        self.assertEqual(data["codes_text"], "a_one\na_two\n-----------\nb_one")
        self.assertEqual([row["index"] for row in data["rows"]], [1, 2, 1])
        self.assertEqual(data["rows"][2]["source_label"], "HNCode Contest: contest_b")

    def test_export_hncode_statements_writes_markdown_without_live_login(self):
        snapshots = {
            "p_one": {"name": "Bai mot", "statement": "Noi dung bai mot."},
            "p_two": {"name": "Bai hai", "statement": "Noi dung bai hai."},
        }

        def fake_snapshot(_session, code):
            return snapshots[code]

        with patch.object(web_app, "login_hncode", return_value=object()), patch.object(
            web_app, "hncode_problem_snapshot", side_effect=fake_snapshot
        ):
            response = self.client.post(
                "/api/misc/export-hncode-statements",
                json={
                    "items": "p_one\nhttps://hncode.edu.vn/contest/demo/problems/p_two",
                    "account": {"username": "fake", "password": "fake"},
                },
            )

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["download_url"])
        self.assertEqual([row["code"] for row in data["rows"]], ["p_one", "p_two"])

        download = self.client.get(data["download_url"])
        markdown = download.get_data(as_text=True)
        download.close()
        self.assertEqual(download.status_code, 200)
        self.assertIn("## 1. Bai mot (`p_one`)", markdown)
        self.assertIn("Noi dung bai hai.", markdown)


if __name__ == "__main__":
    unittest.main()
