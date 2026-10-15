"""hustoj-client: a dependency-free client for HUSTOJ-style online judges.

Scope
-----
This package covers the *read* side of an online judge only:

- watching contest/assignment listings and detecting newly published ones,
- entering a private contest with its contest password,
- fetching problem statements together with their samples.

It deliberately does not log in, submit code, or handle CAPTCHAs. Those paths
turn a useful read-only client into a tool for bypassing a judge's safeguards,
so they are out of scope by design.
"""

from ._http import DEFAULT_UA, FetchError, fetch, fetch_or_raise, new_jar, strip_tags
from .parsing import (
    SECTION_HEADS,
    parse_contest_list,
    parse_problem_detail,
    parse_problem_links,
)
from .checker import (
    build_report,
    enter_contest,
    fetch_contest_list,
    fetch_problem,
    format_report,
    print_report,
    render_markdown,
    render_text,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_UA",
    "FetchError",
    "fetch",
    "fetch_or_raise",
    "new_jar",
    "strip_tags",
    "SECTION_HEADS",
    "parse_contest_list",
    "parse_problem_detail",
    "parse_problem_links",
    "build_report",
    "enter_contest",
    "fetch_contest_list",
    "fetch_problem",
    "print_report",
    "format_report",
    "render_markdown",
    "render_text",
    "__version__",
]
