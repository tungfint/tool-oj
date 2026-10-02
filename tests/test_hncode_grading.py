from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import web_app


CONTEST_PROBLEMS = [
    {"order": 1, "code": "pabc", "title": "Tích ba số", "points": 100.0},
    {
        "order": 2,
        "code": "dtams25_demtcp",
        "title": "Tích chính phương",
        "points": 100.0,
    },
    {"order": 3, "code": "tank", "title": "Xe tăng", "points": 100.0},
    {"order": 4, "code": "dseq", "title": "Chia dãy", "points": 100.0},
    {"order": 5, "code": "bridges", "title": "Xây cầu", "points": 100.0},
]


def sample_submission_zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in ["BRIDGES.cpp", "DEMTCP.cpp", "DSEQ.cpp", "PABC.cpp", "TANK.cpp"]:
            archive.writestr(f"_BaiLam/tranhaian11/{filename}", "int main() { return 0; }")
    return output.getvalue()


class HncodeGradingTests(unittest.TestCase):
    def test_infers_student_account_and_maps_all_contest_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_zip = root / "bai_lam.zip"
            source_zip.write_bytes(sample_submission_zip())
            extract_root = root / "extract"
            web_app.safe_extract_zip(source_zip, extract_root)
            source_root = web_app.grading_source_root(extract_root)

            accounts = web_app.infer_hncode_grading_accounts(source_root)
            rows, warnings = web_app.collect_hncode_grading_files(
                source_root,
                accounts,
                CONTEST_PROBLEMS,
                submission_account="MrTee",
            )

        self.assertEqual([account["username"] for account in accounts], ["tranhaian11"])
        self.assertEqual(len(rows), 5)
        self.assertEqual(warnings, [])
        self.assertTrue(all(row["selected"] for row in rows))
        self.assertTrue(all(row["submission_account"] == "MrTee" for row in rows))
        self.assertEqual(
            {row["problem"] for row in rows},
            {"bridges", "dtams25_demtcp", "dseq", "pabc", "tank"},
        )

    def test_csv_account_can_match_folder_by_username(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source_root = Path(temp)
            student = source_root / "tranhaian11"
            student.mkdir()
            (student / "PABC.cpp").write_text("int main(){}", encoding="utf-8")
            accounts = [
                {
                    "index": 1,
                    "username": "tranhaian11",
                    "password": "secret",
                    "name": "Trần Hải An",
                }
            ]

            rows, warnings = web_app.collect_hncode_grading_files(
                source_root, accounts, CONTEST_PROBLEMS
            )

        self.assertEqual(warnings, [])
        self.assertEqual(rows[0]["student"], "Trần Hải An")
        self.assertEqual(rows[0]["submission_account"], "tranhaian11")

    def test_prepare_admin_mode_does_not_require_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with (
                patch.object(web_app, "RUNTIME", Path(temp)),
                patch.object(web_app, "login_hncode", return_value=object()),
                patch.object(
                    web_app,
                    "parse_hncode_contest_problems",
                    return_value=CONTEST_PROBLEMS,
                ),
            ):
                response = web_app.app.test_client().post(
                    "/api/prepare-hncode-grading",
                    data={
                        "contest_url": "https://hncode.edu.vn/contest/hna26_ams2_ex01",
                        "grading_mode": "admin",
                        "admin_username": "MrTee",
                        "admin_password": "not-used-by-mock",
                        "zip_file": (io.BytesIO(sample_submission_zip()), "_BaiLam.zip"),
                    },
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["grading_mode"], "admin")
        self.assertEqual(len(payload["rows"]), 5)
        self.assertTrue(all(row["submission_account"] == "MrTee" for row in payload["rows"]))

    def test_prepare_student_mode_still_requires_csv(self) -> None:
        response = web_app.app.test_client().post(
            "/api/prepare-hncode-grading",
            data={
                "contest_url": "hna26_ams2_ex01",
                "grading_mode": "student",
                "zip_file": (io.BytesIO(sample_submission_zip()), "_BaiLam.zip"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("cần file CSV", response.get_json()["error"])

    def test_confirm_admin_mode_uses_one_admin_session_for_all_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = []
            for name in ("PABC.cpp", "TANK.cpp"):
                path = root / name
                path.write_text("int main(){}", encoding="utf-8")
                files.append(path)
            rows = [
                {
                    "original_key": f"tranhaian11::{path.name}",
                    "selected": True,
                    "student": "tranhaian11",
                    "username": "tranhaian11",
                    "submission_account": "MrTee",
                    "problem": code,
                    "problem_title": code,
                    "contest_points": 100,
                    "relative_path": f"tranhaian11/{path.name}",
                    "local_path": str(path),
                    "status": "Đã chuẩn bị",
                    "submission_url": "",
                    "percent": "",
                    "score": "",
                    "message": "",
                }
                for path, code in zip(files, ("pabc", "tank"))
            ]
            prepare_id = "adminmode"
            web_app.prepared_hncode_grading[prepare_id] = {
                "root": root,
                "contest_key": "hna26_ams2_ex01",
                "contest_problems": CONTEST_PROBLEMS,
                "accounts": [
                    {
                        "index": 1,
                        "username": "tranhaian11",
                        "password": "",
                        "name": "tranhaian11",
                    }
                ],
                "rows": rows,
                "output": "",
                "grading_mode": "admin",
            }
            admin_session = object()
            with (
                patch.object(web_app, "login_hncode", return_value=admin_session) as login,
                patch.object(
                    web_app,
                    "submit_hncode_grading_file",
                    side_effect=["https://hncode.edu.vn/submission/1", "https://hncode.edu.vn/submission/2"],
                ) as submit,
                patch.object(
                    web_app,
                    "poll_hncode_submission",
                    return_value={"percent": 100.0, "verdict": "Accepted"},
                ),
                patch.object(web_app, "write_hncode_grading_excel"),
            ):
                response = web_app.app.test_client().post(
                    "/api/confirm-hncode-grading",
                    json={
                        "prepare_id": prepare_id,
                        "rows": [
                            {"original_key": row["original_key"], "selected": True}
                            for row in rows
                        ],
                        "admin_account": {"username": "MrTee", "password": "secret"},
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(login.call_count, 1)
        self.assertEqual(submit.call_count, 2)
        self.assertTrue(all(row["score"] == 100.0 for row in payload["rows"]))
        self.assertTrue(all(row["status"] == "✓ Đã chấm" for row in payload["rows"]))


if __name__ == "__main__":
    unittest.main()
