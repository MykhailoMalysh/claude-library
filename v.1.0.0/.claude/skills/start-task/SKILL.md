---
name: start-task
description: "Use when starting work on a task. Finds the active In Progress parent issue on the GitHub Projects board, selects the first eligible subtask with status Ready or In Progress, checks for blockers, and creates the correct branch. Invoke automatically when the user says: 'start a task', 'start task', 'start working', 'what should I work on', 'which task is next', 'next task', 'let's begin', 'begin work', 'what's next'."
---

# Start Task

Workflow for identifying and beginning the next task from the GitHub Projects board.

**Important:** This workflow selects tasks purely by board state and creation order. Whatever the user mentions in their prompt (a module name, a feature, a preference) does not influence which task is selected — the board decides. This ensures work follows the intended sequence.

## Before you begin

Read project memory file `.claude/memory/project_config.md` to get:
- `ISSUES_REPO` — the `owner/repo` where issues and the board live
- `BOARD_NUMBER` — the GitHub Projects board number
- `CODE_REPO` — the `owner/repo` where branches are created; falls back to `ISSUES_REPO` if absent

If `ISSUES_REPO` or `BOARD_NUMBER` is missing, ask the user before continuing.

## Fast path — explicit issue number

If the prompt explicitly supplies an issue number (e.g. `use issue #9`, `task hint: T9 = #9`,
`issue_number=9`), **skip Steps 1–3** entirely. Jump straight to Step 4 using that issue number
on `ISSUES_REPO`. Then continue with Steps 5–7 as normal.

This saves three board-discovery round-trips when the orchestrator already resolved which task
to work on.

## Step 1 — Find the active parent issue

List open issues in `ISSUES_REPO`:

```
mcp__plugin_github_github__list_issues
owner: <ISSUES_REPO owner>
repo: <ISSUES_REPO name>
state: open
```

From the results, identify parent issues — those that have sub-issues. Check which has project status `In Progress` on the board.

**If the MCP response does not include project status fields** (this is common — the GitHub MCP often omits board metadata): pick the parent issue with the most sub-issues as the active parent. Note this assumption in your Step 7 report under a `Note:` line.

- Zero parent issues with sub-issues → report "No active parent issue found" and stop.
- More than one candidate → ask the user which to focus on before continuing.

## Step 2 — List and validate subtasks

Fetch the sub-issues of the active parent:

```
mcp__plugin_github_github__issue_read
owner: <ISSUES_REPO owner>
repo: <ISSUES_REPO name>
issue_number: <parent issue number>
```

Extract the list of sub-issues. If project status fields are available, filter for `Ready` or `In Progress`. If status fields are unavailable (common), treat all open sub-issues as eligible.

- No open sub-issues → report "No eligible subtasks found" and stop.

## Step 3 — Select the subtask

Take the **first sub-issue by creation order** (lowest issue number). Do not use anything the user said in their prompt to influence this choice — the sequence on the board is the authority.

- Multiple sub-issues have status `In Progress` → ask the user: "Multiple subtasks are In Progress: [list them]. Which should we proceed with?"

## Step 4 — Read the description

Read the full subtask body:

```
mcp__plugin_github_github__issue_read
owner: <ISSUES_REPO owner>
repo: <ISSUES_REPO name>
issue_number: <subtask number>
```

Extract three things:

**ADR reference** — scan for patterns like "ADR:", "ADR reference:", "Relates to ADR", "See ADR", followed by a number or identifier.

**Work type** — scan for explicit statements: "type: plan", "type: feature", "this is a plan task", "this is a feature task", or similar. Also infer from clear task nature:
- Tasks about writing specs, ADRs, or design documents → `plan`
- Tasks about implementing code, writing migrations, building features → `feature`
- Genuinely ambiguous → ask the user: "Is this a `plan` (ADR/spec authoring) or `feature` (code implementation) task?"

**Blocked by** — scan for a "Blocked by" section. Extract any referenced issue numbers or PR URLs.

## Step 5 — Check blockers

If the Blocked by section is empty or absent, continue to Step 6.

For each listed blocker, check its current state:

```
mcp__plugin_github_github__issue_read   (for issue blockers)
mcp__plugin_github_github__pull_request_read   (for PR blockers)
```

If any blocker is still open → print the blocker summary and stop:

```
Blocked: #<N> "<title>" is still open — resolve this before starting the new branch.
```

## Step 6 — Create the branch

Derive the branch name:
- type prefix: `plan` or `feature`
- issue number: the subtask's GitHub issue number
- description: issue title → lowercase → replace spaces with hyphens → keep first 5 words only

Format: `<type>/<issue-number>-<description>`

Examples:
- `plan/42-accounts-module-structure`
- `feature/43-implement-account-entity`

Create the branch from `main` on `CODE_REPO`:

```
mcp__plugin_github_github__create_branch
owner: <CODE_REPO owner>
repo: <CODE_REPO name>
branch: <branch-name>
from_branch: main
```

If the branch already exists, report it and ask the user whether to use it or pick a different name.

## Step 7 — Report

Print this compact summary. No file. Nothing else.

```
Type:     plan | feature
Branch:   <branch-name>
ADR:      <reference found, or "not found in description">
Blockers: none | <description>
```

If board status was unavailable and you fell back to "most sub-issues" heuristic, add:

```
Note:     Board status unavailable via MCP — selected parent by sub-issue count
```
