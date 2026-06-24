---
name: triage-pr-findings
description: "Verifies each problem case from a PR Validation Report (posted by the validate-pr skill) against the actual code, schema, and specs, then answers in chat with a per-finding verdict table: Critical / Medium / Low / Trivial / Resolved, each grounded in evidence. Use whenever the user asks to triage, assess, or judge previously identified PR problems — phrases like 'validate PR <N> problems', 'are the PR issues critical', 'triage PR findings', 'give verdicts on PR 17 and 18', 'which of these PR problems matter', or any request to rate severity of issues found in a pull request review."
---

# Triage PR Findings

Takes the problem-cases table from an earlier PR validation and gives the owner a verdict per finding: which ones actually matter, which are cheap fixes, and which dissolve under verification. The owner uses this to decide what blocks merge and what gets carried forward.

## Step 1 — Resolve the PR(s)

- **Explicit number(s)** ("triage PR 17 and 18") → use them directly; multiple PRs are fine, handle each.
- **Current branch / "active"** → find the open PR whose head matches `git rev-parse --abbrev-ref HEAD`.
- **Nothing specified** → list the open PRs (number, title, branch) and ask the owner which to triage before doing any analysis. Use AskUserQuestion if available.

Read the repo from `git remote get-url origin`.

## Step 2 — Collect the findings and the ground truth

For each PR, fetch in parallel:
1. **PR comments** (`get_comments`) — locate the most recent comment containing "PR Validation Report". Its "Problem cases to verify" table is the input list. If no such comment exists, say so and offer to run the `validate-pr` skill first — do not invent a findings list from memory.
2. **The full diff** (`get_diff`) — you will re-read the relevant hunks while verifying.

## Step 3 — Verify every finding against reality

This is the heart of the skill. Do not grade findings by how plausible they sound — check each one against the authoritative sources in the repo:

- **Schema migrations** (`src/main/resources/db/migration/`) — does a constraint, index, or CHECK already backstop the risk? Does a column default change the picture?
- **Specs and docs** (`docs/specs/`, `docs/decisions/`) — does the spec explicitly endorse the behaviour the finding questions?
- **The actual code path** — trace it. A finding like "X might not be revalidated" is settled by reading the call chain, not by judgement.
- **The tests** — is the gap real (could the guard be deleted with the suite staying green) or is it covered elsewhere?

A finding that survives verification gets a severity. A finding that dissolves gets marked **Resolved** with the evidence — these are just as valuable to the owner as the real problems, because they close open questions.

## Step 4 — Assign verdicts

Use this scale, and always say *why* in terms of consequence and probability:

| Verdict | Meaning |
|---|---|
| **Critical** | Merge-blocking: data corruption, money-math error, or broken invariant reachable in normal use. |
| **Medium** | Not a blocker, but must land in a named follow-up task — record where the fix belongs. |
| **Low** | Real but cheap — typically a missing test or one-line hardening; do it next time in the file. |
| **Trivial** | Cosmetic or vanishingly improbable; fix opportunistically, never schedule it. |
| **Resolved** | Verified non-issue — state the evidence (file, line, spec section) that closes it. |

Severity is contextual: weigh who runs the system (single-user vs multi-tenant), what stage the project is in, and whether a DB constraint already guarantees correctness even when the app-layer path is imperfect.

## Step 5 — Answer in chat

Reply in the conversation (do not post to GitHub unless the user asks). Structure:

1. **Bottom line first** — one sentence: is anything merge-blocking?
2. **One verdict table per PR:**

   | # | Finding | Verdict | Why |
   |---|---------|---------|-----|

   Keep finding text short (the owner has the original report); spend the words on *Why* — the evidence found in Step 3, with `file:line` or spec references.
3. **Practical takeaway** — which follow-ups go where (e.g., "carry the error-mapping fix into T7"), and which test additions are one-liners worth doing immediately.
