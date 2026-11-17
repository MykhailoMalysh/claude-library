#!/usr/bin/env python3
"""CLI for GitLab merge request read/create/comment operations via the REST API.

Usage:
  cli_gitlab.py mr-get --iid <N>
  cli_gitlab.py note --iid <N> --content-file <path> [--file <path> --line <N>]
  cli_gitlab.py check --source <branch>
  cli_gitlab.py create --source <branch> --target <branch> --title <title> --description-file <path>

`mr-get` prints the MR as JSON (read-only). `note` posts a general note, or an
inline diff discussion when --file and --line are given, and prints NOTE_ID=<id>.
dev-pr-review only runs `note` when the developer explicitly asks to post.

`check` and `create` are used by dev-pr-open for GitLab-hosted repos, mirroring
cli_pr.py's ADO check/create contract but with MR_IID=/MR_URL= instead of
PR_ID=/PR_URL=. `check` exits 0 (found, prints MR_IID=/MR_URL=) or 1 (not found).

Required env vars: GITLAB_URL, GITLAB_TOKEN
GITLAB_URL must be the instance root (e.g. https://git.epam.com), not a project URL.
Optional: GITLAB_PROJECT (group/project path); otherwise derived from `git remote get-url origin`.
"""

import argparse
import json
import os
import subprocess
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gitlab_client import GitLabApiError, GitLabClient, project_from_remote

REQUIRED_ENV_VARS = ["GITLAB_URL", "GITLAB_TOKEN"]


def instance_root(url):
    """Normalize a GITLAB_URL that may have been set to a project URL by mistake
    down to the instance root (scheme + host) that the API client needs."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}"


def resolve_project():
    project = os.environ.get("GITLAB_PROJECT")
    if project:
        return project
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return project_from_remote(remote)


def client_from_env():
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        for name in missing:
            print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)

    project = resolve_project()
    if not project:
        print("Cannot determine GitLab project: set GITLAB_PROJECT or run inside a repo with an origin remote", file=sys.stderr)
        sys.exit(1)

    return GitLabClient(base_url=instance_root(os.environ["GITLAB_URL"]), token=os.environ["GITLAB_TOKEN"], project=project)


def read_content_file(path):
    if not os.path.isfile(path):
        print(f"Content file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r") as f:
        return f.read()


def run_mr_get(client, args):
    try:
        mr = client.get_mr(args.iid)
    except GitLabApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(mr, indent=2))
    sys.exit(0)


def run_check(client, args):
    try:
        result = client.find_active_mr(args.source)
    except GitLabApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    if result is None:
        sys.exit(1)

    print(f"MR_IID={result['mr_iid']}")
    print(f"MR_URL={result['mr_url']}")
    sys.exit(0)


def run_create(client, args):
    description = read_content_file(args.description_file)

    try:
        result = client.create_mr(args.source, args.target, args.title, description)
    except GitLabApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"MR_IID={result['mr_iid']}")
    print(f"MR_URL={result['mr_url']}")
    sys.exit(0)


def run_note(client, args):
    if (args.file is None) != (args.line is None):
        print("--file and --line must be given together", file=sys.stderr)
        sys.exit(1)

    content = read_content_file(args.content_file)

    try:
        if args.file:
            result = client.post_inline_discussion(args.iid, content, args.file, args.line)
        else:
            result = client.post_note(args.iid, content)
    except GitLabApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"NOTE_ID={result['note_id']}")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="GitLab merge request operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("mr-get")
    get_parser.add_argument("--iid", required=True, type=int)

    note_parser = subparsers.add_parser("note")
    note_parser.add_argument("--iid", required=True, type=int)
    note_parser.add_argument("--content-file", required=True)
    note_parser.add_argument("--file")
    note_parser.add_argument("--line", type=int)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--source", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--source", required=True)
    create_parser.add_argument("--target", required=True)
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--description-file", required=True)

    args = parser.parse_args()
    client = client_from_env()

    commands = {
        "mr-get": run_mr_get,
        "note": run_note,
        "check": run_check,
        "create": run_create,
    }
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
