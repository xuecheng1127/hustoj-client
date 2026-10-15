"""Offline tests: no network access is required or performed.

Fixtures are minimal reproductions of the markup emitted by a Bootstrap-based
HUSTOJ theme. Run with:

    python -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hustoj_client import (  # noqa: E402
    build_report,
    parse_contest_list,
    parse_problem_detail,
    parse_problem_links,
    strip_tags,
)
from hustoj_client._http import FETCH_ERROR_PREFIX, fetch  # noqa: E402
from hustoj_client.checker import (  # noqa: E402
    render_markdown,
    render_text,
    resolve_teachers,
)
from hustoj_client.checker import format_report  # noqa: E402
from hustoj_client.config import mask  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

CONTEST_LIST_HTML = """
<table class="table table-striped">
  <thead><tr><th>#</th><th>Title</th><th>Status</th><th>Private</th><th>Creator</th></tr></thead>
  <tbody>
    <tr>
      <td>1</td>
      <td><a href="contest.php?cid=1766">Data Structures Homework 1</a></td>
      <td>Running</td>
      <td>Private</td>
      <td>teacher_a</td>
    </tr>
    <tr>
      <td>2</td>
      <td><a href="contest.php?cid=1767">Unrelated Practice</a></td>
      <td>Ended</td>
      <td>Public</td>
      <td>teacher_b</td>
    </tr>
    <tr>
      <td>3</td>
      <td>plain text row with no link</td>
      <td>-</td>
    </tr>
  </tbody>
</table>
"""

#: HUSTOJ emits raw ampersands here; some themes escape them as &amp; instead.
#: Both spellings must resolve to the same problems.
CONTEST_PAGE_HTML = """
<div class="panel-body">
  <a href="problem.php?cid=1766&pid=0">A: Create list</a>
  <a href="problem.php?cid=1766&pid=1">B: Find nearest</a>
  <!-- the same link appears again in the footer nav; it must not be duplicated -->
  <a href="problem.php?cid=1766&pid=1">B: Find nearest</a>
</div>
"""

CONTEST_PAGE_HTML_ESCAPED = CONTEST_PAGE_HTML.replace("&pid=", "&amp;pid=")

PROBLEM_HTML = """
<div class="panel panel-default">
  <div class="panel-heading"><h3>Problem A: Create list &amp; print it</h3>
    <span>Time Limit: 1 Sec</span> <span>Memory Limit: 128 MB</span>
  </div>
  <div class="panel-body">
    <h4>Description</h4>
    <div class="panel-body">Read n integers and print their sum.</div>
    <h4>Input</h4>
    <div class="panel-body">The first line contains n (1 &lt;= n &lt;= 1000).</div>
    <h4>Output</h4>
    <div class="panel-body">Print the sum.</div>
    <h4>Sample Input</h4>
    <div class="panel-body">3
1 2 3</div>
    <h4>Sample Output</h4>
    <div class="panel-body">6</div>
  </div>
