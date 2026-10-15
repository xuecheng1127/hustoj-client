"""Central configuration for the watcher.

Every personal value lives in a single JSON file so that nothing has to be
edited inside code or copy-pasted into a scheduled task. The contest password
is masked when printed unless --reveal is passed.

CLI:
    python -m hustoj_client.config show
    python -m hustoj_client.config get teachers
    python -m hustoj_client.config set teachers "Alice,Bob"
"""
import argparse
import json
import os
import sys

CONFIG_FILENAME = "config.json"

#: Field name -> (human label, is_secret)
FIELDS = {
    "base_url": ("OJ base URL", False),
    "teachers": ("teacher name list", False),
    "teacher_filter": ("single teacher name (legacy)", False),
    "contest_password": ("contest/homework password", True),
    "max_pages": ("contest list pages to scan", False),
    "fetch_problems": ("fetch statements and samples", False),
    "request_timeout": ("per-request timeout in seconds", False),
    "state_file": ("path to the seen-contest state file", False),
}
LIST_FIELDS = {"teachers"}
INT_FIELDS = {"max_pages", "request_timeout"}
BOOL_FIELDS = {"fetch_problems"}

#: Fields accepted for backwards compatibility but ignored by this read-only
#: client, with a one-line explanation shown to the user.
IGNORED_FIELDS = {
    "student_id": "account login is out of scope for this client",
    "student_password": "account login is out of scope for this client",
    "student_name": "no longer used",
    "contest_cid": "tracked automatically via the state file",
    "submit_language": "submission is out of scope for this client",
    "build_standard": "local compilation is out of scope for this client",
    "language": "submission is out of scope for this client",
    "auto_submit": "submission is out of scope for this client",
    "submit_interval_seconds": "submission is out of scope for this client",
}

DEFAULT_CONFIG = {
    "_note": "All personal values live here. Never commit this file.",
    "base_url": "http://<your-oj-host>",
    "teachers": ["<teacher-name>"],
    "teacher_filter": "<teacher-name>",
    "contest_password": "",
    "max_pages": 3,
    "fetch_problems": True,
    "request_timeout": 25,
    "state_file": "state.json",
}


def load_config(path=CONFIG_FILENAME):
    """Load a config file and fill in any missing keys with defaults.

    Unknown keys are preserved (so a file written by another tool is not
    destroyed), but keys listed in IGNORED_FIELDS are reported on stderr once
    so the user knows they have no effect here.
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        raise ValueError("config root must be a JSON object")

    for key, reason in IGNORED_FIELDS.items():
        if key in cfg:
            print("[i] ignoring %r: %s" % (key, reason), file=sys.stderr)

    for key, value in DEFAULT_CONFIG.items():
        if key.startswith("_"):
            continue
        cfg.setdefault(key, value)

    if not str(cfg.get("base_url", "")).strip() or "<your-oj-host>" in str(cfg.get("base_url")):
        raise ValueError("base_url is not configured; edit %s first" % path)
    return cfg


def save_config(cfg, path=CONFIG_FILENAME):
    """Write a config dict to disk as UTF-8 JSON with a trailing newline."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def coerce(key, raw):
    """Convert a CLI string to the type implied by the field name."""
    if key in LIST_FIELDS:
        return [x.strip() for x in raw.replace("，", ",").split(",") if x.strip()]
    if key in INT_FIELDS:
        return int(raw)
    if key in BOOL_FIELDS:
        return str(raw).strip().lower() in ("1", "true", "yes", "y", "是", "开", "on")
    return raw


def mask(value):
    """Return a length-preserving mask for a secret value."""
    s = str(value)
    if not s:
        return "(empty)"
    return "*" * len(s) + "  (%d chars)" % len(s)


def cmd_show(path, reveal=False):
    cfg = load_config(path)
    print("config: %s\n" % os.path.abspath(path))
    for key, (label, secret) in FIELDS.items():
        if key not in cfg:
            continue
        value = cfg[key]
        if secret and not reveal:
            value = mask(value)
        print("  %-18s %-30s = %s" % (key, label, value))


def cmd_get(path, key):
    cfg = load_config(path)
    if key not in cfg:
        print("unknown field: %s\navailable: %s" % (key, ", ".join(FIELDS)))
        return 1
    secret = FIELDS.get(key, ("", False))[1]
    print(mask(cfg[key]) if secret else cfg[key])
    return 0


def cmd_set(path, key, raw):
    if key in IGNORED_FIELDS:
        print("field %r is not used by this client: %s" % (key, IGNORED_FIELDS[key]))
        return 1
    if key not in FIELDS:
        print("unknown field: %s\navailable: %s" % (key, ", ".join(FIELDS)))
        return 1
    cfg = load_config(path) if os.path.exists(path) else dict(DEFAULT_CONFIG)
    old = cfg.get(key)
    cfg[key] = coerce(key, raw)
    save_config(cfg, path)
    secret = FIELDS[key][1]
    shown_old = mask(old) if secret else old
    shown_new = mask(cfg[key]) if secret else cfg[key]
    print("updated %s (%s): %s -> %s" % (key, FIELDS[key][0], shown_old, shown_new))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m hustoj_client.config",
        description="Read or edit the hustoj-client configuration.",
    )
    parser.add_argument("--config", default=CONFIG_FILENAME, help="config path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="print the whole config (secrets masked)")
    p_show.add_argument("--reveal", action="store_true", help="print secrets in clear text")

    p_get = sub.add_parser("get", help="print a single field")
    p_get.add_argument("key")

    p_set = sub.add_parser("set", help="set a field")
    p_set.add_argument("key")
    p_set.add_argument("value", nargs="+")

    args = parser.parse_args(argv)
    if args.cmd == "show":
        return cmd_show(args.config, reveal=args.reveal)
    if args.cmd == "get":
        return cmd_get(args.config, args.key)
    if args.cmd == "set":
        return cmd_set(args.config, args.key, " ".join(args.value))
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
