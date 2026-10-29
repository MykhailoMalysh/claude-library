#!/usr/bin/env python3
"""CLI for Jira issue get/search/create/transition/comment via the REST API.

Usage:
  cli_jira.py get --key <ISSUE-KEY>
  cli_jira.py search --jql <jql>
  cli_jira.py create --project <KEY> --summary <text> --type <type>
                      [--description-file <path>] [--assignee <user>] [--priority <name>] [--parent <KEY>]
  cli_jira.py transition --key <ISSUE-KEY> --status <status-name>
  cli_jira.py comment --key <ISSUE-KEY> --content-file <path>

`get`/`search` print the issue(s) as JSON. `create`/`transition`/`comment` print a
single KEY=value line on success (ISSUE_KEY=, STATUS=, COMMENT_ID=) so skills can
parse stdout the same way they already do for the ADO CLIs.

Required env vars: JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jira_client import JiraApiError, JiraClient

REQUIRED_ENV_VARS = ["JIRA_URL", "JIRA_USERNAME", "JIRA_API_TOKEN"]


def client_from_env():
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        for name in missing:
            print(f"Missing required env var: {name}", file=sys.stderr)
        sys.exit(1)

    return JiraClient(
        base_url=os.environ["JIRA_URL"],
        username=os.environ["JIRA_USERNAME"],
        api_token=os.environ["JIRA_API_TOKEN"],
    )


def read_content_file(path):
    if not os.path.isfile(path):
        print(f"Content file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r") as f:
        return f.read()


def run_get(client, args):
    try:
        issue = client.get_issue(args.key)
    except JiraApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(issue, indent=2))
    sys.exit(0)


def run_search(client, args):
    try:
        issues = client.search_issues(args.jql)
    except JiraApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(issues, indent=2))
    sys.exit(0)


def run_create(client, args):
    description = read_content_file(args.description_file) if args.description_file else None

    try:
        result = client.create_issue(
            args.project,
            args.summary,
            args.type,
            description=description,
            assignee=args.assignee,
            priority=args.priority,
            parent_key=args.parent,
        )
    except JiraApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"ISSUE_KEY={result['key']}")
    sys.exit(0)


def run_transition(client, args):
    try:
        result = client.transition_issue(args.key, args.status)
    except JiraApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"STATUS={result['status']}")
    sys.exit(0)


def run_comment(client, args):
    content = read_content_file(args.content_file)

    try:
        result = client.add_comment(args.key, content)
    except JiraApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"COMMENT_ID={result['comment_id']}")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Jira issue operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--key", required=True)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--jql", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--project", required=True)
    create_parser.add_argument("--summary", required=True)
    create_parser.add_argument("--type", required=True)
    create_parser.add_argument("--description-file")
    create_parser.add_argument("--assignee")
    create_parser.add_argument("--priority")
    create_parser.add_argument("--parent")

    transition_parser = subparsers.add_parser("transition")
    transition_parser.add_argument("--key", required=True)
    transition_parser.add_argument("--status", required=True)

    comment_parser = subparsers.add_parser("comment")
    comment_parser.add_argument("--key", required=True)
    comment_parser.add_argument("--content-file", required=True)

    args = parser.parse_args()
    client = client_from_env()

    commands = {
        "get": run_get,
        "search": run_search,
        "create": run_create,
        "transition": run_transition,
        "comment": run_comment,
    }
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
