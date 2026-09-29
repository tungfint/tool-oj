import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import web_app
from services.quiz import parse_quiz_markdown
from services.quiz_export import (
    parse_question_admin_form,
    parse_quiz_admin_form,
    quiz_code,
    quiz_markdown,
    write_quiz_export,
)


QUIZ_FORM = """
<input name="code" value="quiz_demo">
<input name="title" value="Đề Quiz mẫu">
<textarea name="description">Hướng dẫn ![ảnh](/media/guide.png)</textarea>
<input name="time_limit" value="120">
<input name="is_public" type="checkbox" checked>
<input name="quiz_questions-TOTAL_FORMS" value="3">
<select name="quiz_questions-0-question"><option value="12" selected>Q12</option></select>
<input name="quiz_questions-0-points" value="5">
<input name="quiz_questions-0-order" value="2">
<select name="quiz_questions-1-question"><option value="11" selected>Q11</option></select>
<input name="quiz_questions-1-points" value="10">
<input name="quiz_questions-1-order" value="1">
<select name="quiz_questions-2-question"><option value="13" selected>Q13</option></select>
<input name="quiz_questions-2-points" value="5">
<input name="quiz_questions-2-order" value="3">
<input name="quiz_questions-2-DELETE" type="checkbox" checked>
"""


QUESTION_FORM = """
<input name="title" value="Chọn kết quả">
<select name="question_type"><option value="MC" selected>MC</option></select>
<textarea name="content">Xem ![hình](/media/q.png) rồi chọn.</textarea>
<textarea name="choices">[{&quot;id&quot;: &quot;A&quot;, &quot;text&quot;: &quot;1&quot;}, {&quot;id&quot;: &quot;B&quot;, &quot;text&quot;: &quot;2&quot;}]</textarea>
<textarea name="correct_answers">{&quot;answers&quot;: &quot;B&quot;}</textarea>
<textarea name="explanation">Vì $1+1=2$.</textarea>
<select name="grading_strategy"><option value="all_or_nothing" selected>All</option></select>
<input name="shuffle_choices" type="checkbox" checked>
"""


def sample_quiz():
    return {
        "code": "quiz_demo",
        "title": "Đề Quiz mẫu",
        "description": "Làm đủ các câu.",
        "questions": [
            {
                "type": "MC",
                "title": "Một đáp án",
                "content": "2 + 2 bằng bao nhiêu?",
                "choices": [{"id": "A", "text": "3"}, {"id": "B", "text": "4"}],
                "correct_answers": {"answers": "B"},
                "explanation": "Vì $2+2=4$.",
                "points": "5",
            },
            {
                "type": "MA",
                "title": "Nhiều đáp án",
                "content": "Chọn số nguyên tố.",
                "choices": [{"id": "A", "text": "2"}, {"id": "B", "text": "3"}],
                "correct_answers": {"answers": ["A", "B"]},
                "explanation": "",
                "points": "5",
            },
            {
                "type": "SA",
                "title": "Trả lời ngắn",
                "content": "Tính $6\times7$.",
                "choices": [],
                "correct_answers": {"type": "exact", "answers": ["42", "bốn mươi hai"]},
                "explanation": "",
                "points": "5",
            },
            {
                "type": "FB",
                "title": "Điền khuyết",
                "content": r"Điền \_\_\_(1)\_\_\_ và \_\_\_(2)\_\_\_.",
                "choices": None,
                "correct_answers": {
                    "blanks": [
                        {"label": "Ô 1:", "answers": ["5", "năm"]},
                        {"label": "Ô 2:", "answers": ["Python"]},
                    ]
                },
                "explanation": "",
                "points": "5",
            },
            {
                "type": "TF",
                "title": "Đúng sai",
                "content": "Python là ngôn ngữ lập trình.",
                "choices": [{"id": "T", "text": "Đúng"}, {"id": "F", "text": "Sai"}],
                "correct_answers": {"answers": "T"},
                "explanation": "",
                "points": "5",
            },
        ],
    }


class QuizExportTests(unittest.TestCase):
    def test_parse_quiz_code_from_url(self):
        self.assertEqual(
            quiz_code("https://tinhoctre.vn/quiz/tht26_tq_m2/"), "tht26_tq_m2"
        )

    def test_parse_quiz_form_preserves_order_and_skips_deleted(self):
        quiz = parse_quiz_admin_form(QUIZ_FORM, "https://tinhoctre.vn")

        self.assertEqual(quiz["code"], "quiz_demo")
        self.assertEqual([row["question_id"] for row in quiz["assignments"]], [11, 12])
        self.assertEqual(quiz["description"], "Hướng dẫn ![ảnh](https://tinhoctre.vn/media/guide.png)")

    def test_parse_question_form_reads_json_and_assets(self):
        question = parse_question_admin_form(
            QUESTION_FORM,
            11,
            "https://tinhoctre.vn",
            {"points": "5", "order": 1},
        )

        self.assertEqual(question["type"], "MC")
        self.assertEqual(question["correct_answers"]["answers"], "B")
        self.assertIn("https://tinhoctre.vn/media/q.png", question["content"])
        self.assertTrue(question["shuffle_choices"])

    def test_export_markdown_round_trips_all_supported_types(self):
        content = quiz_markdown(sample_quiz())
        parsed = parse_quiz_markdown(content)

        self.assertEqual([question["type"] for question in parsed], ["MC", "MA", "SA", "FB", "TF"])
        self.assertEqual(parsed[0]["correct_answers"]["answers"], "B")
        self.assertEqual(parsed[3]["correct_answers"]["blanks"][0]["answers"], ["5", "năm"])

    def test_write_markdown_uses_reimportable_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_quiz_export(Path(temp_dir), sample_quiz(), "markdown")

            self.assertEqual(path.name, "quiz_demo_quiz.md")
            self.assertEqual(len(parse_quiz_markdown(path.read_text(encoding="utf-8-sig"))), 5)

    def test_export_quiz_api_returns_downloadable_markdown(self):
        rows = [
            {
                "index": 1,
                "question_id": 101,
                "title": "Một đáp án",
                "type": "MC",
                "points": "5",
                "status": "✓ Đã đọc",
                "link": "https://tinhoctre.vn/quiz/questions/101/",
                "error": "",
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            web_app, "RUNTIME", Path(temp_dir)
        ), patch.object(web_app, "login_target_account", return_value=object()), patch.object(
            web_app.quiz_export_service,
            "fetch_quiz",
            return_value=(sample_quiz(), rows),
        ):
            client = web_app.app.test_client()
            response = client.post(
                "/api/misc/export-quiz",
                json={
                    "site": "tinhoctre",
                    "source": "tht26_tq_m2",
                    "format": "markdown",
                    "account": {"username": "admin", "password": "secret"},
                },
            )

            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data["ok"])
            self.assertEqual(data["filename"], "quiz_demo_quiz.md")
            download = client.get(data["download_url"])
            self.assertEqual(download.status_code, 200)
            self.assertIn(b"Lo\xe1\xba\xa1i: MC", download.data)
            download.close()


if __name__ == "__main__":
    unittest.main()
