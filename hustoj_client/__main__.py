"""Command line entry point: python -m hustoj_client check ..."""
import argparse
import json
import sys

from .checker import build_report, print_report
from .config import CONFIG_FILENAME, load_config
from .config import main as config_main


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m hustoj_client",
        description="Watch a HUSTOJ instance for newly published assignments.",
    )
    parser.add_argument("--config", default=CONFIG_FILENAME, help="config path")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="scan the judge and report new assignments")
    p_check.add_argument("--config", default=CONFIG_FILENAME, help="config path")
    p_check.add_argument("--state", default=None,
                         help="state file; omit to run without persisting anything")
    p_check.add_argument("--report", default="text", choices=["text", "json", "markdown"])
    p_check.add_argument("--teacher", default=None, help="override the teacher filter")
    p_check.add_argument("--timeout", type=int, default=None, help="per-request timeout")
    p_check.add_argument("--only-new", action="store_true",
                         help="omit the list of already-seen assignments from the report")
    p_check.add_argument("--json-out", default=None, help="also write the report to this file")

    sub.add_parser("config", help="read or edit the configuration", add_help=False)

    if argv is None:
        argv = sys.argv[1:]
    # Delegate before argparse sees it: the config sub-parser is intentionally
    # add_help=False so that --help reaches config.main().
    if argv and argv[0] == "config":
        return config_main(argv[1:])

    args = parser.parse_args(argv)

    if args.command in (None, "check"):
        cfg_path = getattr(args, "config", None) or CONFIG_FILENAME
        try:
            cfg = load_config(cfg_path)
        except (OSError, ValueError) as e:
            print("[x] %s" % e, file=sys.stderr)
            return 2

        if getattr(args, "teacher", None):
            cfg["teachers"] = [args.teacher]
        timeout = getattr(args, "timeout", None) or int(cfg.get("request_timeout", 25))
        state_path = getattr(args, "state", None)
        if state_path is None and getattr(args, "command", None) == "check":
            state_path = cfg.get("state_file")

        report = build_report(cfg, state_path=state_path, timeout=timeout,
                              include_known=not getattr(args, "only_new", False))
        print_report(report, getattr(args, "report", "text"),
                     base_url=cfg.get("base_url", ""))

        out = getattr(args, "json_out", None)
        if out:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print("\n[ok] report written to %s" % out)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
