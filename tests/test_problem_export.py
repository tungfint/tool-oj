from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from services import problem_export


class ProblemExportTest(unittest.TestCase):
    def test_parse_problem_codes_from_codes_and_links(self) -> None:
        value = """
        bai_mot
        https://hncode.edu.vn/problem/bai_hai
        https://hncode.edu.vn/contest/demo/problems/bai_ba
        bai_mot
        """
        self.assertEqual(
            problem_export.problem_codes(value),
            ["bai_mot", "bai_hai", "bai_ba"],
        )

    def test_detect_input_type(self) -> None:
        self.assertEqual(
            problem_export.detect_input_type(
                "https://hncode.edu.vn/course/demo/lesson/123", "auto"
            ),
            "lesson",
        )
        self.assertEqual(
            problem_export.detect_input_type(
                "https://hnoj.edu.vn/contest/demo", "auto"
            ),
            "contest",
        )
        self.assertEqual(problem_export.detect_input_type("a b", "auto"), "codes")
        self.assertEqual(problem_export.detect_input_type("a", "auto"), "auto_single")

    def test_parse_contest_and_lesson_references(self) -> None:
        self.assertEqual(
            problem_export.contest_key("https://hncode.edu.vn/contest/demo_01"),
            "demo_01",
        )
        self.assertEqual(
            problem_export.lesson_ref(
                "https://hncode.edu.vn/course/course_01/lesson/456"
            ),
            ("course_01", "456"),
        )

    def test_absolute_asset_urls(self) -> None:
        source = "![Hình](/media/a.png)\n<img src='uploads/b.png'>"
        result = problem_export.absolute_asset_urls(source, "https://hncode.edu.vn")
        self.assertIn("https://hncode.edu.vn/media/a.png", result)
        self.assertIn("https://hncode.edu.vn/uploads/b.png", result)

    def test_write_separate_zip_and_combined_markdown(self) -> None:
        problems = [
            {"code": "a", "name": "Bài A", "statement": "Nội dung A"},
            {"code": "b", "name": "Bài B", "statement": "Nội dung B"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            zip_path = problem_export.write_export(root / "zip", problems, "separate", "hncode", "HNCode")
            with zipfile.ZipFile(zip_path) as archive:
                self.assertEqual(archive.namelist(), ["a.md", "b.md"])
                self.assertIn("Bài A | a", archive.read("a.md").decode("utf-8-sig"))

            md_path = problem_export.write_export(root / "md", problems, "combined", "hncode", "HNCode")
            content = md_path.read_text(encoding="utf-8-sig")
            self.assertIn("## 1. Bài A (`a`)", content)
            self.assertIn("## 2. Bài B (`b`)", content)


if __name__ == "__main__":
    unittest.main()
