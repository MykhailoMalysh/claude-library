#!/usr/bin/env python3
"""CLI for ADO pull request check/create/update.

Replaces scripts/create-ado-pr.sh. Same stdout contract (PR_ID=, PR_URL=)
and exit codes (0 success, 1 not found / bad args, 2 API error) so
dev-pr-open/SKILL.md's parsing instructions don't need to change.

Usage:
  cli_pr.py check --source <branch>
  cli_pr.py create --source <branch> --target <branch> --title <title> --description-file <path>
  cli_pr.py update --id <pr-id> [--title <title>] [--description-file <path>]

Required env vars: ADO_ORG, ADO_PROJECT, ADO_REPO, ADO_PAT
"""

import argparse
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


def read_description_file(path):
    if not os.path.isfile(path):
        print(f"Description file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r") as f:
        return f.read()


def run_check(client, args):
    try:
        result = client.find_active_pr(args.source)
    except ADOApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    if result is None:
        sys.exit(1)

    print(f"PR_ID={result['pr_id']}")
    print(f"PR_URL={result['pr_url']}")
    sys.exit(0)


def run_create(client, args):
    description = read_description_file(args.description_file)

    try:
        result = client.create_pr(args.source, args.target, args.title, description)
    except ADOApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"PR_ID={result['pr_id']}")
    print(f"PR_URL={result['pr_url']}")
    sys.exit(0)


def run_update(client, args):
    if args.title is None and args.description_file is None:
        print("update requires at least one of --title or --description-file", file=sys.stderr)
        sys.exit(1)

    description = read_description_file(args.description_file) if args.description_file else None

    try:
        result = client.update_pr(args.id, title=args.title, description=description)
    except ADOApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"PR_ID={result['pr_id']}")
    print(f"PR_URL={result['pr_url']}")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="ADO pull request operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--source", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--source", required=True)
    create_parser.add_argument("--target", required=True)
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--description-file", required=True)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--id", required=True, type=int)
    update_parser.add_argument("--title")
    update_parser.add_argument("--description-file")

    args = parser.parse_args()
    client = client_from_env()

    if args.command == "check":
        run_check(client, args)
    elif args.command == "create":
        run_create(client, args)
    elif args.command == "update":
        run_update(client, args)


if __name__ == "__main__":
    main()
