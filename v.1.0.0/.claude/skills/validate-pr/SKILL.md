---
name: validate-pr
description: "Validates a pull request by reading the actual code diff, then posts a GitHub PR comment with (1) a brief summary of what was implemented and (2) a problem-cases table showing risky scenarios and the exact file:line where the owner should verify correctness. Use whenever the user says 'validate PR <number>', 'review my last PR', 'check just created PR', 'validate current branch PR', 'review PR', or any similar phrase asking to review, validate, or check a pull request — even if no PR number is given."
---

# PR Validator

Analyses the real code diff of a PR and posts a structured GitHub comment that helps the PR owner know what was built and what to personally verify before merging.

## Step 1 — Resolve the PR

Determine which PR to validate:

- **Explicit number** ("validate PR 18") → use that number directly.
- **Current branch** ("validate current branch PR") → find the open PR whose head branch matches `git rev-parse --abbrev-ref HEAD`.
- **Last / just-created PR** ("review my last PR", "check just created PR") → list open PRs for the repo, pick the most recently created one.

Read the repo from `git remote get-url origin` (strip `.git`, extract `owner/repo`).

## Step 2 — Fetch everything you need in parallel

Fetch all three in one turn:
1. PR metadata (title, body, base branch, linked issue numbers).
2. Full diff — use `get_diff`.
3. Changed file list — use `get_files`.

If there is a linked issue number in the PR body, fetch that issue too to get the spec / acceptance criteria.

## Step 3 — Analyse the diff deeply

Read the entire diff. Do not skim. For every changed file, understand:

- What new behaviour was introduced (new methods, new validation branches, new queries).
- What invariants the code is trying to uphold (unique constraints, balance checks, guard clauses).
- Where the code makes assumptions that could fail under concurrency, unusual inputs, or edge-case state.

Focus especially on:
- **Validation logic** — are all reject paths reachable? Is ordering correct?
- **Transaction boundaries** — what happens if the operation is interrupted halfway?
- **Idempotency** — can the same operation be called twice safely?
- **Race conditions** — is there a window between a check and a write where state can change?
- **Edge inputs** — zero amounts, null fields, archived entities, future-dated records.
- **Error mapping** — does every exception reach the right HTTP status / error code?

## Step 4 — Write the PR comment

Compose a single GitHub comment with this exact structure:

---

## PR Validation Report

### What was implemented

_2–4 bullet points. Each bullet names the concrete thing built — class, method, rule, guard — and one sentence on what it does. Ground this in the code you read, not the PR description. If the PR description claims something that the code does not do, note the gap._

### Problem cases to verify

| # | Scenario | Risk if wrong | Where to look |
|---|----------|--------------|---------------|
| 1 | _what to try_ | _what breaks_ | `path/to/File.java:line` |
| 2 | ... | ... | ... |

_Include 5–8 rows. Each row is a specific, concrete scenario the owner can actually reproduce or trace — not a generic category like "null inputs". The "Where to look" column must be a real file path and line number from the diff. If a risk spans two places, list both._

---

Keep the language direct. The audience is the author of the PR — they know the codebase. No filler phrases.

## Step 5 — Post the comment

Post the comment to the PR using `add_issue_comment` (GitHub MCP).

Confirm to the user: "Comment posted to PR #N: <url>".
