import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

from services import misc as misc_service
from services import quiz as quiz_service


QUIZ_SAMPLE = """
Tiêu đề: Câu cộng
Loại: Trắc nghiệm 1 đáp án
Nội dung:
1 + 1 bằng mấy?
Lựa chọn:
A. 1
B. 2
C. 3
Đáp án: B
Giải thích:
1 + 1 = 2.
---
Tiêu đề: Chọn số chẵn
Loại: Trắc nghiệm nhiều đáp án
Nội dung:
Các số nào là số chẵn?
Lựa chọn:
A. 2
B. 3
C. 4
Đáp án: A, C
---
Loại: Trả lời ngắn
Nội dung:
Tên ngôn ngữ Python viết thường?
Đáp án:
python
---
Loại: Đúng / Sai
Nội dung:
2 là số nguyên tố.
Đáp án: Đúng
"""


class QuizServiceTests(unittest.TestCase):
    def test_parse_quiz_markdown(self):
        questions = quiz_service.parse_quiz_markdown(QUIZ_SAMPLE)

        self.assertEqual([item["type"] for item in questions], ["MC", "MA", "SA", "TF"])
        self.assertEqual(questions[0]["title"], "Câu cộng")
        self.assertEqual(questions[0]["correct_answers"], {"answers": "B"})
        self.assertEqual(questions[1]["correct_answers"], {"answers": ["A", "C"]})
        self.assertEqual(questions[2]["correct_answers"]["answers"], ["python"])
        self.assertEqual(questions[3]["correct_answers"], {"answers": "T"})

    def test_validate_quiz_question_reports_bad_answer(self):
        bad = """
        Loại: Trắc nghiệm 1 đáp án
        Nội dung: Chọn đáp án đúng.
        Lựa chọn:
        A. Đúng
        B. Sai
        Đáp án: C
        """

        with self.assertRaisesRegex(RuntimeError, "không có trong lựa chọn"):
            quiz_service.parse_quiz_markdown(textwrap.dedent(bad))

    def test_prepare_quiz_rows_keeps_valid_and_invalid_blocks(self):
        text = QUIZ_SAMPLE + "\n---\nLoại: Trắc nghiệm 1 đáp án\nNội dung: Thiếu lựa chọn\nĐáp án: A\n"

        questions, rows = quiz_service.prepare_quiz_items(text)

        self.assertEqual(len(questions), 4)
        self.assertEqual(len(rows), 5)
        self.assertTrue(rows[0]["can_upload"])
        self.assertFalse(rows[-1]["can_upload"])
        self.assertIn("Lựa chọn", rows[-1]["error"])


class MiscServiceTests(unittest.TestCase):
    def test_last_scratch_submission_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "ContestData"
            history = nested / "HS001" / "$History"
            history.mkdir(parents=True)
            (history / "project_1.sb3").write_bytes(b"old")
            (history / "project_3.sb3").write_bytes(b"new")
            (nested / "HS002").mkdir()
            output = root / "out"

            data_root = misc_service.find_scratch_data_root(root)
            summary = misc_service.collect_last_scratch_submissions(data_root, output)

            self.assertEqual(data_root.name, "ContestData")
            self.assertEqual(summary["total"], 2)
            self.assertEqual(summary["found"], 1)
            self.assertEqual(summary["missing"], 1)
            self.assertTrue((output / "HS001.sb3").exists())
            self.assertTrue((output / "report.txt").exists())

    def test_collect_code_records_from_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "contest_data.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "HS001/bai1.py",
                    "def solve_problem_with_clear_name():\n    # time complexity O(n)\n    return 1\n",
                )
                archive.writestr("HS002/$History/bai1_2.cpp", "#include <bits/stdc++.h>\nint main(){return 0;}\n")
            extract_root = Path(tmp) / "extracted"

            records = misc_service.collect_code_records_from_zip(zip_path, extract_root)

            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["contest"], "contest")
            self.assertEqual(records[0]["problem"], "bai1")
            self.assertGreater(records[0]["features"]["code_ai_score"], 0)
            self.assertTrue(records[1]["is_history"])
            self.assertTrue(Path(records[0]["local_path"]).exists())

    def test_code_similarity_logic(self):
        code_a = "int main(){int answer=0; for(int i=0;i<10;i++) answer+=i; return answer;}"
        code_b = "int main(){int total=0; for(int j=0;j<10;j++) total+=j; return total;}"
        rec_a = {"ext": ".cpp", "fingerprints": misc_service.token_fingerprints(misc_service.normalized_code_tokens(code_a, ".cpp"))}
        rec_b = {"ext": ".cpp", "fingerprints": misc_service.token_fingerprints(misc_service.normalized_code_tokens(code_b, ".cpp"))}

        self.assertGreater(misc_service.code_similarity_percent(rec_a, rec_b), 70)


if __name__ == "__main__":
    unittest.main()
