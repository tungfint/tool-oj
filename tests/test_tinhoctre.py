import tempfile
import unittest
from pathlib import Path

import requests

from services import tinhoctre as tinhoctre_service


class FakeResponse:
    def __init__(self, status_code=200, headers=None, text="", url="https://tinhoctre.vn/"):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.url = url


class TinHocTreServiceTests(unittest.TestCase):
    def test_statement_for_tinhoctre_replaces_dollar_with_tilde(self):
        statement = "Tên bài | ma_bai\n\nTính $a+b$ và giữ công thức ~c~."

        normalized = tinhoctre_service.statement_for_tinhoctre(statement, skip_title_line=True)

        self.assertNotIn("$", normalized)
        self.assertIn("~a+b~", normalized)
        self.assertIn("~c~", normalized)
        self.assertNotIn("Tên bài | ma_bai", normalized)

    def test_build_urls(self):
        base_url = "https://tinhoctre.vn"

        self.assertEqual(
            tinhoctre_service.admin_problem_add_url(base_url),
            "https://tinhoctre.vn/admin/judge/problem/add/",
        )
        self.assertEqual(tinhoctre_service.problem_url(base_url, "abc"), "https://tinhoctre.vn/problem/abc")
        self.assertEqual(
            tinhoctre_service.problem_edit_url(base_url, "abc"),
            "https://tinhoctre.vn/problem/abc/edit",
        )
        self.assertEqual(
            tinhoctre_service.test_data_url(base_url, "abc"),
            "https://tinhoctre.vn/problem/abc/test_data",
        )

    def test_detect_waf_challenge_from_fake_response(self):
        self.assertTrue(tinhoctre_service.is_waf_challenge_response(FakeResponse(status_code=202)))
        self.assertTrue(
            tinhoctre_service.is_waf_challenge_response(
                FakeResponse(headers={"x-amzn-waf-action": "challenge"})
            )
        )
        self.assertTrue(tinhoctre_service.is_waf_challenge_response(FakeResponse(text="aws-waf-token")))
        self.assertFalse(tinhoctre_service.is_waf_challenge_response(FakeResponse(text="<form></form>")))

    def test_detect_login_redirect(self):
        self.assertTrue(tinhoctre_service.is_login_redirect(FakeResponse(url="https://tinhoctre.vn/admin/login/")))
        self.assertTrue(tinhoctre_service.is_login_redirect(FakeResponse(text="/accounts/login")))
        self.assertFalse(tinhoctre_service.is_login_redirect(FakeResponse(url="https://tinhoctre.vn/problem/abc/edit")))

    def test_parse_form_errors(self):
        html = """
        <p class="errornote">Please correct the error below.</p>
        <ul class="errorlist"><li>Code: Problem with this code already exists.</li></ul>
        <div class="alert alert-danger">Description is required.</div>
        """

        errors = tinhoctre_service.parse_form_errors(html)

        self.assertIn("Please correct the error below.", errors)
        self.assertIn("Code: Problem with this code already exists.", errors)
        self.assertIn("Description is required.", errors)

    def test_cookie_storage_and_apply_cookie_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            tinhoctre_service.save_cookie(root, "csrftoken=abc; sessionid=def")
            loaded = tinhoctre_service.load_cookie(root)

        session = tinhoctre_service.apply_cookie_header(requests.Session(), loaded)

        self.assertEqual(loaded, "csrftoken=abc; sessionid=def")
        self.assertEqual(session.cookies.get("csrftoken", domain=".tinhoctre.vn"), "abc")
        self.assertEqual(session.cookies.get("sessionid", domain="tinhoctre.vn"), "def")

    def test_problem_add_form_detection(self):
        page = '<form><input name="code"><textarea name="description"></textarea></form>'

        self.assertTrue(tinhoctre_service.is_problem_add_form(page))
        self.assertFalse(tinhoctre_service.is_problem_add_form("<html>login</html>"))


if __name__ == "__main__":
    unittest.main()
