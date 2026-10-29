#!/usr/bin/env python3
"""CLI for resolving the per-project ai-sdlc profile.

Usage:
  cli_profile.py show [--section NAME]

Prints the resolved profile as JSON ({"path", "settings", "sections"}), or
{"profile": null, "reason": "..."} when none resolves or it cannot be parsed.
Adds "warnings" when a list/map key parsed as a plain string. Always exits 0.
--section limits "sections" to the named heading.

Profile lookup: $AI_SDLC_PROFILE, else a profile in $AI_SDLC_PROFILES_DIR
(default ~/.claude/ai-sdlc/profiles) whose `remotes` matches origin of the cwd repo.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from profile import load_profile, resolve_profile_path, settings_warnings


def profiles_dir(env):
    return Path(env.get("AI_SDLC_PROFILES_DIR") or Path.home() / ".claude" / "ai-sdlc" / "profiles")


def cmd_show(args):
    res = resolve_profile_path(Path.cwd(), os.environ, profiles_dir(os.environ))
    if res.path is None:
        print(json.dumps({"profile": None, "reason": res.reason}))
        return 0
    try:
        data = load_profile(res.path)
    except ValueError as exc:
        print(json.dumps({"profile": None, "reason": f"cannot parse {res.path}: {exc}"}))
        return 0
    except OSError as exc:
        print(json.dumps({"profile": None, "reason": f"cannot read {res.path}: {exc}"}))
        return 0
    if args.section:
        data["sections"] = {k: v for k, v in data["sections"].items() if k == args.section}
    out = {"path": str(res.path), **data}
    if res.reason:
        out["reason"] = res.reason
    warnings = settings_warnings(data["settings"])
    if warnings:
        out["warnings"] = warnings
    print(json.dumps(out, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("show", help="print the resolved profile as JSON")
    show.add_argument("--section", help="only include this ## section")
    show.set_defaults(func=cmd_show)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
