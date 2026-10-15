# hustoj-client

A dependency-free Python client for **HUSTOJ**-style online judges.

It watches the assignment/contest listing for newly published work, enters
private contests, and fetches problem statements together with their samples —
as plain Python objects or structured JSON.

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](#why-zero-dependencies)

---

## Why this exists

HUSTOJ is one of the most widely deployed open-source online judges, and it has
**no public API**. Everything is server-rendered HTML with Bootstrap panels, so
any tool built on top of it re-implements the same fragile scraping logic and
hits the same undocumented behaviours:

- the assignment list is public, but private contests need a *separate* contest password,
- problem statements are split across `panel-heading` / `h4` / `panel-body` structures,
- HTML entities and raw ampersands are used inconsistently across themes,
- an empty `CookieJar` is falsy, which silently destroys the session.

This package is a clean, documented implementation of that read path, so you do
not have to rediscover it. It is around 500 lines of standard library code and
it has no third-party dependencies.

## What it does (and deliberately does not)

| Capability | Supported |
|---|---|
| Watch the contest list and detect newly published assignments | ✅ |
| Persist a seen-contest state file so reruns only report what is new | ✅ |
| Enter a private contest with its contest password | ✅ |
| Fetch problem statements, limits and samples as JSON | ✅ |
| Filter assignments by teacher name | ✅ |
| Log in to an account | ❌ |
| Submit solutions | ❌ |
| Solve or bypass CAPTCHAs | ❌ |

The last three rows are **out of scope by design**. They are what turn a useful
read-only client into a tool for defeating a judge's safeguards. Please keep any
fork on the read side.

## Quick start

No installation step is required — the standard library is the only dependency.

```bash
git clone https://github.com/<your-github-username>/hustoj-client.git
cd hustoj-client

# 1. create your config (never commit this file)
cp examples/config.example.json config.json

# 2. fill in your judge URL and teacher name
python -m hustoj_client config set base_url "http://your-oj-host"
python -m hustoj_client config set teachers "Prof. Smith"
python -m hustoj_client config show

# 3. scan for new assignments
python -m hustoj_client check --report text
```

A first run reports every matching assignment as new and writes them to
`state.json`. Every later run reports only what appeared since. Use `--report json`
or `--json-out report.json` for machine-readable output.

To scan without writing any state at all:

```bash
python -m hustoj_client check --state "" --report text
```

## Using it as a library

```python
from hustoj_client import build_report, load_config

cfg = load_config("config.json")
report = build_report(cfg, state_path="state.json")

for item in report["new"]:
    contest = item["contest"]
    print(contest["cid"], contest["title"])
    for problem in item["problems"]:
        info = problem["info"]
        print(" ", info["label"], info["title"], info["time_limit"])
        print(info["sections"].get("Sample Input"))
```

Lower-level pieces are exported too, if you only want one of them:

```python
from hustoj_client import (
    enter_contest,        # (base_url, cid, contest_password) -> (html, cookie_jar)
    parse_problem_links,  # (contest_html, cid) -> [{"pid", "title"}, ...]
    parse_problem_detail, # (problem_html) -> {"label", "title", "time_limit", "sections", ...}
    fetch_problem,        # (base_url, cid, pid, cookie_jar) -> html
)
```

## Configuration

All personal values live in a single `config.json` so nothing has to be edited
inside code. Secrets are masked when printed; add `--reveal` to see them.

| Key | Meaning |
|---|---|
| `base_url` | Judge root URL, without a trailing slash |
| `teachers` | List of teacher names to match against contest titles |
| `teacher_filter` | Legacy single-name form, still honoured |
| `contest_password` | Password for entering private contests (masked on output) |
| `max_pages` | How many listing pages to scan |
| `fetch_problems` | Whether to download statements and samples |
| `request_timeout` | Per-request socket timeout in seconds |
| `state_file` | Where the seen-contest map is persisted |

```bash
python -m hustoj_client config show
python -m hustoj_client config get teachers
python -m hustoj_client config set max_pages 5
python -m hustoj_client config set teachers "Alice,Bob"
```

## HUSTOJ protocol notes

These are the behaviours that cost real debugging time. They are documented here
because none of them are written down upstream.

### Two different passwords

A *private contest* is unlocked with the **contest password**, posted as
`password` to `contest.php?cid=<cid>`. Account credentials are not involved at all.
Getting the two confused is the usual reason a private contest appears empty.

### The session must survive between requests

After entering the contest you get a `PHPSESSID` cookie, and the problem pages are
only reachable with the same jar. `http.cookiejar.CookieJar` defines `__len__`, so
an **empty jar is falsy**. The obvious-looking helper

```python
jar = cookie_jar or CookieJar()   # BUG: silently drops the session
```

creates a brand-new jar on every call and loses the cookie. See `new_jar()` and the
note in `hustoj_client/_http.py`.

### Ampersand escaping is inconsistent

Some HUSTOJ themes emit `problem.php?cid=1&pid=0`, others `...&amp;pid=0`. A parser
that accepts only one form returns *zero problems* on the other, with no error.
`parse_problem_links` accepts both.

### Problem pages are Bootstrap panels

- The title sits in the first `<h3>`, formatted `Problem A: <title>`.
- Each section is an `<h4>` followed by a `<div class="panel-body">`.
- The `panel-body` element often carries *extra* classes, so match the class
  token rather than the exact attribute value.
- Section headings are matched case-insensitively and normalised to canonical
  names (`Sample   Input` → `Sample Input`), because themes vary the spacing.

### Dates and page parameters

Page 1 is requested as the bare `contest.php`; `?page=1` behaves inconsistently
across versions. Later pages use the explicit parameter.

## Project layout

```
hustoj_client/
├── _http.py      # urllib wrapper, jar handling, HTML-to-text
├── parsing.py    # contest list, problem links, statement parsing
├── checker.py    # fetch + diff against state, report building
├── config.py     # config load/save + the config CLI
└── __main__.py   # `python -m hustoj_client check`
tools/
└── make_vs_solution.py   # generate a VS solution, one project per problem
tests/
└── test_parsing.py       # 19 offline tests, no network needed
```

## Tests

The suite is fully offline: network failure paths are asserted rather than
mocked, so it runs anywhere.

```bash
python -m unittest discover -s tests -v
```

## Companion tool: one Visual Studio project per problem

A contest usually ships several problems and every one has its own `main()`, so
they cannot share a project. `tools/make_vs_solution.py` generates a `.sln` with
one console project per source file:

```bash
python tools/make_vs_solution.py --root ./code/cid1234 --name OJ1234 \
    A:src/A.cpp B:src/B.cpp C:src/C.cpp
```

It emits `/utf-8` into `AdditionalOptions` on purpose. Without it, `cl.exe` running
under a non-UTF-8 code page (for example 936) reports `C4819` and then misparses
every line after the first non-ASCII byte, producing nonsense errors such as
`"cin": undeclared identifier`. Adjust `PlatformToolset` if your Visual Studio
does not ship v145.

## Privacy

`config.json`, `state.json` and `session.txt` are in `.gitignore` for a reason:
they hold a judge URL, a contest password and possibly a live session cookie.
Check `git status` before your first push.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This project is intended for personal automation and for learning how a
server-rendered online judge is structured. It only ever *reads* from the judge.
If you use it, follow your institution's rules and do not use it to submit work
that is not yours.

## Screenshots

<!-- Add 2-3 screenshots here. A repository with a screenshot gets far more
     attention than one without. Suggestion:

     ![CLI scan output](docs/cli.png)

     Put files under docs/ and reference them relatively. -->
