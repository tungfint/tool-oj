from pathlib import Path
import unittest

from services import hncode, hnoj


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class ParserTests(unittest.TestCase):
    def test_parse_hncode_old_problem_links(self):
        rows = hncode.extract_contest_problem_rows_from_html(fixture("hncode_contest_old.html"), "old_contest")

        self.assertEqual([row["code"] for row in rows], ["old_sum", "old_array"])
        self.assertEqual([row["title"] for row in rows], ["Tổng hai số", "Mảng đẹp"])
        self.assertEqual([row["points"] for row in rows], ["100", "80"])

    def test_parse_hncode_new_contest_problem_links(self):
        rows = hncode.extract_contest_problem_rows_from_html(fixture("hncode_contest_new.html"), "tht26_a")

        self.assertEqual([row["code"] for row in rows], ["new_square", "new_path"])
        self.assertEqual([row["title"] for row in rows], ["Hình vuông số", "Đường đi"])
        self.assertEqual([row["points"] for row in rows], ["60", "40"])

    def test_parse_hncode_ranking_problem_codes(self):
        rows = hncode.extract_contest_problem_rows_from_html(fixture("hncode_ranking.html"), "rank_contest")

        self.assertEqual([row["code"] for row in rows], ["rank_a", "rank_b"])
        self.assertEqual([row["title"] for row in rows], ["Bài A", "Bài B"])
        self.assertEqual([row["points"] for row in rows], ["100", "50"])

    def test_parse_hncode_lesson_problem_codes(self):
        rows = hncode.extract_problem_link_rows_from_html(fixture("hncode_lesson.html"), "")

        self.assertEqual([row["code"] for row in rows], ["lesson_one", "lesson_two"])
        self.assertEqual([row["title"] for row in rows], ["Bài lesson 1", "Bài lesson 2"])

    def test_parse_hnoj_contest_problem_codes(self):
        rows = hnoj.extract_contest_problem_rows_from_html_hnoj(fixture("hnoj_contest.html"), "hnoj_round")

        self.assertEqual([row["code"] for row in rows], ["hnoj_alpha", "hnoj_beta"])
        self.assertEqual([row["title"] for row in rows], ["Alpha", "Beta"])
        self.assertEqual([row["points"] for row in rows], ["100", "75"])


if __name__ == "__main__":
    unittest.main()
