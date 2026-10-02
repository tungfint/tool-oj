from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from services import problem_export


class ProblemExportTest(unittest.TestCase):
    def test_canonical_markdown_math_preserves_code_urls_and_escaped_tilde(self) -> None:
        source = (
            "Công thức ~N~ và ~~F = N + 1~~; giữ $M$ và $a~b$.\n"
            r"Dấu \~ thường, URL https://example.test/~user~/a và `~code~`." + "\n"
            "```cpp\ncout << \"~not_math~\";\n```\n"
        )

        result = problem_export.canonical_markdown_math(source)

        self.assertIn("$N$", result)
        self.assertIn("$$F = N + 1$$", result)
        self.assertIn("$M$", result)
        self.assertIn("$a~b$", result)
        self.assertIn(r"\~ thường", result)
        self.assertIn("https://example.test/~user~/a", result)
        self.assertIn("`~code~`", result)
        self.assertIn('cout << "~not_math~";', result)

    def test_hnoj_markdown_export_normalizes_all_paired_tildes(self) -> None:
        content = problem_export.one_problem_markdown(
            {
                "code": "sample",
                "name": "Bài mẫu",
                "statement": "Giá trị ~answer~ và ~x~.",
            },
            "hnoj",
        )

        self.assertIn("$answer$", content)
        self.assertIn("$x$", content)
        self.assertNotIn("~answer~", content)

    def test_pdf_detection_for_source_pdf_and_image_links(self) -> None:
        self.assertTrue(problem_export.requires_pdf({"pdf_path": "source.pdf"}))
        self.assertTrue(
            problem_export.requires_pdf(
                {"statement": "![Sơ đồ](https://example.test/diagram.png)"}
            )
        )
        self.assertTrue(
            problem_export.requires_pdf(
                {"statement": "[Xem ảnh](https://example.test/diagram.jpg)"}
            )
        )
        self.assertFalse(problem_export.requires_pdf({"statement": "Đề chỉ có văn bản."}))

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

    def test_separate_export_uses_pdf_for_pdf_problem_and_markdown_for_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_pdf = root / "source.pdf"
            pdf = canvas.Canvas(str(source_pdf))
            pdf.drawString(72, 760, "Original PDF")
            pdf.save()
            problems = [
                {
                    "code": "pdf_problem",
                    "name": "Đề PDF",
                    "statement": "",
                    "pdf_path": str(source_pdf),
                },
                {
                    "code": "text_problem",
                    "name": "Đề chữ",
                    "statement": "Nội dung chữ",
                },
            ]

            output = problem_export.write_export(
                root / "out", problems, "separate", "hncode", "HNCode"
            )

            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    archive.namelist(), ["pdf_problem.pdf", "text_problem.md"]
                )
                self.assertTrue(archive.read("pdf_problem.pdf").startswith(b"%PDF"))

    def test_combined_export_becomes_one_pdf_when_any_problem_requires_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_pdf = root / "source.pdf"
            pdf = canvas.Canvas(str(source_pdf))
            pdf.drawString(72, 760, "Original PDF")
            pdf.save()
            problems = [
                {
                    "code": "pdf_problem",
                    "name": "Đề PDF",
                    "statement": "",
                    "pdf_path": str(source_pdf),
                },
                {
                    "code": "text_problem",
                    "name": "Đề chữ",
                    "statement": "Nội dung chữ tiếng Việt",
                },
            ]

            output = problem_export.write_export(
                root / "out", problems, "combined", "hncode", "HNCode"
            )

            self.assertEqual(output.suffix, ".pdf")
            self.assertGreaterEqual(len(PdfReader(str(output)).pages), 2)

    def test_forced_markdown_exports_pdf_and_image_problems_as_markdown(self) -> None:
        problems = [
            {
                "code": "pdf_problem",
                "name": "Đề PDF",
                "statement": "",
                "pdf_url": "https://example.test/source.pdf",
            },
            {
                "code": "image_problem",
                "name": "Đề có ảnh",
                "statement": "Quan sát hình:\n\n![Hình](https://example.test/a.png)",
            },
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = problem_export.write_export(
                Path(temp),
                problems,
                "separate",
                "hncode",
                "HNCode",
                output_format="markdown",
            )
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    archive.namelist(), ["pdf_problem.md", "image_problem.md"]
                )
                pdf_markdown = archive.read("pdf_problem.md").decode("utf-8-sig")
                image_markdown = archive.read("image_problem.md").decode("utf-8-sig")
                self.assertIn(
                    "[Xem đề bài PDF gốc](https://example.test/source.pdf)",
                    pdf_markdown,
                )
                self.assertIn("![Hình](https://example.test/a.png)", image_markdown)

    def test_forced_combined_markdown_does_not_switch_to_pdf(self) -> None:
        problems = [
            {
                "code": "pdf_problem",
                "name": "Đề PDF",
                "statement": "",
                "pdf_url": "https://example.test/source.pdf",
            },
            {"code": "text_problem", "name": "Đề chữ", "statement": "Nội dung"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = problem_export.write_export(
                Path(temp),
                problems,
                "combined",
                "hncode",
                "HNCode",
                output_format="markdown",
            )
            self.assertEqual(output.suffix, ".md")
            content = output.read_text(encoding="utf-8-sig")
            self.assertIn("[Xem đề bài PDF gốc](https://example.test/source.pdf)", content)
            self.assertIn("## 2. Đề chữ (`text_problem`)", content)

    def test_image_statement_is_rendered_to_pdf(self) -> None:
        image_buffer = io.BytesIO()
        Image.new("RGB", (120, 80), "white").save(image_buffer, format="PNG")

        class ImageResponse:
            ok = True
            status_code = 200
            content = image_buffer.getvalue()

        class ImageSession:
            def get(self, _url, **_kwargs):
                return ImageResponse()

        problems = [
            {
                "code": "image_problem",
                "name": "Đề có ảnh",
                "statement": "Quan sát hình:\n\n![Hình](https://example.test/a.png)",
            }
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = problem_export.write_export(
                Path(temp),
                problems,
                "separate",
                "hncode",
                "HNCode",
                ImageSession(),
            )
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), ["image_problem.pdf"])
                self.assertTrue(archive.read("image_problem.pdf").startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
