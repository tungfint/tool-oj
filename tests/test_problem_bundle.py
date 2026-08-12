import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

from services import problem_bundle as bundle_service


DEFAULTS = {
    "points": "100",
    "tags": "",
    "partial": True,
    "time_limit": "1.0",
    "memory_limit": "1048576",
}


def write_zip(zip_path: Path, files: dict[str, str | bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            if isinstance(content, bytes):
                archive.writestr(name, content)
            else:
                archive.writestr(name, content)


def test_archive_bytes(code: str = "sample") -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("01.inp", "1 2\n")
        archive.writestr("01.out", "3\n")
        archive.writestr("02.inp", "2 3\n")
        archive.writestr("02.out", "5\n")
    return buffer.getvalue()


def generator_source(code: str) -> str:
    return textwrap.dedent(
        f"""
        import zipfile

        with zipfile.ZipFile("{code}.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("01.inp", "1 2\\n")
            archive.writestr("01.out", "3\\n")
        """
    ).strip() + "\n"


class ProblemBundleFormatTests(unittest.TestCase):
    def prepare(self, source_path: Path) -> dict:
        root = source_path.parent / "runtime"
        return bundle_service.prepare_multi_upload_source(source_path, root / "source", root / "generated", DEFAULTS)

    def test_standard_single_problem_zip_with_generator_and_no_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "single.zip"
            write_zip(
                zip_path,
                {
                    "tonghaiso.md": "Tổng hai số | tonghaiso | 100 | nhập xuất, toán\n\nCho a b, tính tổng.\n",
                    "gentest_tonghaiso.py": generator_source("tonghaiso"),
                },
            )

            result = self.prepare(zip_path)

        self.assertEqual(len(result["rows"]), 1)
        row = result["rows"][0]
        self.assertEqual(row["code"], "tonghaiso")
        self.assertEqual(row["name"], "Tổng hai số")
        self.assertEqual(row["points"], "100")
        self.assertEqual(row["tags"], "nhập xuất, toán")
        self.assertEqual(row["test_file"], "tonghaiso.zip")
        self.assertEqual(row["test_count"], 1)
        self.assertTrue(row["upload_tests_default"])
        self.assertFalse(row["upload_solution_default"])

    def test_multi_problem_zip_with_generator_and_existing_test_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "multi.zip"
            write_zip(
                zip_path,
                {
                    "1_tonghaiso.md": "Tổng hai số | tonghaiso | 50 | cơ bản\n\nNội dung 1.\n",
                    "gentest_1_tonghaiso.py": generator_source("tonghaiso"),
                    "2_hieuhahiso.md": "Hiệu hai số | hieuhahiso | 60 | toán\n\nNội dung 2.\n",
                    "hieuhahiso.zip": test_archive_bytes("hieuhahiso"),
                    "sol_hieuhahiso.md": "# Lời giải\n",
                },
            )

            result = self.prepare(zip_path)

        rows = {row["code"]: row for row in result["rows"]}
        self.assertEqual(set(rows), {"tonghaiso", "hieuhahiso"})
        self.assertEqual(rows["tonghaiso"]["test_count"], 1)
        self.assertEqual(rows["hieuhahiso"]["test_count"], 2)
        self.assertEqual(rows["hieuhahiso"]["test_file"], "hieuhahiso.zip")
        self.assertTrue(rows["hieuhahiso"]["upload_solution_default"])

    def test_combined_markdown_many_problems_has_metadata_and_no_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "de_tong_hop.md"
            md_path.write_text(
                textwrap.dedent(
                    """
                    # Bài 1. Tổng A | tonga | 50 | tag a

                    Nội dung bài tổng A.

                    # Bài 2. Tổng B | tongb | 70 | tag b, quy hoạch

                    Nội dung bài tổng B.
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            result = self.prepare(md_path)

        self.assertEqual([row["code"] for row in result["rows"]], ["tonga", "tongb"])
        self.assertEqual(result["rows"][0]["name"], "Tổng A")
        self.assertEqual(result["rows"][0]["points"], "50")
        self.assertEqual(result["rows"][1]["tags"], "tag b, quy hoạch")
        self.assertEqual(result["rows"][0]["test_file"], "Không có test")
        self.assertEqual(result["rows"][0]["test_count"], 0)
        self.assertFalse(result["rows"][0]["upload_tests_default"])

    def test_statement_metadata_header_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            statement = Path(tmp) / "meta.md"
            statement.write_text("Tên bài | ma_bai | 80 | tham lam, mảng\n\nNội dung.\n", encoding="utf-8")

            meta = bundle_service.metadata_from_statement(statement, DEFAULTS)

        self.assertEqual(meta["points"], "80")
        self.assertEqual(meta["tags"], "tham lam, mảng")
        self.assertTrue(meta["partial"])

    def test_missing_test_source_reports_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "missing_test.zip"
            write_zip(zip_path, {"khongtest.md": "Không test | khongtest | 100 | thử\n\nNội dung.\n"})

            with self.assertRaisesRegex(RuntimeError, "Missing test source for khongtest"):
                self.prepare(zip_path)

    def test_existing_test_zip_missing_output_reports_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_test = Path(tmp) / "bad.zip"
            write_zip(bad_test, {"01.inp": "1 2\n"})
            zip_path = Path(tmp) / "bad_bundle.zip"
            write_zip(
                zip_path,
                {
                    "badtest.md": "Bad test | badtest | 100 | test\n\nNội dung.\n",
                    "badtest.zip": bad_test.read_bytes(),
                },
            )

            with self.assertRaisesRegex(RuntimeError, "missing output files"):
                self.prepare(zip_path)


if __name__ == "__main__":
    unittest.main()
