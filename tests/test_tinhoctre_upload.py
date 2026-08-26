import unittest

from transfer_tinhoctre_to_hncode import ProblemInfo, create_hncode_problem


class FakeResponse:
    def __init__(self, status_code, url, text="", headers=None):
        self.status_code = status_code
        self.url = url
        self.text = text
        self.headers = headers or {}

    @property
    def ok(self):
        return self.status_code < 400


class FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if method == "GET" and url.endswith("/admin/judge/problem/add/"):
            return FakeResponse(500, url, "TemplateSyntaxError")
        if method == "GET" and url.endswith("/admin/judge/problem/"):
            return FakeResponse(200, url, '<a href="/problem/existing/edit">existing</a>')
        if method == "GET" and url.endswith("/problem/existing/edit"):
            return FakeResponse(200, url, problem_form("existing"))
        if method == "POST" and url.endswith("/admin/judge/problem/add/"):
            return FakeResponse(302, url, headers={"Location": "/admin/judge/problem/99/change/"})
        if method == "GET" and url.endswith("/problem/new_problem/edit"):
            return FakeResponse(200, url, problem_form("new_problem"))
        raise AssertionError(f"Unexpected request: {method} {url}")


def problem_form(code):
    return f"""
    <form>
      <input name="csrfmiddlewaretoken" value="csrf-token">
      <input name="code" value="{code}">
      <input name="allowed_languages" value="15">
      <select name="types"><option value="13">Default</option></select>
      <select name="group"><option value="13">Default</option></select>
    </form>
    """


class TinHocTreUploadTests(unittest.TestCase):
    def test_create_problem_uses_public_edit_form_when_admin_template_is_broken(self):
        session = FakeSession()
        info = ProblemInfo(
            code="new_problem",
            name="Bài kiểm thử",
            description="Đề bài kiểm thử.",
            points="100",
            partial=True,
            time_limit="1.0",
            memory_limit="1048576",
            memory_unit="KB",
        )

        result = create_hncode_problem(
            session,
            "https://tinhoctre.vn",
            info,
            dest_code="new_problem",
            type_id="13",
            group_id="13",
            public=False,
            allow_all_languages=False,
            allowed_language_ids=["15"],
            default_type_id="13",
            default_group_id="13",
            target_label="TinHocTre",
        )

        self.assertEqual(result, "https://tinhoctre.vn/admin/judge/problem/99/change/")
        post = next(call for call in session.calls if call[0] == "POST")
        self.assertFalse(post[2]["allow_redirects"])
        self.assertIn(("code", "new_problem"), post[2]["data"])


if __name__ == "__main__":
    unittest.main()
