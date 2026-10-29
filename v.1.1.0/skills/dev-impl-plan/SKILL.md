---
name: dev-impl-plan
description: Turn a Jira ticket into a written implementation plan — explore the codebase, then use Claude Code's plan mode to design and present an approach for approval. Writes a plan only; never edits code or commits. Use when the developer says "let's plan this ticket", "create an implementation plan for TICKET-123", "how should I approach this", or invokes /dev-impl-plan — especially right after boarding a ticket with dev-task-start and before starting to code.
compatibility:
  required_tools:
    - Bash
    - Read
    - EnterPlanMode
    - ExitPlanMode
---

# dev-impl-plan

Bridges ticket intake and implementation: reads a Jira ticket's requirements, explores the codebase for the relevant context, and produces a written implementation plan via Claude Code's plan mode. This skill only plans — it never edits files, runs migrations, or commits. Turning the approved plan into code is a separate, explicit step (e.g. `/dev-bug-fix`, or the developer working manually).

## When to Use

- Developer says "let's plan this ticket", "create an implementation plan", "how should I approach TICKET-123"
- Developer invokes `/dev-impl-plan`
- Right after `/dev-task-start` boards a ticket and before any code gets written — this is the natural next step once a ticket is picked up but before implementation begins

Do not use this skill to implement anything. If the developer wants code written now, that's `/dev-bug-fix` or a direct implementation request, not this skill.

## Prerequisites

See `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` for the full `.env` schema and branch naming convention. This skill reads `JIRA_PROJECT` to resolve a ticket key from the current branch when one isn't given explicitly, and `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` to fetch the ticket via the Jira REST API.

The Jira calls run through the shared `lib/` Python package at `${CLAUDE_PLUGIN_ROOT}/lib/`. It needs `requests` installed — `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt` if it isn't already available.

## Workflow

### Step 1: Identify the ticket

- If a ticket ID was given directly (as an argument or in the conversation), use it.
- Otherwise, get the current branch (`git branch --show-current`) and derive the ticket key per the branch naming convention.
- If neither yields a ticket key, ask the developer for the ticket key, or for a description of the work if there's no ticket yet — a plan can still be built from a plain description.

### Step 2: Gather requirements

First check for an existing task file at `tasks/{ticket-number}.md` (the shared convention in
`${CLAUDE_PLUGIN_ROOT}/references/conventions.md` — created by `dev-task-start` when the ticket was
boarded). If it exists, treat it as the starting point: its Context, Decisions already made, and
Questions for the team are prior work, not something to re-derive from scratch. If any "Questions
for the team" are still open and block scoping the plan, resolve them with the developer now (via
`AskUserQuestion` or by asking directly) rather than guessing — this is the natural point to close
them before design work builds on an unresolved fork.

If no task file exists yet, fetch the ticket directly:
```bash
export JIRA_URL JIRA_USERNAME JIRA_API_TOKEN
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py get --key <TICKET-KEY>
```
Extract `summary` and `description` from the JSON output, and create `tasks/{ticket-number}.md`
using the shared template before continuing.

If the description follows the team's ticket format (Context / Acceptance Criteria / Blocked by / Testing — see `pm-create-ticket`), pull out the Acceptance Criteria explicitly; the plan's verification section should map back to them one-to-one. If the description is freeform, work from it as-is.

If the ticket has no clear acceptance criteria and the ask is ambiguous, ask the developer directly rather than guessing scope — an implementation plan built on a guessed scope wastes the exploration effort in Step 3.

### Step 3: Enter plan mode and explore

Call `EnterPlanMode`. Once in plan mode:

1. Explore the codebase for everything the ticket touches — existing patterns, the files most likely to change, related tests, prior art for similar changes. Use Explore agents for anything spanning more than a couple of files.
2. **Verify every claim against the actual code before it goes in the plan** — grep for the
   relevant endpoint/class/function and read it; don't infer behavior from the ticket description,
   a comment, or a prior teammate's summary of it. Tickets and comments can be stale or wrong. This
   is what turns "Findings" in the task file from guesses into something the developer can trust
   enough to act on.
3. Identify the exact approach: which real files, functions, and (where it aids precision) line
   numbers change, and why — including alternatives you considered and rejected, if the choice
   wasn't obvious. Placeholders ("the relevant service file") are not acceptable in the final plan —
   if you can't name the real file/function yet, keep exploring.
4. If there's a genuine fork in approach (e.g. two valid architectures, a library choice) that
   wasn't already resolved via the task file's Questions in Step 2, use `AskUserQuestion` to resolve
   it before finalizing the plan — don't silently pick one and hope it's right.

### Step 4: Write the plan into the task file

Extend `tasks/{ticket-number}.md` in place (don't create a separate plan file) by adding/filling:

- **Approach** — the design, naming real files/functions found during exploration and why
- **Verification** — how each Acceptance Criterion will be checked once implemented (tests to
  add/run, manual steps) — mapped one-to-one; a criterion with no corresponding verification step
  is a sign the plan doesn't fully cover the ticket

Also apply the task-file's tracking rule now: any "Questions for the team" resolved during Step 2
or Step 3 should be moved into "Decisions already made" and deleted from the Questions list — don't
leave them there annotated as answered.

### Step 5: Request approval

Call `ExitPlanMode`. Once approved, stop — do not begin implementing. Tell the developer the plan is ready in `tasks/{ticket-number}.md` and that they can start implementation (e.g. via `/dev-bug-fix`, or manually) whenever they're ready; this skill's job ends at an approved plan.

## Error Handling

| Situation | Action |
|---|---|
| No ticket key resolvable and no description given | Ask the developer for a ticket key or a plain-text description of the work |
| No task file and Jira credentials missing/`requests` not installed/ticket not found | Ask the developer to paste the ticket/requirements directly, and create `tasks/{ticket-number}.md` from that |
| Task file has unresolved "Questions for the team" that block scoping | Resolve them with the developer now, before exploring — don't guess |
| Ticket has no clear acceptance criteria and scope is ambiguous | Ask the developer to clarify scope before exploring — don't guess |
| A genuine architectural fork appears during exploration | Use `AskUserQuestion` to resolve it before finalizing the plan |
| A claim can't be verified in the actual code | Don't write it into Approach/Decisions as fact — put it in "Questions for the team" instead |

## Why This Workflow

Jumping straight into code on a non-trivial ticket means design decisions get made ad hoc, mid-implementation, without the developer having seen the full shape of the change first. This skill forces the design conversation to happen up front, grounded in the ticket's actual acceptance criteria and the codebase as it really is — not the ticket's description of it, which can be stale or wrong — and stops there. It builds on the same `tasks/{ticket-number}.md` file `dev-task-start` seeds, so a ticket has one running record instead of scattered context, and it deliberately does not implement, so a plan can be reviewed, redirected, or discarded before any code exists to unwind.
