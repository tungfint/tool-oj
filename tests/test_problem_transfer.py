from pathlib import Path
import unittest

from services import problem_transfer
from transfer_tinhoctre_to_hncode import ProblemInfo, TestCase


class ProblemTransferTests(unittest.TestCase):
    def test_make_prepare_transfer_row(self):
        info = ProblemInfo(
            code="abc_1",
            name="Bài ABC",
            description="Đề bài",
            points="100",
            partial=True,
            time_limit="2.0",
            memory_limit="2048",
            memory_unit="KB",
        )
        cases = [TestCase(1, "C", "01.inp", "01.out", "100")]

        row = problem_transfer.make_prepare_transfer_row(
            original_code="ABC_1",
            info=info,
            zip_path=Path("abc_1.zip"),
            cases=cases,
            source_base_url="https://hnoj.edu.vn",
            dest="hncode",
            settings={},
            normalize_problem_code_for_target=lambda code, target: code.lower(),
            test_data_url=lambda base, code: f"{base}/problem/{code}/test_data",
        )

        self.assertEqual(row["code"], "abc_1")
        self.assertEqual(row["name"], "Bài ABC")
        self.assertEqual(row["time_limit"], "2.0")
        self.assertEqual(row["memory_limit"], "2048")
        self.assertEqual(row["test_count"], 1)
        self.assertEqual(row["status"], "Đã đọc")

    def test_make_failed_prepare_transfer_row(self):
        row = problem_transfer.make_failed_prepare_transfer_row(
            code="missing",
            source_base_url="https://hnoj.edu.vn",
            settings={"time_limit": "1.5", "memory_limit": "1024"},
            test_data_url=lambda base, code: f"{base}/problem/{code}/test_data",
        )

        self.assertEqual(row["code"], "missing")
        self.assertEqual(row["time_limit"], "1.5")
        self.assertEqual(row["memory_limit"], "1024")
        self.assertEqual(row["test_count"], 0)
        self.assertIn("Lỗi", row["status"])

    def test_apply_transfer_row_to_info(self):
        info = ProblemInfo(
            code="abc",
            name="Tên cũ",
            description="Đề bài",
            points="100",
            partial=True,
            time_limit="1.0",
            memory_limit="1048576",
            memory_unit="KB",
        )

        problem_transfer.apply_transfer_row_to_info(
            info,
            {"name": "Tên mới", "time_limit": "3.0", "memory_limit": "4096"},
            {},
        )

        self.assertEqual(info.name, "Tên mới")
        self.assertEqual(info.time_limit, "3.0")
        self.assertEqual(info.memory_limit, "4096")


if __name__ == "__main__":
    unittest.main()
