#!/usr/bin/env python3
"""Offline demo: parse the bundled fixtures and print what the client extracts.

This makes the parsing behaviour inspectable without a judge to talk to, and it is
what docs/demo.png shows. Run it from the repository root:

    python examples/demo_parse.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hustoj_client import (  # noqa: E402
    enter_contest,
    parse_contest_list,
    parse_problem_detail,
    parse_problem_links,
)

FIXTURES = os.path.join(ROOT, "tests", "fixtures")
TEACHER = "teacher_a"


def read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def rule(label):
    print("\n" + "-" * 68)
    print(label)
    print("-" * 68)


def main():
    print("hustoj-client offline demo - no network access")

    rule("parse_contest_list(contest_list.html)")
    contests = parse_contest_list(read("contest_list.html"))
    for c in contests:
        print("  cid=%-5s %-8s %-8s %s" % (c["cid"], c["status"], c["private"], c["title"]))

    rule("filter by teacher: %r" % TEACHER)
    mine = [c for c in contests if TEACHER in c["title"]]
    for c in mine:
        print("  cid=%-5s  %s" % (c["cid"], c["title"]))
    print("  -> %d of %d assignments match" % (len(mine), len(contests)))

    rule("parse_problem_detail(problem.html)")
    info = parse_problem_detail(read("problem.html"))
    print("  label        : %s" % info["label"])
    print("  title        : %s" % info["title"])
    print("  time limit   : %s" % info["time_limit"])
    print("  memory limit : %s" % info["memory_limit"])
    print("  sections     : %s" % ", ".join(sorted(info["sections"])))

    rule("extracted sample (ready to write into tests/)")
    print("  [Sample Input]")
    for line in info["sections"]["Sample Input"].splitlines():
        print("    " + line)
    print("  [Sample Output]")
    for line in info["sections"]["Sample Output"].splitlines():
        print("    " + line)

    rule("parse_problem_links(contest page, cid)")
    contest_html = '<a href="problem.php?cid=1234&pid=0">A: Print the sum</a>'
    for p in parse_problem_links(contest_html, 1234):
        print("  pid=%s  %s" % (p["pid"], p["title"]))
    print("  (raw & and escaped &amp; are both accepted)")

    print("\nOK - parsed %d contests and 1 problem statement entirely offline."
          % len(contests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
