import unittest
from pathlib import Path
from unittest.mock import Mock

from services import problem_upload
from transfer_tinhoctre_to_hncode import test_data_base_fields
from upload_tinhoctre_batch import GeneratedTests


class FileIoUploadTests(unittest.TestCase):
    def test_infer_fileio_names_from_statement(self):
        statement = """
        Bài dùng file `DIVNUM.INP`.
        Kết quả ghi ra file `DIVNUM.OUT`.
        """

        self.assertEqual(problem_upload.infer_fileio_names(statement), ("DIVNUM.INP", "DIVNUM.OUT"))

    def test_infer_fileio_names_returns_empty_for_stdio(self):
        statement = "Dữ liệu nhập từ bàn phím, kết quả in ra màn hình."

        self.assertEqual(problem_upload.infer_fileio_names(statement), ("", ""))

    def test_test_data_base_fields_accepts_fileio_override(self):
        page = """
        <input name="cases-MIN_NUM_FORMS" value="0">
        <input name="cases-MAX_NUM_FORMS" value="1000">
        <select name="problem-data-checker"><option value="standard" selected>standard</option></select>
        <input name="problem-data-fileio_input" value="">
        <input name="problem-data-fileio_output" value="">
        <input name="problem-data-output_zip_size_mb" value="">
        <input name="problem-data-communication_num_processes" value="">
        <input name="problem-data-generator_script" value="">
        <input name="problem-data-checker_args" value="">
        """

        data = test_data_base_fields(
            page,
            "csrf",
            cases_total=0,
            fileio_input="DIVNUM.INP",
            fileio_output="DIVNUM.OUT",
        )

        self.assertIn(("problem-data-fileio_input", "DIVNUM.INP"), data)
        self.assertIn(("problem-data-fileio_output", "DIVNUM.OUT"), data)

    def test_upload_tests_for_hncode_passes_fileio_names(self):
        tests = GeneratedTests(Path("tests.zip"), ["01.inp"], ["01.out"])
        upload_hncode_tests = Mock(return_value="ok")

        problem_upload.upload_tests_for_target(
            object(),
            "hncode",
            "https://hncode.edu.vn",
            "divnum",
            tests,
            upload_hncode_tests,
            Mock(),
            statement="Đọc file DIVNUM.INP và ghi file DIVNUM.OUT.",
        )

        kwargs = upload_hncode_tests.call_args.kwargs
        self.assertEqual(kwargs["fileio_input"], "DIVNUM.INP")
        self.assertEqual(kwargs["fileio_output"], "DIVNUM.OUT")


if __name__ == "__main__":
    unittest.main()