</div>
"""


class TestStripTags(unittest.TestCase):
    def test_removes_scripts_and_entities(self):
        out = strip_tags("<p>a &amp; b</p><script>var x = 1 < 2;</script>")
        self.assertEqual(out, "a & b")

    def test_keeps_inner_text_of_nested_tags(self):
        self.assertEqual(strip_tags("<b>bold</b> tail"), "bold tail")


class TestParseContestList(unittest.TestCase):
    def setUp(self):
        self.contests = parse_contest_list(CONTEST_LIST_HTML)

    def test_only_linked_rows_are_returned(self):
        self.assertEqual([c["cid"] for c in self.contests], ["1766", "1767"])

    def test_row_fields_are_extracted(self):
        first = self.contests[0]
        self.assertEqual(first["title"], "Data Structures Homework 1")
        self.assertEqual(first["status"], "Running")
        self.assertEqual(first["private"], "Private")
        self.assertEqual(first["creator"], "teacher_a")


class TestParseProblemLinks(unittest.TestCase):
    def test_links_are_found_and_deduplicated(self):
        probs = parse_problem_links(CONTEST_PAGE_HTML, 1766)
        self.assertEqual([p["pid"] for p in probs], ["0", "1"])
        self.assertEqual(probs[0]["title"], "A: Create list")

    def test_links_for_another_contest_are_ignored(self):
        self.assertEqual(parse_problem_links(CONTEST_PAGE_HTML, 999), [])

    def test_html_escaped_ampersands_are_accepted(self):
        probs = parse_problem_links(CONTEST_PAGE_HTML_ESCAPED, 1766)
        self.assertEqual([p["pid"] for p in probs], ["0", "1"])


class TestParseProblemDetail(unittest.TestCase):
    def setUp(self):
        self.info = parse_problem_detail(PROBLEM_HTML)

    def test_label_and_title(self):
        self.assertEqual(self.info["label"], "A")
        self.assertEqual(self.info["title"], "Create list & print it")

    def test_limits(self):
        self.assertEqual(self.info["time_limit"], "1 Sec")
        self.assertEqual(self.info["memory_limit"], "128 MB")

    def test_sections(self):
        s = self.info["sections"]
        self.assertEqual(s["Description"], "Read n integers and print their sum.")
        self.assertEqual(s["Input"], "The first line contains n (1 <= n <= 1000).")
        self.assertEqual(s["Sample Output"], "6")


class TestResolveTeachers(unittest.TestCase):
    def test_prefers_list_field(self):
        self.assertEqual(resolve_teachers({"teachers": ["A", "B"], "teacher_filter": "C"}), ["A", "B"])

    def test_falls_back_to_legacy_scalar(self):
        self.assertEqual(resolve_teachers({"teacher_filter": "C"}), ["C"])

    def test_accepts_a_bare_string(self):
        self.assertEqual(resolve_teachers({"teachers": "A"}), ["A"])

    def test_placeholder_when_nothing_is_configured(self):
        self.assertEqual(resolve_teachers({}), ["<teacher-name>"])


class TestMask(unittest.TestCase):
    def test_masks_length_and_hides_value(self):
        masked = mask("hunter2")
        self.assertNotIn("hunter2", masked)
        self.assertIn("7 chars", masked)

    def test_empty_is_reported(self):
        self.assertEqual(mask(""), "(empty)")


class TestFetchIsOfflineSafe(unittest.TestCase):
    def test_unreachable_host_returns_marker_not_exception(self):
        body = fetch("http://127.0.0.1:9/never-listening", timeout=1)
        self.assertTrue(body.startswith(FETCH_ERROR_PREFIX), body)

    def test_build_report_survives_a_dead_host(self):
        cfg = {"base_url": "http://127.0.0.1:9", "teachers": ["A"], "max_pages": 1,
               "fetch_problems": False, "request_timeout": 1}
        report = build_report(cfg, state_path=None, timeout=1)
        self.assertEqual(report["new_count"], 0)
        self.assertEqual(report["total_found"], 0)

    def test_build_report_does_not_write_state_when_path_is_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cfg = {"base_url": "http://127.0.0.1:9", "teachers": ["A"], "max_pages": 1,
                   "fetch_problems": False, "request_timeout": 1}
            build_report(cfg, state_path=None, timeout=1)
            self.assertEqual(os.listdir(d), [])


def _sample_report(new_count=1, known=None):
    """Build a report dict shaped exactly like build_report() returns."""
    report = {
        "checked_at": "2026-01-01 09:00:00",
        "teacher": "teacher_a",
        "teachers": ["teacher_a"],
        "total_found": 2,
        "new_count": new_count,
        "new": [],
        "known": known if known is not None else [],
    }
    if new_count:
        report["new"] = [{
            "contest": {
                "cid": "1234",
                "title": "Data Structures - Assignment 3",
                "status": "Running",
                "private": "Private",
                "creator": "teacher_a",
            },
            "problem_count": 1,
            "problems": [{
                "pid": "0",
                "title": "Print the sum",
                "info": {
                    "label": "A",
                    "title": "Print the sum",
                    "time_limit": "1 Sec",
                    "memory_limit": "128 MB",
                    "url": "http://oj.example.edu.cn/problem.php?cid=1234&pid=0",
                    "sections": {
                        "Description": "Read n integers and print their sum.",
                        "Sample Input": "3\n1 2 3",
                        "Sample Output": "6",
                    },
                },
            }],
        }]
    return report


class TestRenderText(unittest.TestCase):
    def test_reports_new_assignment(self):
        out = render_text(_sample_report())
        self.assertIn("1 new.", out)
        self.assertIn("cid      : 1234", out)
        self.assertIn("[Problem A] Print the sum", out)
        self.assertIn("1 Sec / 128 MB", out)
        self.assertIn("--- Sample Output ---", out)

    def test_reports_no_new_assignments(self):
        out = render_text(_sample_report(new_count=0))
        self.assertIn("No new assignments.", out)

    def test_lists_known_assignments_when_present(self):
        known = [{"cid": "1231", "title": "Assignment 2", "status": "Ended"}]
        out = render_text(_sample_report(new_count=0, known=known))
        self.assertIn("Already seen:", out)
        self.assertIn("cid=1231", out)


class TestRenderMarkdown(unittest.TestCase):
    def test_structure(self):
        out = render_markdown(_sample_report(), base_url="http://oj.example.edu.cn")
        self.assertIn("# OJ assignment report", out)
        self.assertIn("## New: Data Structures - Assignment 3", out)
        self.assertIn("### Problem A: Print the sum", out)
        self.assertIn("Time / memory: 1 Sec / 128 MB", out)
        self.assertIn("contest.php?cid=1234", out)
        self.assertIn("Read n integers and print their sum.", out)

    def test_no_new_assignments(self):
        out = render_markdown(_sample_report(new_count=0))
        self.assertIn("No new assignments.", out)

    def test_works_without_a_base_url(self):
        out = render_markdown(_sample_report(), base_url="")
        self.assertIn("Contest cid:", out)
        self.assertIn("1234", out)
        self.assertNotIn("](http", out)


class TestFormatReport(unittest.TestCase):
    def test_json_is_valid_json(self):
        import json as _json
        out = format_report(_sample_report(), "json")
        self.assertEqual(_json.loads(out)["teacher"], "teacher_a")

    def test_markdown_and_text_are_distinct(self):
        md = format_report(_sample_report(), "markdown")
        txt = format_report(_sample_report(), "text")
        self.assertIn("# OJ assignment report", md)
        self.assertNotIn("# OJ assignment report", txt)


class TestBuildReportIncludeKnown(unittest.TestCase):
    """include_known must actually drop already-seen entries, not just be ignored.

    fetch_contest_list is patched with fixture data so this runs offline and
    produces a non-empty known list -- otherwise the assertion would be vacuous.
    """

    def _cfg(self):
        return {"base_url": "http://oj.example.edu.cn", "teachers": ["teacher_a"],
                "max_pages": 1, "fetch_problems": False, "request_timeout": 1}

    def _fixture_contests(self):
        with open(os.path.join(FIXTURES, "contest_list.html"), encoding="utf-8") as f:
            return parse_contest_list(f.read())

    def test_known_is_populated_when_requested(self):
        import tempfile
        contests = self._fixture_contests()
        self.assertGreaterEqual(len(contests), 2)
        with tempfile.TemporaryDirectory() as d:
            state_file = os.path.join(d, "state.json")
            # mark the older matching contest as already seen
            seen_cid = [c for c in contests if "Assignment 2" in c["title"]][0]["cid"]
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"seen": {seen_cid: "old"}}, f)
            with mock.patch("hustoj_client.checker.fetch_contest_list",
                            return_value=contests):
                report = build_report(self._cfg(), state_path=state_file, timeout=1)
        self.assertEqual([k["cid"] for k in report["known"]], [seen_cid])
        self.assertEqual([n["contest"]["cid"] for n in report["new"]], ["1234"])

    def test_include_known_false_empties_only_the_known_list(self):
        import tempfile
        contests = self._fixture_contests()
        with tempfile.TemporaryDirectory() as d:
            state_file = os.path.join(d, "state.json")
            seen_cid = [c for c in contests if "Assignment 2" in c["title"]][0]["cid"]
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"seen": {seen_cid: "old"}}, f)
            with mock.patch("hustoj_client.checker.fetch_contest_list",
                            return_value=contests):
                report = build_report(self._cfg(), state_path=state_file, timeout=1,
                                     include_known=False)
        self.assertEqual(report["known"], [])
        # the new list must be unaffected by the flag
        self.assertEqual([n["contest"]["cid"] for n in report["new"]], ["1234"])


if __name__ == "__main__":
    unittest.main()
