---
name: plan-task
description: >-
  Turns the current task into a reviewed, test-first plan written to
  .plans/<n>-<slug>.md — and then stops, before any code. Use this whenever the user wants to
  plan, design, or think through the current task before building — e.g. "plan the task",
  "plan this", "make a plan", "write the plan", "let's plan first", "what's the plan for this".
  It is the first half of the old implement-task: start-task cuts the branch, plan-task produces
  the plan, then implement-task builds from that plan. Use it especially on complex tasks where
  you want to review the approach, action items, and edge cases before a single test is written.
  Trigger it even when the user doesn't say the word "skill". Do NOT use it to pick the next task
  (that's start-task) or to write code (that's implement-task — which reads the plan this skill
  produces).
---

# Plan Task

The first half of the task build lifecycle. `start-task` selected a subtask and cut the branch;
this skill turns that subtask's spec into a **test-first plan** and stops there. The plan is the
thing a human reviews before any code exists — its whole value is catching a wrong approach
while changing it still costs nothing.

This skill is a **thin orchestrator**: it does not reinvent planning, it invokes
`superpowers:writing-plans` and adds the project-specific framing (where the spec lives, where
the plan goes). The split from `implement-task` exists so the plan is a real reviewable
artifact and so an orchestrator can pause cleanly between planning and building.

**Authority is the branch, not the prompt.** Like the rest of the lifecycle, this skill plans
the issue encoded in the *current branch name*. If the user mentions a different feature or
module, ignore it for task selection — the branch decides what gets planned.

## Precondition

You must be on a task branch: `feature/<n>-…` or `plan/<n>-…`. If the current branch is `main`
(check with `git rev-parse --abbrev-ref HEAD`), stop and tell the user to run `start-task`
first — there is no task to plan.

No environment preflight is needed: planning runs no tests and needs no build tooling. That cost
belongs to `implement-task`, where the suite actually runs.

## The flow

```
start-task (branch)
   │
   ▼  plan-task
   1. read the issue spec    GitHub MCP (inline)               — what to build + ACs
   2. plan                   skill: superpowers:writing-plans  → .plans/<n>-<slug>.md
   │
   ▼  implement-task (reads the plan)
```

### Step 1 — Read the issue spec

Derive the issue number from the branch (`feature/7-…` → `#7`). Read the subtask and any spec
it points at:

- Fetch the issue body via the GitHub MCP (`issue_read`) on `ISSUES_REPO` (owner/board
  from `.claude/memory/project_config.md`).
- Pull out the **acceptance criteria** and any referenced ADR or behavioral-spec section.
  These are what the plan's tests must prove.

### Step 2 — Write the plan

Invoke the **`superpowers:writing-plans`** skill to turn the spec into a test-first plan, with
one override: **write the plan to the gitignored scratch path `.plans/<issue>-<slug>.md`, and
do not commit it.** The plan is working scaffolding for this run, not durable knowledge — once
the PR merges, the code and the per-green commits already record how the task was built, so the
plan is deliberately ephemeral (`finish-pr` removes it at PR close). Durable design rationale
belongs in project documentation, not in a plan.

Make the plan genuinely reviewable: each step should name the failing test it adds, the minimal
code that makes it pass, and any project-specific nuance that matters. Surfacing these in the
plan is the point: it's where a reviewer catches a wrong assumption before it becomes code.

## Report

After Step 2, print this compact summary — nothing else:

```
Branch:   <branch-name>
Issue:    #<n> — <title>
Plan:     .plans/<n>-<slug>.md   (local scratch, gitignored)
Steps:    <N> planned
Next:     implement-task   (builds from this plan)
```

## Boundary with implement-task

This skill stops at the plan. It writes no production code, no tests, opens no PR, and touches
no board status. `implement-task` is the next skill: it reads `.plans/<n>-<slug>.md` and builds
test-first. If that plan file is missing when `implement-task` runs, that skill will stop and
point the user back here.
