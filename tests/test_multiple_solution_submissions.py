import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import web_app
from services.problem_upload import submit_if_requested
from upload_tinhoctre_batch import ProblemBundle, discover_bundles, generate_tests


def write_test_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("01.inp", "1\n")
        archive.writestr("01.out", "1\n")


class MultipleSolutionDiscoveryTests(unittest.TestCase):
    def test_existing_test_directory_is_used_without_running_generator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "demo.md").write_text("Bài mẫu | demo\nNội dung", encoding="utf-8")
            (root / "gentest_demo.py").write_text("raise RuntimeError('must not run')\n", encoding="utf-8")
            tests = root / "tests"
            tests.mkdir()
            (tests / "01.inp").write_text("1\n", encoding="utf-8")
            (tests / "01.out").write_text("1\n", encoding="utf-8")

            bundle = discover_bundles(root)[0]
            generated = generate_tests(bundle, root / "generated")

            self.assertEqual(bundle.test_directory, tests)
            self.assertEqual(generated.input_files, ["tests/01.inp"])
            self.assertEqual(generated.output_files, ["tests/01.out"])

    def test_nested_problem_test_directories_are_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            expected = {}
            for code, value in (("alpha", "1"), ("beta", "2")):
                problem = root / code
                tests = problem / "tests"
                tests.mkdir(parents=True)
                (problem / f"{code}.md").write_text(
                    f"Bài {code} | {code}\nNội dung", encoding="utf-8"
                )
                (tests / "01.inp").write_text(value + "\n", encoding="utf-8")
                (tests / "01.out").write_text(value + "\n", encoding="utf-8")
                expected[code] = tests

            bundles = {bundle.code: bundle for bundle in discover_bundles(root)}

            self.assertEqual(bundles["alpha"].test_directory, expected["alpha"])
            self.assertEqual(bundles["beta"].test_directory, expected["beta"])

    def test_flat_multi_problem_package_does_not_reuse_shared_test_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for code in ("alpha", "beta"):
                (root / f"{code}.md").write_text(f"Bài {code} | {code}\nNội dung", encoding="utf-8")
                (root / f"gentest_{code}.py").write_text(
                    "from pathlib import Path\n"
                    "p=Path('made'); p.mkdir(exist_ok=True)\n"
                    f"(p/'01.inp').write_text('{code}\\n')\n"
                    f"(p/'01.out').write_text('{code}\\n')\n",
                    encoding="utf-8",
                )
            shared = root / "tests"
            shared.mkdir()
            (shared / "01.inp").write_text("shared\n", encoding="utf-8")
            (shared / "01.out").write_text("shared\n", encoding="utf-8")

            bundles = discover_bundles(root)

            self.assertEqual(len(bundles), 2)
            self.assertTrue(all(bundle.test_directory is None for bundle in bundles))

    def test_txt_statement_and_generator_without_zip_are_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CANBANG.txt").write_text("### Bài 3. Chuỗi cân bằng\n\nNội dung", encoding="utf-8")
            (root / "README.md").write_text("# Tài liệu bộ test", encoding="utf-8")
            (root / "oracle_helper.py").write_text("ANSWER = 0\n", encoding="utf-8")
            (root / "gentest_canbang.py").write_text(
                "from pathlib import Path\n"
                "from oracle_helper import ANSWER\n"
                "p=Path('tests'); p.mkdir(exist_ok=True)\n"
                "(p/'test01.inp').write_text('a\\n')\n"
                "(p/'test01.out').write_text(str(ANSWER)+'\\n')\n"
                "open('summary.csv', 'w').write('Ghi chú: dữ liệu phụ')\n",
                encoding="utf-8",
            )
            (root / "solution_full.cpp").write_text("int main(){}", encoding="utf-8")

            bundles = discover_bundles(root)
            generated = generate_tests(bundles[0], root / "generated")

            self.assertEqual(len(bundles), 1)
            self.assertEqual(bundles[0].code.lower(), "canbang")
            self.assertEqual([path.name for path in bundles[0].all_cpp_solutions()], ["solution_full.cpp"])
            self.assertTrue(generated.zip_path.exists())
            self.assertEqual(generated.input_files, ["tests/test01.inp"])
            self.assertEqual(generated.output_files, ["tests/test01.out"])

    def test_single_problem_collects_all_generic_solution_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "demo.md").write_text("Bài mẫu | demo | 100 | implementation\nNội dung", encoding="utf-8")
            write_test_zip(root / "demo.zip")
            for name in ("solution_sub2.cpp", "solution_sub1.cpp", "solution_full.cpp", "solution_full.py"):
                (root / name).write_text("// source", encoding="utf-8")

            bundle = discover_bundles(root)[0]

            self.assertEqual(
                [path.name for path in bundle.all_cpp_solutions()],
                ["solution_full.cpp", "solution_sub1.cpp", "solution_sub2.cpp"],
            )
            self.assertEqual([path.name for path in bundle.all_python_solutions()], ["solution_full.py"])

    def test_multiple_flat_problems_do_not_share_generic_solutions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for code in ("alpha", "beta"):
                (root / f"{code}.md").write_text(f"{code} | {code}\nNội dung", encoding="utf-8")
                write_test_zip(root / f"{code}.zip")
                (root / f"solution_{code}_full.cpp").write_text("// source", encoding="utf-8")
            (root / "solution_sub1.cpp").write_text("// ambiguous", encoding="utf-8")

            bundles = {bundle.code: bundle for bundle in discover_bundles(root)}

            self.assertEqual([path.name for path in bundles["alpha"].all_cpp_solutions()], ["solution_alpha_full.cpp"])
            self.assertEqual([path.name for path in bundles["beta"].all_cpp_solutions()], ["solution_beta_full.cpp"])

    def test_submit_requested_submits_every_source_and_continues_after_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            statement = root / "demo.md"
            statement.write_text("Demo | demo", encoding="utf-8")
            sources = tuple(root / name for name in ("solution_a.cpp", "solution_b.cpp", "solution_c.cpp"))
            for source in sources:
                source.write_text("int main(){}", encoding="utf-8")
            bundle = ProblemBundle(0, "demo", "Demo", statement, None, None, None, None, None, (), sources)
            log: list[str] = []

            def fake_submit(_session, _base_url, _code, source_path, _languages, _errors):
                if source_path.name == "solution_b.cpp":
                    raise RuntimeError("fixture error")
                return f"https://hncode.edu.vn/submission/{source_path.stem}"

            with patch("services.problem_upload.submit_solution_file", side_effect=fake_submit) as mocked:
                submit_if_requested(
                    object(),
                    "https://hncode.edu.vn",
                    bundle,
                    {"submit_cpp": True, "submit_python": False, "no_submit": False},
                    log,
                    lambda _html: [],
                )

            self.assertEqual(mocked.call_count, 3)
            self.assertTrue(any("solution_b.cpp" in line and "fixture error" in line for line in log))
            self.assertTrue(any("solution_c.cpp" in line and "đã nộp" in line for line in log))


class MultipleSolutionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime_patch = patch.object(web_app, "RUNTIME", Path(self.temp.name))
        self.runtime_patch.start()
        web_app.prepared_single_uploads.clear()
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()

    def tearDown(self):
        self.runtime_patch.stop()
        self.temp.cleanup()

    def test_prepare_single_upload_accepts_multiple_submission_sources(self):
        payload = {"target": "hncode", "code": "demo", "name": "Bài mẫu", "statement_text": "Nội dung"}
        response = self.client.post(
            "/api/prepare-single-upload",
            data={
                "payload": json.dumps(payload),
                "submission_sources": [
                    (io.BytesIO(b"int main(){}"), "solution_sub1.cpp"),
                    (io.BytesIO(b"print(1)"), "solution_full.py"),
                ],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertIn("solution_sub1.cpp", data["rows"][0]["submission_files"])
        self.assertIn("solution_full.py", data["rows"][0]["submission_files"])
        bundle = web_app.prepared_single_uploads[data["prepare_id"]]["bundles"]["demo"]
        self.assertEqual(len(bundle.all_cpp_solutions()), 1)
        self.assertEqual(len(bundle.all_python_solutions()), 1)

    def test_prepare_single_upload_discovers_sources_inside_test_zip(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("tests/01.inp", "1\n")
            package.writestr("tests/01.out", "1\n")
            package.writestr("solution_sub1.cpp", "int main(){}")
            package.writestr("nested/solution_full.py", "print(1)")
        archive.seek(0)
        payload = {"target": "hncode", "code": "demo", "name": "Bài mẫu", "statement_text": "Nội dung"}

        response = self.client.post(
            "/api/prepare-single-upload",
            data={
                "payload": json.dumps(payload),
                "test_zip": (archive, "demo.zip"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertEqual(data["rows"][0]["test_count"], 1)
        self.assertIn("solution_sub1.cpp", data["rows"][0]["submission_files"])
        self.assertIn("solution_full.py", data["rows"][0]["submission_files"])


if __name__ == "__main__":
    unittest.main()
