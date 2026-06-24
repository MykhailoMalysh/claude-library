#!/usr/bin/env python3
"""
board.py — shared GitHub + Projects-board mechanics for the PR-workflow skills.

Consumers (each imports this with a two-line bootstrap):
  - finish-pr/scripts/finish_pr.py      moves closed issues -> Done
  - implement-task/scripts/start_pr.py  opens the PR, moves issue -> In Review

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
    import board

This lives in _lib/ (no SKILL.md) so the skill loader never routes to it — it is
invisible to skill selection and only ever imported by the scripts above. The point
of extracting it is that a board API change is a one-file edit and "move issue to
status X" exists in exactly one place.

Every command is passed as a list (never shell=True), so there is no shell-injection
surface.

Board configuration (ISSUES_REPO, BOARD_NUMBER, CODE_REPO) is read from the
project memory file at .claude/memory/project_config.md.
"""

import json
import re
import subprocess
import sys
from pathlib import Path


# ── subprocess + gh helpers ──────────────────────────────────────────────────

def run(args, check=True):
    """Run a command given as a list and return its stdout (stripped)."""
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"ERROR running: {' '.join(args)}\n{result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def gh(*args, check=True):
    return run(["gh"] + list(args), check=check)


def gh_json(*args):
    return json.loads(gh(*args))


# ── repo discovery ───────────────────────────────────────────────────────────

def get_repo():
    """owner/repo parsed from the origin remote."""
    remote = run(["git", "remote", "get-url", "origin"]).replace(".git", "")
    m = re.search(r"[:/]([^/]+/[^/]+)$", remote)
    if not m:
        print(f"Cannot parse repo from remote: {remote}", file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def repo_root():
    """Absolute path to the repository working tree root."""
    return run(["git", "rev-parse", "--show-toplevel"])


def read_project_number_from_memory():
    """Board number from .claude/memory/project_config.md, or None.

    Resolved relative to this file: _lib/ -> skills/ -> .claude/, then /memory.
    (The old in-script copy in finish_pr.py used one too few '..' and silently
    returned None — which is why auto-discovery used to fail. This is the fix.)
    """
    memory_path = Path(__file__).resolve().parents[2] / "memory" / "project_config.md"
    try:
        text = memory_path.read_text()
    except FileNotFoundError:
        return None
    m = re.search(r"board.?number.*?(\d+)", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def resolve_project_number(cli_value):
    """CLI --project wins; otherwise read from memory. Exit with a clear error if neither."""
    number = cli_value or read_project_number_from_memory()
    if not number:
        print("Project board number not found. Pass --project N or update "
              ".claude/memory/project_config.md.", file=sys.stderr)
        sys.exit(1)
    return number


# ── project board ────────────────────────────────────────────────────────────

def get_project_context(owner, project_number):
    """Discover the board once. Returns:
        {'project_id', 'status_field_id', 'options': {status_name: option_id}}

    Generalized from a Done-only lookup so a caller can target any Status column
    by name (Done, In Review, …) without re-querying the board.
    """
    project_id = gh_json(
        "project", "view", str(project_number), "--owner", owner, "--format", "json"
    )["id"]
    fields = gh_json(
        "project", "field-list", str(project_number), "--owner", owner, "--format", "json"
    )["fields"]

    status = next((f for f in fields if f["name"] == "Status"), None)
    if not status:
        print("Cannot find Status field on project board.", file=sys.stderr)
        sys.exit(1)

    options = {o["name"]: o["id"] for o in status.get("options", [])}
    return {"project_id": project_id, "status_field_id": status["id"], "options": options}


def _option_id(ctx, status_name):
    oid = ctx["options"].get(status_name)
    if not oid:
        print(f"Cannot find '{status_name}' option in the Status field. "
              f"Available: {', '.join(ctx['options']) or '(none)'}", file=sys.stderr)
        sys.exit(1)
    return oid


def _get_project_items_for_issue(owner, repo_name, issue_number, project_id):
    """Query the issue directly for its project board items via GraphQL.
    Returns a list of item node IDs that belong to the given project_id.
    This avoids fetching all board items and is not sensitive to board size."""
    query = """
    query($owner: String!, $repo: String!, $issue: Int!) {
      repository(owner: $owner, name: $repo) {
        issue(number: $issue) {
          projectItems(first: 10) {
            nodes { id project { id } }
          }
        }
      }
    }
    """
    raw = run([
        "gh", "api", "graphql",
        "-f", f"query={query}",
        "-f", f"owner={owner}",
        "-f", f"repo={repo_name}",
        "-F", f"issue={issue_number}",
    ])
    data = json.loads(raw)
    nodes = data["data"]["repository"]["issue"]["projectItems"]["nodes"]
    return [n["id"] for n in nodes if n["project"]["id"] == project_id]


def move_item(owner, project_number, issue_number, status_name, ctx):
    """Move the board item for issue #N to the named Status option.
    Looks up the item directly from the issue (no board-size limit). Idempotent:
    an issue absent from the board is reported and skipped rather than an error."""
    repo_name = get_repo().split("/")[1]
    item_ids = _get_project_items_for_issue(owner, repo_name, issue_number, ctx["project_id"])
    if not item_ids:
        print(f"    Issue #{issue_number} not found on board — skipping.")
        return

    target = _option_id(ctx, status_name)
    for item_id in item_ids:
        gh(
            "project", "item-edit",
            "--id", item_id,
            "--project-id", ctx["project_id"],
            "--field-id", ctx["status_field_id"],
            "--single-select-option-id", target,
        )
        print(f"    Moved issue #{issue_number} → {status_name} on board.")
