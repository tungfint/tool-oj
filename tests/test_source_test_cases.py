import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

from transfer_tinhoctre_to_hncode import infer_cases_from_zip_archive, parse_source_cases


class SourceTestCaseParserTests(TestCase):
    def test_reads_selected_file_names_from_select_fields(self):
        page = """
        <input name="cases-0-order" value="1">
        <select name="cases-0-type"><option value="C" selected>Case</option></select>
        <select name="cases-0-input_file"><option value="1.in" selected>1.in</option></select>
        <select name="cases-0-output_file"><option value="1.out" selected>1.out</option></select>
        <input name="cases-0-points" value="2">
        """
        cases = parse_source_cases(page)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].input_file, "1.in")
        self.assertEqual(cases[0].output_file, "1.out")
        self.assertEqual(cases[0].points, "2")

    def test_infers_naturally_sorted_pairs_from_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "tests.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                for stem in ("10", "2", "1"):
                    archive.writestr(f"tests/{stem}.in", stem)
                    archive.writestr(f"tests/{stem}.out", stem)
            cases = infer_cases_from_zip_archive(archive_path)
        self.assertEqual([case.input_file for case in cases], ["tests/1.in", "tests/2.in", "tests/10.in"])
        self.assertEqual([case.output_file for case in cases], ["tests/1.out", "tests/2.out", "tests/10.out"])
