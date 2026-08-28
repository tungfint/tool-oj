import tempfile
import unittest
import zipfile
from pathlib import Path

from upload_tinhoctre_batch import discover_bundles


def write_test_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("01.inp", "1 2\n")
        archive.writestr("01.out", "3\n")


class ProblemBundlePdfTests(unittest.TestCase):
    def test_pdf_only_problem_uses_default_metadata_statement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "demo.pdf").write_bytes(b"%PDF-1.7\nfixture")
            write_test_zip(root / "demo.zip")

            bundles = discover_bundles(root)

            self.assertEqual(len(bundles), 1)
            self.assertEqual(bundles[0].code, "demo")
            self.assertEqual(bundles[0].pdf_statement.name, "demo.pdf")
            self.assertTrue(bundles[0].statement.is_file())

    def test_markdown_and_pdf_are_paired(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "1_demo.md").write_text("Bài mẫu | demo | 100 | Chưa phân loại\nNội dung\n", encoding="utf-8")
            (root / "1_demo.pdf").write_bytes(b"%PDF-1.7\nfixture")
            write_test_zip(root / "demo.zip")

            bundles = discover_bundles(root)

            self.assertEqual(len(bundles), 1)
            self.assertEqual(bundles[0].name, "Bài mẫu")
            self.assertEqual(bundles[0].pdf_statement.name, "1_demo.pdf")


if __name__ == "__main__":
    unittest.main()
