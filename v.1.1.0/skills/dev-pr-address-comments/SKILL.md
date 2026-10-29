---
name: dev-pr-address-comments
description: Walk through open Azure DevOps PR review comments one at a time and, per comment, either fix the code (edit, commit, push) and reply with what changed, reply only, mark it resolved, or skip. Use when the developer says "address the PR comments", "respond to review feedback", "fix the review comments", "resolve the comments on my PR", or invokes /dev-pr-address-comments. This closes the loop that dev-pr-review opens — dev-pr-review finds issues as a reviewer (and posts them when asked), this skill answers them as the author.
compatibility:
  required_tools:
    - Bash
    - Read
    - Edit
---

# dev-pr-address-comments

Fetches active (unresolved) comment threads on the current branch's Azure DevOps PR and walks them one at a time with the developer. For each thread the developer decides how to handle it — fix the code, reply only, mark resolved, or skip — and the skill carries out that decision immediately before moving to the next thread.

## When to Use

- Developer says "address the PR comments", "respond to review feedback", "fix the review comments"
- Developer invokes `/dev-pr-address-comments`
- Developer has an open PR with reviewer comments (from `dev-pr-review` or a human reviewer) they want to work through

## Prerequisites

See `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` for the full `.env` schema. This skill reads `ADO_ORG`, `ADO_PROJECT`, `ADO_REPO`, `ADO_PAT` (same as `dev-pr-open` — see its Prerequisites for how to generate a PAT).

The ADO calls run through the shared `lib/` Python package at `${CLAUDE_PLUGIN_ROOT}/lib/`. It needs `requests` installed — `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt` if it isn't already available.

Must be run inside a git repository, on the branch the PR is open against.

## Workflow

### Step 1: Find the target PR

```bash
export ADO_ORG ADO_PROJECT ADO_REPO ADO_PAT
CURRENT_BRANCH=$(git branch --show-current)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_pr.py check --source "$CURRENT_BRANCH"
```

If it exits 1 (no active PR), tell the user: "No open PR found for this branch — run `/dev-pr-open` first." Stop.

If it exits 0, it printed `PR_ID=`. Use that PR for everything below.

### Step 2: List open comment threads

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_comment.py list --pr-id <id>
```

This prints a JSON array of active threads, each with `thread_id`, `file_path`, `line` (both `null` for general comments), and `comments` (each with `id`, `content`, `author`).

If the array is empty, report "No open review comments on PR #`<id>`." and stop — nothing to do.

Process threads grouped by file (alphabetical), then by line within a file; general (no `file_path`) threads last. This keeps related comments together instead of jumping around the diff.

### Step 3: Walk threads one at a time

Posting replies and resolving threads is visible to every reviewer on the PR — handle each thread individually and get an explicit decision before acting, the same discipline `dev-pr-review` uses when asked to post.

For each thread:

**3a. Show the thread**

```
File: <file_path>:<line>          (or "General comment" if no file_path)
<author>: <comment content>
(plus any earlier replies already in the thread, oldest first)
```

If the thread is anchored to a file/line, read that file around the line so you have real context before deciding anything — don't rely on the comment text alone.

**3b. Ask how to handle it**

Ask: "How do you want to handle this?" with these choices:
1. **Fix it** — make the code change now
2. **Reply only** — explain without changing code (e.g. "won't fix, here's why" or "already handled elsewhere")
3. **Mark resolved** — no code change, no reply, just close the thread (e.g. duplicate or already stale)
4. **Skip** — leave it untouched, decide later

**3c. Fix it**

1. **Read specifications first** — Before implementing the fix, check if it involves a format, protocol, standard, or system with formal specifications (TOML, JSON, API specs, platform docs, etc.). If yes:
   - Identify what specification governs the fix
   - Ask the user for the specification URL if you don't have it
   - Read the relevant sections BEFORE writing any code
   - Base the fix on the specification, not assumptions
   - See `dev-bug-fix` Phase 5 "CRITICAL — Read Specifications First" for full guidance
2. Make the change. If the fix isn't obvious from the comment + surrounding code + specifications, ask the developer for clarification before editing — don't guess at intent on a change a reviewer will see.
3. Verify the change (read the file back, verify against specification if applicable).
4. Read recent commits (`git log --oneline -10`) and commit in the same style — same discipline as `dev-bug-fix`'s Commit Style section. Don't invent a format.
5. Push the branch (`git push`) — the reviewer needs to see the updated diff for the reply to make sense.
6. Draft a reply, e.g. `Fixed in <short-sha>: <one-line description>`. Show it to the developer and let them accept, edit, or write their own before posting (same yes/no/edit pattern as `dev-pr-review` Phase 4).
7. Post the reply and resolve the thread:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_comment.py reply --pr-id <id> --thread-id <thread_id> --content-file <path>
   python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_comment.py resolve --pr-id <id> --thread-id <thread_id> --status fixed
   ```

**3d. Reply only**

1. Draft or ask the developer for the reply text (write it to a temp file).
2. Post it:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_comment.py reply --pr-id <id> --thread-id <thread_id> --content-file <path>
   ```
3. Ask whether the thread should be marked resolved now or left open pending the reviewer's response. If resolved, ask which status fits — `fixed` (addressed as-is), or `wontFix` (declined, explained in the reply) — and run:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_comment.py resolve --pr-id <id> --thread-id <thread_id> --status <fixed|wontFix>
   ```

**3e. Mark resolved (no reply)**

Confirm the reason briefly (e.g. "duplicate of the comment on line 12"), then:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_comment.py resolve --pr-id <id> --thread-id <thread_id> --status <fixed|wontFix|closed>
```

**3f. Skip**

Do nothing. Move to the next thread.

Report the outcome of each thread immediately (`✓ Fixed and replied`, `✓ Replied`, `✓ Resolved`, `— Skipped`) before moving on — don't batch the reporting until the end.

### Step 4: Summary

After the last thread, report:

```
Addressed N/M comments on PR #<id>:
  Fixed:    <count> (<short-sha>, <short-sha>, ...)
  Replied:  <count>
  Resolved: <count>
  Skipped:  <count>

<PR_URL>
```

## Error Handling

| Situation | Action |
|---|---|
| No active PR for this branch | Tell the user to run `/dev-pr-open` first, stop |
| No open comment threads | Report "No open review comments" and stop |
| Fix requires clarification | Ask the developer before editing — do not guess |
| `git push` fails (e.g. diverged branch) | Report the error, do not post the reply until the push succeeds — a reply claiming a fix that isn't visible in the diff is misleading |
| `cli_comment.py reply`/`resolve` fails for one thread | Report the stderr message for that thread, continue with the remaining threads |
| `requests` not installed | Tell the user to run `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt`, stop |

## Why This Workflow

`dev-pr-review` lets the reviewer (human or Claude) post verified, structured comments to the PR on request. Without this skill, the author still has to open the ADO web UI to read, fix, and reply to each one — the same copy-paste round trip `dev-pr-review` was built to eliminate, just on the other side of the conversation. Walking threads one at a time, with an explicit decision per thread, keeps the same safety discipline as posting: nothing lands on the PR — a reply, a resolution, a pushed commit — without the developer having seen and approved it first.
