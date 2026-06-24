#!/usr/bin/env python3
"""
finish_pr.py — merge PRs, close linked issues, move board items to Done.

Usage:
  python finish_pr.py 17 18          # finish in order
  python finish_pr.py --list         # show open PRs and exit
  python finish_pr.py --project 5    # override project board number (default: from memory)

Steps for each PR (in the order given):
  1. Merge (squash, delete branch). Skip if already merged/closed.
  2. Collect issues referenced by "Closes #N" / "Fixes #N" in the PR body.
  3. Close each referenced issue if still open.
  4. Remove that issue's ephemeral plan scaffold (.plans/<issue>-*.md), if any.
  5. Move each issue's project-board item to Done.

Board mechanics (gh/project helpers, board discovery, the move call) live in the
shared _lib/board.py so they exist once and are reused by start_pr.py. The only
logic kept here is PR-specific.
"""

import argparse
import sys
import time
from pathlib import Path

# Import the shared board library: _lib/ is a sibling of this skill's parent.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
import board  # noqa: E402


# ── per-PR logic ──────────────────────────────────────────────────────────────

def get_pr(repo, number):
    return board.gh_json(
        "pr", "view", str(number), "--repo", repo,
        "--json", "number,title,state,body,mergedAt"
    )


def parse_closes(body):
    """Return issue numbers referenced by Closes/Fixes/Resolves #N."""
    import re
    return [int(n) for n in re.findall(
        r"(?:closes|fixes|resolves)\s+#(\d+)", body, re.IGNORECASE
    )]


def merge_pr(repo, number):
    pr = get_pr(repo, number)
    state = pr["state"]
    if state == "MERGED":
        print(f"  PR #{number} already merged — skipping.")
        return
    if state == "CLOSED":
        print(f"  PR #{number} closed (stacked / auto-closed) — skipping.")
        return
    print(f"  Merging PR #{number}: {pr['title']} …")
    board.gh("pr", "merge", str(number), "--repo", repo, "--squash", "--delete-branch")
    print(f"  PR #{number} merged.")
    time.sleep(2)


def close_issue(repo, number):
    issue = board.gh_json("issue", "view", str(number), "--repo", repo, "--json", "number,title,state")
    if issue["state"] == "CLOSED":
        print(f"    Issue #{number} already closed.")
        return
    board.gh("issue", "close", str(number), "--repo", repo)
    print(f"    Closed issue #{number}: {issue['title']}")


def remove_plan_files(issue_number):
    """Delete the ephemeral plan scaffold for a closed issue. Plans live in the
    gitignored .plans/ dir (working scratch from the implement-task skill), so this
    is a plain filesystem delete — nothing to commit. A missing plan is a no-op."""
    plans_dir = Path(board.repo_root()) / ".plans"
    if not plans_dir.is_dir():
        return
    removed = []
    for path in plans_dir.glob(f"{issue_number}-*.md"):
        path.unlink()
        removed.append(path.name)
    if removed:
        print(f"    Removed plan scaffold: {', '.join(removed)}")


# ── list mode ─────────────────────────────────────────────────────────────────

def list_open_prs(repo):
    prs = board.gh_json(
        "pr", "list", "--repo", repo, "--state", "open",
        "--limit", "30", "--json", "number,title,headRefName"
    )
    if not prs:
        print("No open PRs.")
        return
    print(f"Open PRs in {repo}:")
    for pr in prs:
        print(f"  #{pr['number']}  {pr['title']}  [{pr['headRefName']}]")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Finish PRs: merge, close linked issues, move board to Done."
    )
    parser.add_argument("prs", nargs="*", type=int, help="PR numbers (in merge order)")
    parser.add_argument("--list", action="store_true", help="List open PRs and exit")
    parser.add_argument("--project", type=int, default=None, help="Project board number")
    args = parser.parse_args()

    repo = board.get_repo()
    owner = repo.split("/")[0]

    if args.list:
        list_open_prs(repo)
        return

    if not args.prs:
        print("No PR numbers given. Use --list to see open PRs.", file=sys.stderr)
        sys.exit(1)

    project_number = board.resolve_project_number(args.project)

    print(f"Discovering project board #{project_number} …")
    ctx = board.get_project_context(owner, project_number)
    print(f"  Project node ID : {ctx['project_id']}")
    print(f"  Status field ID : {ctx['status_field_id']}")
    print(f"  Done option ID  : {board._option_id(ctx, 'Done')}\n")

    all_issues = []

    for pr_num in args.prs:
        print(f"── PR #{pr_num} ──────────────────────────────")
        pr = get_pr(repo, pr_num)
        issues = parse_closes(pr["body"] or "")
        print(f"  Linked issues: {issues or 'none detected'}")
        merge_pr(repo, pr_num)
        for issue_num in issues:
            close_issue(repo, issue_num)
            remove_plan_files(issue_num)
            all_issues.append(issue_num)

    print("\n── Moving board items to Done ──────────────")
    for issue_num in all_issues:
        board.move_item(owner, project_number, issue_num, "Done", ctx)

    print("\nDone.")


if __name__ == "__main__":
    main()
