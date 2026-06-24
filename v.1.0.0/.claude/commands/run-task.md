---
description: Run the next task end-to-end — start → plan → build → validate → triage — as per-stage subagents, stopping at a triaged PR for your merge decision.
argument-hint: "[stepwise|auto] [T<n>|#<n>]   (default: stepwise, board-driven)"
---

# /run-task — task lifecycle orchestrator

Drive one task from "nothing started" to a **created, verified, and triaged PR**, then
stop and hand back to the human. You are the **orchestrator**: you do not do the stage work
yourself, you **dispatch each stage as a subagent** (via the Agent tool) with a stage-specific
**model override**, then apply the checkpoint for the chosen mode, then dispatch the next stage.

**This command never merges.** `finish-pr` is out of scope — the run is terminal at triage, and
the human decides whether to merge.

## Arguments

Parse `$ARGUMENTS` for two optional tokens (order does not matter):

- **Mode token** — `auto` → autonomous (all stages back-to-back); anything else or absent →
  `stepwise` (default, pause after each stage).
- **Task hint** — `T<n>` or `#<n>` (e.g. `T9`, `#11`) → the explicit issue number to work on.
  When present, pass it to the Stage 1 subagent so `start-task` can skip board discovery and
  go directly to reading, checking blockers, and cutting the branch for that issue.
  Absent → `start-task` picks the next eligible task from the board as usual.

Examples: `stepwise T9`, `auto #11`, `T10`, `auto`, *(empty)*.

State the resolved mode and task hint (or "board-driven") in one line before you begin.

## Why subagents (read before dispatching)

Each stage wants a different model, and a single session can only run one model — so each stage
runs as its own subagent with its own `model`. Subagents start with **fresh context**, so state
does **not** flow through your conversation. It flows through **durable handoffs** that already
exist in this repo, and your job is to pass the right pointer into each subagent's prompt:

| Handoff | Lives in | Passed to |
|---|---|---|
| selected task + branch | the git branch `start-task` cut | every later stage |
| the plan | `.plans/<n>-<slug>.md` on disk | implement-task |
| the PR number | discoverable from the branch (`gh pr view`) / the board | validate, triage |
| validation findings | the "PR Validation Report" comment on the PR | triage |

After Stage 1, capture the **branch name**, **issue number**, and **issue title** from the
subagent's report and thread them into every later subagent prompt. After Stage 3, capture the
**PR number**.

## The stages

Dispatch these in order. Each subagent's task is: "invoke the named skill and follow it exactly
for the current branch; report back its standard summary." Set the Agent `model` as shown.

| # | Skill | Default model | Escalation rule |
|---|---|---|---|
| 1 | `start-task` | `haiku` | — |
| 2 | `plan-task` | `sonnet` | → `opus` if issue involves schema/data model changes, new modules, or architectural decisions |
| 3 | `implement-task` | `sonnet` | — |
| 4 | `validate-pr` | `sonnet` | — |
| 5 | `triage-pr-findings` | `sonnet` | → `opus` if Stage 4 reported any Critical or High findings |

**Stage 2 model selection:** After Stage 1 returns the issue title and body, scan for these
signals. If any match, dispatch Stage 2 with `opus`; otherwise use `sonnet`:
- schema, migration, data model changes
- new module, new package, new aggregate or bounded context
- ADR, architectural decision
- contract surface change (adding/removing public API, not just tests)

**Stage 5 model selection:** After Stage 4 returns, check whether the Validation Report
contains any `Critical` or `High` findings. If yes, dispatch Stage 5 with `opus`. If findings
are all Medium / Low / Trivial / Resolved, use `sonnet`.

For each dispatch, give the subagent: the skill to invoke, the branch name and issue number
(from Stage 1), the PR number (from Stage 3 onward), and the exact summary you need back. Keep
each subagent narrowly scoped to its one stage — it must not run ahead into the next.

**Forwarding prior context to Stage 2:** If your conversation context already contains analysis
about this issue (gap analysis, known missing coverage, existing file inventory), include a
concise `Prior context` block in the Stage 2 subagent prompt. This lets `plan-task` skip
re-reading files it doesn't need to re-read and go straight to writing the plan.

## Checkpoints

### Stepwise mode (default)

After each stage's subagent returns, post a compact summary and **stop for explicit approval**
before the next dispatch:

1. after **start-task** — which task + branch
2. after **plan-task** — the plan (action items, nuances, edge cases); this is the review *before
   any code*, the whole reason planning is its own stage
3. after **implement-task** — what was built, suite result, PR link
4. after **validate-pr** — the problem cases posted to the PR
5. after **triage-pr-findings** — the verdicts (terminal anyway)

Do not dispatch the next stage until the human says go.

### Autonomous mode (`auto`)

Dispatch Stage 1 → 5 with no pauses of your own. If a subagent reports that its skill hit a
hard-required input gate it cannot resolve alone (e.g. `start-task` finds two candidate parent
issues), surface that question and wait — otherwise keep going. End with one consolidated
summary: task, branch, plan path, PR link, validation report, triage verdicts.

## Failure handling

- **Triage is always terminal.** Both modes end after Stage 5 and wait for the human's approval
  or action items. **Never** merge, regardless of the verdicts.
- **A hard failure before triage halts the run immediately** (either mode). If a subagent reports
  any of these, stop and report with the evidence — do **not** dispatch further stages:
  - `start-task` finds no eligible task on the board.
  - `implement-task` reports no plan at `.plans/<n>-<slug>.md` (shouldn't happen — Stage 2 writes
    it — but if it does, the build subagent stops and so do you).
  - The environment preflight fails at `implement-task`.
  - Tests won't go green.
  - The PR cannot be opened.
- **No self-fixes, no retries.** You stop and hand the human the failure. Leave partial progress
  (branch, plan, commits) in place for inspection — do not clean it up.

## Final report

When the run reaches the terminal triage state, print one consolidated block:

```
Mode:     <stepwise | autonomous>
Task:     #<n> — <title>
Branch:   <branch-name>
Plan:     .plans/<n>-<slug>.md
PR:       <url>   (board → In Review)
Validate: report posted
Triage:   <one-line tally — e.g. 1 Critical, 2 Low, 3 Resolved>
Next:     your call — review the triage, then finish-pr to merge (not run by this command)
```
