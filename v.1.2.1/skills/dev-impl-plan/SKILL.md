---
name: dev-impl-plan
description: Turn a Jira ticket into a written implementation plan — check the ticket's premises against the current code, explore the codebase, then use Claude Code's plan mode to design and present an approach for approval. Writes a plan only; never edits code or commits. Use when the developer says "let's plan this ticket", "create an implementation plan for TICKET-123", "how should I approach this", or invokes /dev-impl-plan — especially right after boarding a ticket with dev-task-start and before starting to code.
role: planning
compatibility:
  required_tools:
    - Bash
    - Read
    - Agent
    - EnterPlanMode
    - ExitPlanMode
---

# dev-impl-plan

Reads a ticket, checks what it claims against the code as it is today, explores the codebase, and writes an approved plan into the ticket's task file. It only plans: no code edits, migrations, or commits. `/dev-implement` turns the approved plan into code.

Tickets are often stale by the time work starts: migration numbers move, scan results predate the base branch, totals change, or the code lives in a sibling repo. So the plan rests on the code and on what the developer says in this session, not on the ticket text alone.

## 1. Load the profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show
```

Treat the output as `<profile>`. Use `settings.base_branch`, `settings.task_files_dir` (default `tasks/`), `settings.summaries_dir`, `settings.forbidden.paths`, `settings.forbidden.commands`, and the sections "How the application works", "How we build things here", and "Local testing flow".

With no profile (`{"profile": null, ...}`), use the env configuration in `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`, take the base branch from `git symbolic-ref refs/remotes/origin/HEAD`, treat the forbidden lists as empty, and suggest `/dev-profile-init` once at the end. A missing profile never stops the run.

## 2. Identify the ticket and gather requirements

- Use the ticket ID given as an argument or in the conversation; otherwise derive it from the branch name (see `conventions.md`). With neither, ask for a ticket key or a plain description; a plan can be built from a description.
- Read `{task_files_dir}/{ticket-number}.md` if it exists (seeded by `dev-task-start`; structure in `conventions.md`). Its Context, Decisions, and Questions are prior work. If open "Questions for the team" block scoping the plan, resolve them with the developer now (`AskUserQuestion`) before any design work builds on them.
- Otherwise fetch the ticket with `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py get --key <TICKET-KEY>` (credentials come from the process env), wrap summary and description in `<ticket>`, and create the task file from the template.
- Pull out the acceptance criteria in `<ticket>`. If there are none and scope is ambiguous, ask the developer before exploring.

## 3. Premise check

Before designing anything, compare three sources:

1. What `<ticket>` and the task file claim (files, migration numbers, counts, scan results, endpoints, which repo).
2. The code on `origin/<base_branch>`: run `git fetch origin`, then check each claim with `git grep`, `git show origin/<base_branch>:<path>`, and `git log origin/<base_branch> -- <path>`.
3. What the developer said in this session, which overrides the ticket when they conflict.

Also read sibling task notes in `summaries_dir` (`ls`, then the notes for related tickets) before quoting any shared source such as a scan report, migration list, or spreadsheet, so you don't repeat a number a teammate already found to be wrong.

List every mismatch as a decision for the developer, in one message:

```
Premise drift:
1. Ticket says migration 0042; origin/develop already has 0042_add_index.py. Next free is 0045. Use 0045?
2. Ticket's scan (2026-09-12) predates 31 commits on develop; 3 of 7 findings no longer reproduce. Plan only the remaining 4?
```

Wait for answers. Record each answer in the task file's "Decisions already made". If the premise fails entirely (already fixed, code is in another repo), report that and stop.

## 4. Explore in plan mode

Call `EnterPlanMode`, then:

1. Split the ticket into independent areas (for example API layer, data model, frontend, CI). For two or more areas, dispatch one `Explore` agent per area in a single message so they run in parallel. Each brief names the area, the base ref, the paths to start from, and asks for `file:line` anchors. A single small area you explore directly.
2. Read what the agents point to before relying on it. Every claim in the plan names a real file, function, and, where it helps, a line number; if you can't name it yet, keep exploring.
3. Check every planned step against `forbidden.paths` and `forbidden.commands`. A step that needs one becomes a question for the developer naming the rule, not a silent workaround.
4. When there is a real fork in approach (two valid designs, a library choice), ask with `AskUserQuestion` before finalizing.

## 5. Write the plan into the task file

Extend `{task_files_dir}/{ticket-number}.md` in place; `/dev-implement` reads these sections:

- **Approach**: the design as ordered steps, naming real files and functions, and why; rejected alternatives when the choice wasn't obvious.
- **Acceptance Criteria**: from `<ticket>`, corrected by the premise check, or drafted with the developer.
- **Verification**: one check per acceptance criterion (tests to add or run), then a **Local test steps** list the developer can follow by hand, based on the profile's "Local testing flow".

Move resolved questions into "Decisions already made" and delete them from "Questions for the team". Anything you couldn't verify in code goes into Questions, not Decisions.

## 6. Request approval

Call `ExitPlanMode`. Once approved, stop. Tell the developer the plan is in `{task_files_dir}/{ticket-number}.md` and that `/dev-grill-me` can stress-test it and `/dev-implement` can build it.

## Error handling

| Situation | Action |
|---|---|
| No ticket key and no description | Ask for one or the other. |
| Jira credentials missing or ticket not found | Name the missing variable with the `settings.local.json` line to add, or ask the developer to paste the ticket; build the task file from that. |
| Premise drift found | List it as decisions (step 3) and wait. |
| Code lives in a sibling repo | Report the repo and stop; the plan belongs in that repo's session. |
| A step needs a forbidden path or command | Ask the developer, naming the rule. |
| A claim can't be verified in code | Put it in "Questions for the team". |
