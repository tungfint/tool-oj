import unittest

from services.quiz import parse_quiz_markdown, prepare_quiz_items


QUIZ_MARKDOWN = r"""
Loại: MC
Tiêu đề: Một đáp án
Nội dung:
2 + 2 bằng bao nhiêu?
Lựa chọn:
- A. 3
- B. 4
Đáp án: B
---
Loại: Điền vào chỗ trống
Tiêu đề: Hai ô trống
Nội dung:
Điền \_\_\_(1)\_\_\_ và \_\_\_(2)\_\_\_.
Đáp án:
- Ô 1: 5 | năm
- Ô 2: Python | python
"""


class QuizParserTests(unittest.TestCase):
    def test_parse_fill_blank_payload(self):
        questions = parse_quiz_markdown(QUIZ_MARKDOWN)

        self.assertEqual([item["type"] for item in questions], ["MC", "FB"])
        self.assertEqual(questions[1]["grading_strategy"], "correct_only")
        self.assertIsNone(questions[1]["choices"])
        self.assertEqual(
            questions[1]["correct_answers"]["blanks"],
            [
                {"label": "Ô 1:", "answers": ["5", "năm"]},
                {"label": "Ô 2:", "answers": ["Python", "python"]},
            ],
        )

    def test_prepare_rows_accepts_fill_blank_label(self):
        questions, rows = prepare_quiz_items(QUIZ_MARKDOWN)

        self.assertEqual(len(questions), 2)
        self.assertTrue(all(row["can_upload"] for row in rows))
        self.assertEqual(rows[1]["type"], "FB")


if __name__ == "__main__":
    unittest.main()
