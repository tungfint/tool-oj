"""HNOJ parsing helpers.

HNOJ currently uses the same public contest/problem link structure as HNCode
for the parts this tool needs, but keeping this wrapper separate makes future
HTML changes cheaper to localize.
"""

from __future__ import annotations

from .hncode import extract_contest_problem_rows_from_html


def extract_contest_problem_rows_from_html_hnoj(page: str, contest_key: str = "", default_points: str = "100") -> list[dict]:
    return extract_contest_problem_rows_from_html(page, contest_key, default_points)
