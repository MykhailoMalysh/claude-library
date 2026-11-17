#!/usr/bin/env python3
"""CLI for managing PR review comments and threads on ADO.

Usage:
  cli_comment.py post --pr-id <id> --content-file <path> [--file <path> --line <N>]
  cli_comment.py list --pr-id <id> [--all]
  cli_comment.py reply --pr-id <id> --thread-id <id> --content-file <path>
  cli_comment.py resolve --pr-id <id> --thread-id <id> [--status fixed|wontFix|closed]

Content is read from a file to avoid shell-escaping issues. --file/--line on
`post` anchor the comment to a specific line; omit both to post a general PR
comment. `list` prints active threads as JSON by default; pass --all to
include already-resolved threads.

Required env vars: ADO_ORG, ADO_PROJECT, ADO_REPO, ADO_PAT
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ado_client import ADOApiError, ADOClient

REQUIRED_ENV_VARS = ["ADO_ORG", "ADO_PROJECT", "ADO_REPO", "ADO_PAT"]


def client_from_env():
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        for name in missing:
            print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)

    return ADOClient(
        org=os.environ["ADO_ORG"],
        project=os.environ["ADO_PROJECT"],
        repo=os.environ["ADO_REPO"],
        pat=os.environ["ADO_PAT"],
    )


def run_post(client, args):
    if (args.file is None) != (args.line is None):
        print("--file and --line must be given together", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.content_file):
        print(f"Content file not found: {args.content_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.content_file, "r") as f:
        content = f.read()

    try:
        result = client.post_comment(args.pr_id, content, file_path=args.file, line=args.line)
    except ADOApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"COMMENT_ID={result['thread_id']}")
    sys.exit(0)


def run_list(client, args):
    try:
        threads = client.list_threads(args.pr_id, active_only=not args.all)
    except ADOApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(threads, indent=2))
    sys.exit(0)


def run_reply(client, args):
    if not os.path.isfile(args.content_file):
        print(f"Content file not found: {args.content_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.content_file, "r") as f:
        content = f.read()

    try:
        result = client.reply_to_thread(args.pr_id, args.thread_id, content)
    except ADOApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"REPLY_ID={result['comment_id']}")
    sys.exit(0)


def run_resolve(client, args):
    try:
        result = client.resolve_thread(args.pr_id, args.thread_id, status=args.status)
    except ADOApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"RESOLVED={result['status']}")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Manage ADO PR comments and threads")
    subparsers = parser.add_subparsers(dest="command", required=True)

    post_parser = subparsers.add_parser("post")
    post_parser.add_argument("--pr-id", required=True, type=int)
    post_parser.add_argument("--content-file", required=True)
    post_parser.add_argument("--file")
    post_parser.add_argument("--line", type=int)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--pr-id", required=True, type=int)
    list_parser.add_argument("--all", action="store_true", help="Include already-resolved threads")

    reply_parser = subparsers.add_parser("reply")
    reply_parser.add_argument("--pr-id", required=True, type=int)
    reply_parser.add_argument("--thread-id", required=True, type=int)
    reply_parser.add_argument("--content-file", required=True)

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--pr-id", required=True, type=int)
    resolve_parser.add_argument("--thread-id", required=True, type=int)
    resolve_parser.add_argument("--status", default="fixed", choices=["fixed", "wontFix", "closed"])

    args = parser.parse_args()
    client = client_from_env()

    if args.command == "post":
        run_post(client, args)
    elif args.command == "list":
        run_list(client, args)
    elif args.command == "reply":
        run_reply(client, args)
    elif args.command == "resolve":
        run_resolve(client, args)


if __name__ == "__main__":
    main()
