#!/usr/bin/env python3
"""
start_pr.py — open the PR for the current task branch and move its board item to In Review.

Division of labor with the implement-task skill: Claude composes the PR body prose
(Summary / Tests / deviations) into a file, because that part is not deterministic;
this script does the mechanical, repeatable parts:

  1. Derive the issue number + slug from the current branch (feature/<n>-… or plan/<n>-…).
  2. Resolve a PR title — explicit --title, else the linked issue's title.
  3. Ensure the body contains "Closes #N" (inject a line if absent).
  4. Push the branch, then `gh pr create --body-file …`.
  5. Move the issue's board item Status → In Review.

It is the symmetric counterpart of finish_pr.py and shares its board mechanics via
the _lib/board.py library.

Usage:
  python start_pr.py --body-file /tmp/pr-body.md
  python start_pr.py --body-file /tmp/pr-body.md --project 5 --base main
  python start_pr.py --body-file /tmp/pr-body.md --title "Stage 5 · T8 · OpenAPI v0.1"
"""

import argparse
import re
import sys
import tempfile
from pathlib import Path

# Import the shared board library: _lib/ is a sibling of this skill's parent.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib"))
import board  # noqa: E402

REVIEW_STATUS = "In Review"


def current_branch():
    return board.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def parse_branch(branch):
    """Return (issue_number, slug) from a feature/<n>-… or plan/<n>-… branch."""
    m = re.match(r"^(?:feature|plan)/(\d+)-(.+)$", branch)
    if not m:
        print(f"Not on a task branch (got '{branch}'). Expected feature/<n>-… or "
              f"plan/<n>-… — run the start-task skill first.", file=sys.stderr)
        sys.exit(1)
    return int(m.group(1)), m.group(2)


def issue_title(repo, issue_number):
    return board.gh_json(
        "issue", "view", str(issue_number), "--repo", repo, "--json", "title"
    )["title"]


def ensure_closes(body, issue_number):
    """Guarantee the body links the issue so the PR auto-closes it on merge."""
    if re.search(rf"(?:closes|fixes|resolves)\s+#{issue_number}\b", body, re.IGNORECASE):
        return body
    return f"Closes #{issue_number}.\n\n{body}"


def existing_pr_url(repo, branch):
    """If an open PR already targets this branch, return its URL — else None."""
    result = board.gh(
        "pr", "view", branch, "--repo", repo, "--json", "url,state", check=False
    )
    if not result:
        return None
    import json
    data = json.loads(result)
    return data["url"] if data.get("state") == "OPEN" else None


def main():
    parser = argparse.ArgumentParser(
        description="Open the PR for the current task branch and move it to In Review."
    )
    parser.add_argument("--body-file", required=True, help="File holding the PR body prose")
    parser.add_argument("--title", default=None, help="PR title (default: linked issue title)")
    parser.add_argument("--base", default="main", help="Base branch (default: main)")
    parser.add_argument("--project", type=int, default=None, help="Project board number")
    args = parser.parse_args()

    repo = board.get_repo()
    owner = repo.split("/")[0]
    branch = current_branch()
    issue_number, _slug = parse_branch(branch)

    # Already open? Don't create a duplicate — just ensure the board reflects review.
    url = existing_pr_url(repo, branch)
    if url:
        print(f"PR already open for {branch}: {url}")
    else:
        body = Path(args.body_file).read_text()
        body = ensure_closes(body, issue_number)
        title = args.title or issue_title(repo, issue_number)

        # gh pr create needs the branch on the remote.
        print(f"Pushing {branch} …")
        board.run(["git", "push", "-u", "origin", branch])

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tmp:
            tmp.write(body)
            body_path = tmp.name

        print(f"Creating PR: {title}")
        url = board.gh(
            "pr", "create", "--repo", repo, "--base", args.base, "--head", branch,
            "--title", title, "--body-file", body_path,
        )
        print(f"  PR opened: {url}")

    print(f"\n── Moving issue #{issue_number} → {REVIEW_STATUS} ──")
    project_number = board.resolve_project_number(args.project)
    ctx = board.get_project_context(owner, project_number)
    board.move_item(owner, project_number, issue_number, REVIEW_STATUS, ctx)

    print(f"\nDone. PR: {url}")


if __name__ == "__main__":
    main()
