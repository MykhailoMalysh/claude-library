---
name: implement-task
description: >-
  Builds a single task from an existing plan to an open, review-ready PR using
  test-driven development. Use this whenever the user wants to implement, build, or write the
  code for the current task — e.g. "implement the task", "implement this", "build this task",
  "let's implement", "start implementing", "write the code for this". It runs the build half of
  the lifecycle: after start-task (which cut the branch) and plan-task (which wrote the plan), it
  preflights the environment, reads the plan, builds it test-first (red/green/refactor), verifies
  the full suite, then opens the PR and moves the board item to In Review. It requires a plan at
  .plans/<n>-<slug>.md; if none exists it stops and tells the user to run plan-task first.
  Trigger it even when the user doesn't say the word "skill" — any request to implement or build
  the current task counts. Do NOT use it to pick the next task (that's start-task), to plan the
  work (that's plan-task), or to review/merge an existing PR (that's validate-pr / finish-pr).
---

# Implement Task

The build half of the task lifecycle. `start-task` selected a subtask and cut the branch;
`plan-task` turned the spec into a test-first plan; the review skills (`validate-pr`,
`triage-pr-findings`, `finish-pr`) handle the PR that comes out. This skill is the part in the
middle that writes the code — and it builds **test-first**.

This skill is a **thin orchestrator**. It does not reinvent TDD; it sequences the superpowers
skills that already do it well and adds the project-specific glue (environment preflight, PR
opening, board move). Lean on those skills — don't paraphrase their discipline, invoke them.

**Authority is the branch, not the prompt.** Like `start-task`, this skill works on the issue
encoded in the *current branch name*. If the user mentions a different feature or module in
their request, ignore it for task selection — the branch decides what gets built. This keeps
work on the intended sequence.

## Precondition

Two things must hold before building:

1. **On a task branch** — `feature/<n>-…` or `plan/<n>-…` (check with
   `git rev-parse --abbrev-ref HEAD`). If the branch is `main`, stop and tell the user to run
   `start-task` first — there is no task to implement.
2. **A plan exists** — `.plans/<n>-<slug>.md` for this issue must be present. Planning now lives
   in the separate `plan-task` skill, so this skill builds *from* a plan rather than writing one.
   If no plan file is found, **stop and tell the user to run `plan-task` first** — do not
   improvise a plan inline. This keeps the plan a reviewable artifact and keeps the two halves of
   the build cleanly separable.

## The flow

```
start-task (branch) → plan-task (.plans/<n>-<slug>.md)
   │
   ▼  implement-task
   1. preflight environment        scripts/preflight.sh         — environment ready
   2. read the plan                .plans/<n>-<slug>.md          — what to build, test-first
   3. build (TDD)                  skill: superpowers:executing-plans    → red/green/refactor
   4. verify                       skill: superpowers:verification-before-completion
   5. open PR                      scripts/start_pr.py          — PR + board → In Review
   │
   ▼  validate-pr
```

### Step 1 — Preflight the environment

Run the preflight script and confirm it exits 0 before doing anything that runs tests:

```bash
bash .claude/skills/implement-task/scripts/preflight.sh
```

It checks that the build environment is ready (e.g. that required services are running). If it
exits non-zero, surface its one-line fix hint to the user and stop — nothing downstream can pass
with a broken environment.

If the script is absent, skip this step and proceed directly to Step 2.

### Step 2 — Read the plan

Derive the issue number from the branch (`feature/7-…` → `#7`) and read
`.plans/<n>-<slug>.md` — the plan `plan-task` wrote. It already carries the acceptance criteria
distilled into a test-first sequence; you build *from* it, you do not re-derive it. If the file
is absent, you should have already stopped at the precondition above and sent the user to
`plan-task`.

### Step 3 — Build, test-first

Invoke the **`superpowers:executing-plans`** skill, which drives **`superpowers:test-driven-development`**
task by task: write a failing test, watch it fail for the right reason, write the minimal code to
pass, refactor, commit per green. Honor the Iron Law — no production code without a failing test
first.

### Step 4 — Verify before completion

Invoke the **`superpowers:verification-before-completion`** skill. The full suite must be green
and no test was left skipped or `xfail`ed to make the build pass. If anything is red, go back
to Step 3 — do not open a PR on a failing build.

### Step 5 — Open the PR

Compose the PR body prose yourself (you have the context the script can't): a short **Summary**,
a **Tests** line with the suite count, and any **notable deviations**. Write it to a temp file,
then run:

```bash
python3 .claude/skills/implement-task/scripts/start_pr.py --body-file <body-file>
```

The script does the deterministic mechanics: derives the issue number + title from the branch,
injects `Closes #N` if your body omits it, pushes the branch, `gh pr create`s, and moves the
board item Status → **In Review**. It prints the PR URL. (Pass `--project 5` only if board
auto-discovery ever fails.)

## Report

After Step 5, print this compact summary — nothing else:

```
Branch:   <branch-name>
Issue:    #<n> — <title>
Plan:     .plans/<n>-<slug>.md   (local scratch, gitignored)
Tests:    <N>/<N> green
PR:       <url>   (board → In Review)
Next:     validate-pr
```

## Bundled scripts

- `scripts/preflight.sh` — environment readiness check. Adapt or replace for your project's
  build tooling (Docker, services, compilers). Reusable before any test run.
- `scripts/start_pr.py` — opens the PR and moves the board item to In Review. Shares board
  mechanics with `finish-pr` via `.claude/skills/_lib/board.py`.
