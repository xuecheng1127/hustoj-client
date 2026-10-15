"""Offline tests: no network access is required or performed.

Fixtures are minimal reproductions of the markup emitted by a Bootstrap-based
HUSTOJ theme. Run with:

    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hustoj_client import (  # noqa: E402
    build_report,
    parse_contest_list,
    parse_problem_detail,
    parse_problem_links,
    strip_tags,
)
from hustoj_client._http import FETCH_ERROR_PREFIX, fetch  # noqa: E402
from hustoj_client.checker import resolve_teachers  # noqa: E402
from hustoj_client.config import mask  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
