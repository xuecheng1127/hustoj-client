"""HTML parsing for HUSTOJ pages: contest list, problem links, problem statements.

HUSTOJ is a PHP application that renders everything with Bootstrap panels.
The parsers below deliberately use regexes over the raw HTML instead of a
DOM library, so that the whole package stays dependency-free. The selectors
mirror the markup that Bootstrap-based HUSTOJ themes emit:

- contest.php rows are <tr> elements containing a contest.php?cid=<id> anchor
  followed by <td> cells: status, visibility, creator.
- problem.php wraps the title in <h3>, the limits in the panel-heading, and
  every section (Description, Input, ...) in an <h4> followed by a panel-body.
"""
import re

from ._http import strip_tags

#: Canonical section names and the patterns that match their headings.
SECTION_HEADS = [
    ("Description", r"^Description"),
    ("Input", r"^Input$"),
    ("Output", r"^Output$"),
    ("Sample Input", r"^Sample\s+Input"),
    ("Sample Output", r"^Sample\s+Output"),
    ("Hint", r"^Hint"),
    ("Source", r"^Source"),
]


def parse_contest_list(html_text):
    """Parse a contest.php listing page into a list of contest dicts.

    Returns:
        A list of dicts with the keys cid, title, status, private, creator.
        Rows that do not link to contest.php are skipped.
    """
    results = []
    for row_m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html_text, re.S | re.I):
        row_html = row_m.group(1)
        link_m = re.search(
            r"<a\s+href=['\"]contest\.php\?cid=(\d+)['\"][^>]*>(.*?)</a>",
            row_html, re.S | re.I,
        )
        if not link_m:
            continue
        cid = link_m.group(1)
        title = strip_tags(link_m.group(2))
        raw_cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S | re.I)
        cells = [strip_tags(c) for c in raw_cells]
        if len(cells) < 4:
            continue
        status = cells[2] if len(cells) > 2 else ""
        private = cells[3] if len(cells) > 3 else ""
        creator = cells[4] if len(cells) > 4 else ""
        results.append({
            "cid": cid,
            "title": title,
            "status": status,
            "private": private,
            "creator": creator,
        })
    return results


def parse_problem_links(contest_html, cid):
    """Extract the problem links from a contest page the user has entered.

    Duplicate pids are collapsed, keeping the first occurrence.

    HUSTOJ themes are inconsistent about the ampersand: some emit a raw "&",
    others emit the HTML entity "&amp;". Both are accepted, because a parser
    that handles only one of them silently returns zero problems on the other.
    """
    pattern = re.compile(
        r"<a\s+href=['\"]problem\.php\?cid=" + re.escape(str(cid))
        + r"(?:&|&amp;)pid=(\d+)['\"][^>]*>(.*?)</a>",
        re.S | re.I,
    )
    probs = []
    for m in pattern.finditer(contest_html):
        pid = m.group(1)
        title = strip_tags(m.group(2))
        if not any(p["pid"] == pid for p in probs):
            probs.append({"pid": pid, "title": title})
    return probs


def parse_problem_detail(html_text):
    """Parse a problem.php page into a structured dict.

    Returns keys: label, title, time_limit, memory_limit, sections (a dict of
    canonical section name -> plain text), and raw_text.
    """
    info = {"raw_text": html_text, "label": "", "title": "",
            "time_limit": "", "memory_limit": "", "sections": {}}

    h3_m = re.search(r"<h3[^>]*>(.*?)</h3>", html_text, re.S | re.I)
    if h3_m:
        h3_text = strip_tags(h3_m.group(1)).strip()
        m = re.match(r"Problem\s+([A-Z0-9]+)\s*[:：]\s*(.+)", h3_text)
        if m:
            info["label"] = m.group(1).strip()
            info["title"] = m.group(2).strip()
        else:
            info["title"] = h3_text

    heading_m = re.search(
        r"<div[^>]*class=['\"]panel-heading['\"][^>]*>.*?<h3[^>]*>.*?</h3>(.*?)</div>",
        html_text, re.S | re.I,
    )
    if heading_m:
        heading_text = strip_tags(heading_m.group(1))
        tl = re.search(r"Time\s+Limit[:：]?\s*(\d+(?:\.\d+)?)\s*Sec", heading_text, re.I)
        ml = re.search(r"Memory\s+Limit[:：]?\s*(\d+)\s*MB", heading_text, re.I)
        info["time_limit"] = tl.group(1) + " Sec" if tl else ""
        info["memory_limit"] = ml.group(1) + " MB" if ml else ""

    sections = {}
    sec_pattern = re.compile(
        r"<h4[^>]*>(.*?)</h4>.*?<div[^>]*class=['\"]panel-body(?:\s+content)?['\"][^>]*>(.*?)</div>",
        re.S | re.I,
    )
    for m in sec_pattern.finditer(html_text):
        sec_name = strip_tags(m.group(1)).strip()
        sec_content = strip_tags(m.group(2)).strip()
        for canonical, pat in SECTION_HEADS:
            if re.search(pat, sec_name, re.I):
                if canonical not in sections or len(sec_content) > len(sections[canonical]):
                    sections[canonical] = sec_content
                break
    info["sections"] = sections
    return info
