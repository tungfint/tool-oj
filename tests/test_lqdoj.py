import unittest

from services import lqdoj


class LqdojHelpersTests(unittest.TestCase):
    def test_detects_cloudflare_challenge(self):
        self.assertTrue(lqdoj.is_waf_challenge(403, {"CF-Ray": "abc"}, "Just a moment..."))
        self.assertFalse(lqdoj.is_waf_challenge(200, {}, "normal page"))

    def test_problem_and_contest_codes_are_strict_alphanumeric(self):
        self.assertEqual(lqdoj.normalize_problem_code("THT26_Bai-1"), "tht26bai1")
        self.assertEqual(lqdoj.normalize_contest_key("CK_2026-A"), "ck2026a")
        lqdoj.validate_problem_code("tht26bai1")
        lqdoj.validate_contest_key("ck2026a")
        with self.assertRaises(RuntimeError):
            lqdoj.validate_problem_code("tht26_bai1")

    def test_course_slug_uses_hyphens(self):
        self.assertEqual(lqdoj.normalize_course_slug("Khoa_Hoc C++"), "Khoa-Hoc-C")
        lqdoj.validate_course_slug("khoa-hoc-2026")
        with self.assertRaises(RuntimeError):
            lqdoj.validate_course_slug("khoa_hoc")


if __name__ == "__main__":
    unittest.main()
