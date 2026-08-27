from __future__ import annotations

import tempfile
import unittest
import zipfile
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import unquote

from services.last_submissions import (
    SubmissionArchiveEntry,
    SubmissionMetadata,
    parse_submission_filename,
    parse_submission_page,
    read_submission_archive,
    read_submission_package,
    select_latest_submissions,
    write_result_archive,
)


class LastSubmissionsTest(unittest.TestCase):
    def test_parse_submission_filename(self):
        parsed = parse_submission_filename("folder/1937_CK26C102.CPP20")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.submission_id, 1937)
        self.assertEqual(parsed.username, "CK26C102")
        self.assertEqual(parsed.language, "CPP20")
        exported = parse_submission_filename("sources/CK26D107__sub1430__CE_0.sb3")
        self.assertIsNotNone(exported)
        self.assertEqual(exported.submission_id, 1430)
        self.assertEqual(exported.username, "CK26D107")
        self.assertEqual(exported.language, "sb3")
        self.assertIsNone(parse_submission_filename("readme.txt"))

    def test_read_manifest_export_package(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_zip = Path(temp_dir) / "export-problem.zip"
            manifest = {
                "problem": {"code": "26tq_debai_d1", "name": "Đề bài D1"},
                "exported_count": 3,
                "submissions": [
                    {"submission_id": 10, "username": "alice", "file": "alice__sub10__WA_0.sb3"},
                    {"submission_id": 12, "username": "alice", "file": "alice__sub12__AC_100.sb3"},
                    {"submission_id": 11, "username": "bob", "file": "bob__sub11__CE_0.py"},
                ],
            }
            with zipfile.ZipFile(source_zip, "w") as archive:
                archive.writestr("export/submissions.json", json.dumps(manifest, ensure_ascii=False))
                archive.writestr("export/submissions.csv", "submission_id,username,file\n")
                archive.writestr("export/sources/alice__sub10__WA_0.sb3", "old")
                archive.writestr("export/sources/alice__sub12__AC_100.sb3", "latest")
                archive.writestr("export/sources/bob__sub11__CE_0.py", "print(1)")

            package = read_submission_package(source_zip)
            self.assertEqual(len(package.entries), 3)
            self.assertEqual(package.metadata_by_id[12].problem_code, "26tq_debai_d1")
            selected, unresolved = select_latest_submissions(package.entries, package.metadata_by_id)
            self.assertFalse(unresolved)
            self.assertEqual([item.entry.submission_id for item in selected], [12, 11])

    def test_read_csv_only_export_package(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_zip = Path(temp_dir) / "export-26tq_debai_d1.zip"
            csv_text = (
                "submission_id,username,language,file\n"
                "10,alice,SCRATCH,alice__sub10__WA_0.sb3\n"
                "12,alice,SCRATCH,alice__sub12__AC_100.sb3\n"
            )
            with zipfile.ZipFile(source_zip, "w") as archive:
                archive.writestr("export/submissions.json", "{invalid json")
                archive.writestr("export/submissions.csv", csv_text)
                archive.writestr("export/sources/alice__sub10__WA_0.sb3", "old")
                archive.writestr("export/sources/alice__sub12__AC_100.sb3", "latest")

            package = read_submission_package(source_zip)
            self.assertEqual(len(package.entries), 2)
            self.assertEqual(package.metadata_by_id[12].problem_code, "26tq_debai_d1")

    def test_parse_submission_page(self):
        page = """
        <html><head><title>Submission</title></head><body>
          <a href="/user/CK26C102">CK26C102</a>
          <a href="/problem/26tq_debai_c1">THT26 Toàn Quốc - Đề bài C1</a>
        </body></html>
        """
        metadata = parse_submission_page(page, 1937)
        self.assertEqual(metadata.problem_code, "26tq_debai_c1")
        self.assertEqual(metadata.problem_name, "THT26 Toàn Quốc - Đề bài C1")

    def test_select_latest_for_each_account_and_problem(self):
        entries = [
            SubmissionArchiveEntry("10_alice.CPP17", 10, "alice", "CPP17"),
            SubmissionArchiveEntry("12_alice.CPP20", 12, "alice", "CPP20"),
            SubmissionArchiveEntry("14_alice.PY3", 14, "alice", "PY3"),
            SubmissionArchiveEntry("13_bob.CPP17", 13, "bob", "CPP17"),
            SubmissionArchiveEntry("15_bob.CPP17", 15, "bob", "CPP17"),
        ]
        metadata = {
            10: SubmissionMetadata(10, "sum"),
            12: SubmissionMetadata(12, "sum"),
            14: SubmissionMetadata(14, "graph"),
            13: SubmissionMetadata(13, "sum"),
            15: SubmissionMetadata(15, "sum"),
        }
        selected, unresolved = select_latest_submissions(entries, metadata)
        self.assertFalse(unresolved)
        selected_ids = {
            (item.entry.username, item.metadata.problem_code): item.entry.submission_id
            for item in selected
        }
        self.assertEqual(
            selected_ids,
            {("alice", "sum"): 12, ("alice", "graph"): 14, ("bob", "sum"): 15},
        )

    def test_read_and_write_result_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_zip = root / "submissions.zip"
            output_zip = root / "last_submissions.zip"
            with zipfile.ZipFile(source_zip, "w") as archive:
                archive.writestr("10_alice.CPP17", "old")
                archive.writestr("12_alice.CPP20", "latest")
                archive.writestr("README.txt", "ignored")

            entries = read_submission_archive(source_zip)
            self.assertEqual([entry.submission_id for entry in entries], [10, 12])
            metadata = {
                10: SubmissionMetadata(10, "sum", "Tổng"),
                12: SubmissionMetadata(12, "sum", "Tổng"),
            }
            selected, unresolved = select_latest_submissions(entries, metadata)
            summary = write_result_archive(source_zip, output_zip, selected, unresolved)

            self.assertEqual(summary["selected"], 1)
            with zipfile.ZipFile(output_zip) as archive:
                self.assertEqual(archive.read("alice/sum.CPP20"), b"latest")
                report = archive.read("report.csv").decode("utf-8-sig")
            self.assertIn("alice,sum,Tổng,12,CPP20", report)

    def test_flask_endpoint_returns_result_zip(self):
        from web_app import app

        source = BytesIO()
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("10_alice.CPP17", "old")
            archive.writestr("12_alice.CPP20", "latest")
        source.seek(0)
        metadata = {
            10: SubmissionMetadata(10, "sum", "Tổng"),
            12: SubmissionMetadata(12, "sum", "Tổng"),
        }
        with (
            patch("web_app.login_upload_target", return_value=MagicMock()),
            patch(
                "web_app.last_submissions_service.resolve_submission_metadata",
                return_value=(metadata, {}),
            ),
        ):
            response = app.test_client().post(
                "/api/misc/last-submissions",
                data={
                    "source": "hncode",
                    "account": '{"username":"test","password":"test"}',
                    "zip_file": (source, "submissions.zip"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 200)
        summary = unquote(response.headers["X-Last-Submissions-Summary"])
        self.assertIn('"selected": 1', summary)
        payload = response.get_data()
        response.close()
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            self.assertEqual(archive.read("alice/sum.CPP20"), b"latest")


if __name__ == "__main__":
    unittest.main()
