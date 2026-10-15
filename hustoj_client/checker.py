"""Assignment watching: compare the live contest list against persisted state."""
import json
import os
import sys
from datetime import datetime

from ._http import fetch, new_jar
from .parsing import (
    parse_contest_list,
    parse_problem_detail,
    parse_problem_links,
)

#: Fallback teacher filter used when the config leaves it empty.
DEFAULT_TEACHER = "<teacher-name>"


def now_str():
    """Return the current local time as "YYYY-MM-DD HH:MM:SS"."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fetch_contest_list(base_url, page=1, cookie_jar=None, timeout=25):
    """Fetch and parse one page of contest.php.

    Page 1 uses the bare URL because HUSTOJ treats "?page=1" inconsistently
    across versions; later pages use the explicit parameter.
    """
    base_url = base_url.rstrip("/")
    url = base_url + "/contest.php" if page == 1 else base_url + "/contest.php?page=" + str(page)
    html_text = fetch(url, cookie_jar=cookie_jar, timeout=timeout)
    return parse_contest_list(html_text)


def enter_contest(base_url, cid, contest_password, timeout=25):
    """Enter a private contest and return (page_html, cookie_jar).

    Getting past a *private* contest needs only the contest password -- not the
    account login. The session cookie obtained here is what makes the problem
    pages reachable afterwards, so the returned jar must be passed to
    :func:`fetch_problem`.
    """
    base_url = base_url.rstrip("/")
    url = base_url + "/contest.php?cid=" + str(cid)
    jar = new_jar()
    fetch(url, cookie_jar=jar, timeout=timeout)  # obtain a session first
    html_text = fetch(
        url, cookie_jar=jar, data={"password": contest_password}, timeout=timeout,
    )
    return html_text, jar


def fetch_problem(base_url, cid, pid, cookie_jar, timeout=25):
    """Fetch one problem page. The jar must come from :func:`enter_contest`."""
    base_url = base_url.rstrip("/")
    url = base_url + "/problem.php?cid=" + str(cid) + "&pid=" + str(pid)
    return fetch(url, cookie_jar=cookie_jar, timeout=timeout)


def load_state(path):
    """Load the seen-contests map, tolerating a missing or corrupt file."""
    if not path or not os.path.exists(path):
        return {"seen": {}, "last_check": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        state.setdefault("seen", {})
        return state
    except (OSError, ValueError):
        return {"seen": {}, "last_check": None}


def save_state(path, state):
    """Persist the seen-contests map, creating parent directories as needed."""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def resolve_teachers(cfg):
    """Return the list of teacher filters from a config dict.

    Accepts either the modern list field "teachers" or the legacy scalar
    "teacher_filter". Empty entries are dropped; the placeholder is used when
    nothing usable is configured so that the report says so instead of silently
    matching every contest.
    """
    teachers = cfg.get("teachers")
    if isinstance(teachers, str):
        teachers = [teachers]
    if not teachers:
        teachers = [cfg.get("teacher_filter", DEFAULT_TEACHER)]
    teachers = [t.strip() for t in teachers if t and str(t).strip()]
    return teachers or [DEFAULT_TEACHER]


def build_report(cfg, state_path=None, timeout=25, include_known=True):
    """Check the judge for newly published assignments.

    Args:
        cfg: Parsed config dict (see hustoj_client.config).
        state_path: Where to persist the seen-contest map. Written only when
            given; pass None for a completely read-only dry run.
        timeout: Per-request socket timeout.
        include_known: When False, the "known" list of already-seen assignments is
            omitted from the report. Useful for scheduled runs whose only job is to
            report what is new, and for keeping machine-readable output small.

    Returns:
        A report dict with checked_at, teachers, total_found, new_count, new
        and known. New entries carry the fetched problem statements when
        fetch_problems is enabled.
    """
    base_url = cfg["base_url"].rstrip("/")
    teachers = resolve_teachers(cfg)
    contest_password = cfg.get("contest_password", "")
    max_pages = int(cfg.get("max_pages", 3))
    fetch_problems = bool(cfg.get("fetch_problems", True))

    state = load_state(state_path) if state_path else {"seen": {}}

    all_contests = []
    for page in range(1, max_pages + 1):
        try:
            contests = fetch_contest_list(base_url, page, timeout=timeout)
        except Exception as e:  # noqa: BLE001 - report, do not abort the run
            print("[!] page %d failed: %s" % (page, e), file=sys.stderr)
            break
        if not contests:
            break
        all_contests.extend(contests)

    matched = [c for c in all_contests
               if any(t in c.get("title", "") for t in teachers)]
    matched.sort(key=lambda x: int(x["cid"]), reverse=True)

    seen = state.get("seen", {})
    new_contests = [c for c in matched if c["cid"] not in seen]

    report = {
        "checked_at": now_str(),
        "teacher": "、".join(teachers),
        "teachers": teachers,
        "total_found": len(matched),
        "new_count": len(new_contests),
        "new": [],
        "known": [c for c in matched if c["cid"] in seen] if include_known else [],
    }

    for c in new_contests:
        cid = c["cid"]
        detail = {"contest": c, "problems": []}
        if fetch_problems and contest_password:
            try:
                contest_html, jar = enter_contest(
                    base_url, cid, contest_password, timeout=timeout,
                )
                probs = parse_problem_links(contest_html, cid)
                detail["problem_count"] = len(probs)
                for p in probs:
                    page = fetch_problem(base_url, cid, p["pid"], jar, timeout=timeout)
                    pinfo = parse_problem_detail(page)
                    pinfo["url"] = (base_url + "/problem.php?cid=" + str(cid)
                                    + "&pid=" + str(p["pid"]))
                    detail["problems"].append({
                        "pid": p["pid"],
                        "title": pinfo.get("title") or p["title"],
                        "info": pinfo,
                    })
            except Exception as e:  # noqa: BLE001 - surface the failure in the report
                detail["error"] = str(e)
        report["new"].append(detail)
        if state_path:
            state.setdefault("seen", {})[cid] = c["title"]

    if state_path:
        state["last_check"] = now_str()
        save_state(state_path, state)
    return report


REPORT_SECTIONS = ["Description", "Input", "Output", "Sample Input", "Sample Output"]


def render_text(report):
    """Render a report as the human-readable plain-text form."""
    out = []
    out.append("[OJ] %s  teacher: %s" % (report["checked_at"], report["teacher"]))
    out.append("%d matching assignment(s), %d new." % (report["total_found"], report["new_count"]))

    if report["new_count"] == 0:
        out.append("No new assignments.")
        if report.get("known"):
            out.append("")
            out.append("Already seen:")
            for k in report["known"]:
                out.append("  - cid=%s %s [%s]" % (k["cid"], k["title"], k["status"]))
        return "\n".join(out) + "\n"

    for idx, item in enumerate(report["new"], 1):
        c = item["contest"]
        out.append("")
        out.append("#%d new assignment" % idx)
        out.append("  cid      : %s" % c["cid"])
        out.append("  title    : %s" % c["title"])
        out.append("  status   : %s" % c["status"])
        out.append("  private  : %s   creator: %s" % (c["private"], c["creator"]))
        if "error" in item:
            out.append("  [problem fetch failed: %s]" % item["error"])
            out.append("")
            out.append("=" * 60)
            continue
        out.append("  problems : %s" % item.get("problem_count", len(item["problems"])))
        for p in item["problems"]:
            info = p["info"]
            out.append("")
            out.append("  [Problem %s] %s" % (info.get("label") or "?", p["title"]))
            out.append("  limits: %s / %s"
                       % (info.get("time_limit") or "?", info.get("memory_limit") or "?"))
            if info.get("url"):
                out.append("  url   : %s" % info["url"])
            for sec_name in REPORT_SECTIONS:
                sec = info.get("sections", {}).get(sec_name)
                if sec:
                    out.append("")
                    out.append("  --- %s ---" % sec_name)
                    for line in sec.splitlines():
                        out.append("  " + line)
        out.append("")
        out.append("=" * 60)
    return "\n".join(out) + "\n"


def render_markdown(report, base_url=""):
    """Render a report as Markdown, for issue templates, reports or documentation.

    Args:
        report: A report produced by :func:`build_report`.
        base_url: Judge root URL used to build clickable links when the report
            entries do not already carry absolute URLs.
    """
    base_url = (base_url or "").rstrip("/")
    lines = []
    lines.append("# OJ assignment report")
    lines.append("")
    lines.append("- Checked at: %s" % report["checked_at"])
    lines.append("- Teacher filter: %s" % report["teacher"])
    lines.append("- Matching assignments: %d" % report["total_found"])
    lines.append("- New assignments: **%d**" % report["new_count"])
    lines.append("")

    if report["new_count"] == 0:
        lines.append("No new assignments.")
        if report.get("known"):
            lines.append("")
            lines.append("## Already seen")
            lines.append("")
            for k in report["known"]:
                link = "[%s]" % k["title"]
                if base_url:
                    link = "[%s](%s/contest.php?cid=%s)" % (k["title"], base_url, k["cid"])
                lines.append("- cid `%s` %s (%s)" % (k["cid"], link, k["status"]))
        return "\n".join(lines) + "\n"

    for item in report["new"]:
        c = item["contest"]
        lines.append("## New: %s" % c["title"])
        lines.append("")
        if base_url:
            lines.append("- Contest: [contest.php?cid=%s](%s/contest.php?cid=%s)"
                         % (c["cid"], base_url, c["cid"]))
        else:
            lines.append("- Contest cid: `%s`" % c["cid"])
        lines.append("- Status: %s   Visibility: %s   Creator: %s"
                     % (c["status"], c["private"], c["creator"]))
        if "error" in item:
            lines.append("- Problem fetch failed: %s" % item["error"])
            lines.append("")
            continue
        lines.append("- Problems: %s" % item.get("problem_count", len(item["problems"])))
        lines.append("")
        for p in item["problems"]:
            info = p["info"]
            label = info.get("label") or "?"
            lines.append("### Problem %s: %s" % (label, p["title"]))
            lines.append("")
            limits = "%s / %s" % (info.get("time_limit") or "?", info.get("memory_limit") or "?")
            lines.append("Time / memory: %s" % limits)
            if info.get("url"):
                lines.append("")
                lines.append("<%s>" % info["url"])
            for sec_name in REPORT_SECTIONS:
                sec = info.get("sections", {}).get(sec_name)
                if not sec:
                    continue
                lines.append("")
                lines.append("**%s**" % sec_name)
                lines.append("")
                lines.append("```")
                lines.extend(sec.splitlines())
                lines.append("```")
            lines.append("")
    return "\n".join(lines) + "\n"


def format_report(report, fmt="text", base_url=""):
    """Render a report in the requested format and return it as a string."""
    if fmt == "json":
        return json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if fmt == "markdown":
        return render_markdown(report, base_url=base_url)
    return render_text(report)


def print_report(report, fmt="text", base_url=""):
    """Print a report produced by :func:`build_report` as text, JSON or Markdown."""
    sys.stdout.write(format_report(report, fmt, base_url=base_url))
