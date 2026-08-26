import time
import unittest
from unittest.mock import patch

import web_app


QUIZ_MARKDOWN = """
Loại: MC
Tiêu đề: Câu kiểm tra 1
Nội dung:
2 + 2 bằng bao nhiêu?
Lựa chọn:
- A. 3
- B. 4
Đáp án: B
---
Loại: SA
Tiêu đề: Câu kiểm tra 2
Nội dung:
Số tiếp theo sau 4 là số nào?
Đáp án: 5
"""


class QuizBackgroundUploadTests(unittest.TestCase):
    def setUp(self):
        self.client = web_app.app.test_client()
        self.progress_id = ""

    def tearDown(self):
        if self.progress_id:
            web_app.progress_path(self.progress_id).unlink(missing_ok=True)

    def test_start_upload_rebuilds_questions_and_reports_progress(self):
        created_links = [
            "https://tinhoctre.vn/quiz/questions/101/",
            "https://tinhoctre.vn/quiz/questions/102/",
        ]
        with (
            patch.object(web_app, "login_quiz_target", return_value=object()),
            patch.object(web_app, "create_quiz_question", side_effect=created_links) as create_mock,
        ):
            started_at = time.monotonic()
            response = self.client.post(
                "/api/upload-quiz-start",
                json={
                    "prepare_id": "missing-from-this-worker",
                    "text": QUIZ_MARKDOWN,
                    "target": "quiz_tinhoctre",
                    "account": {"username": "test", "password": "test"},
                    "shuffle_choices": True,
                    "is_public": True,
                },
            )
            elapsed = time.monotonic() - started_at

            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertTrue(body["ok"])
            self.progress_id = body["progress_id"]
            self.assertLess(elapsed, 1.0)

            deadline = time.monotonic() + 3
            progress = {}
            while time.monotonic() < deadline:
                progress = web_app.job_service.read_job(web_app.PROGRESS_DIR, self.progress_id)
                if progress.get("finished"):
                    break
                time.sleep(0.02)

            self.assertTrue(progress.get("finished"), progress)
            self.assertTrue(progress.get("ok"), progress)
            self.assertEqual(progress.get("done"), 2)
            self.assertEqual(progress.get("total"), 2)
            self.assertEqual([row["link"] for row in progress["rows"]], created_links)
            self.assertEqual(create_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
