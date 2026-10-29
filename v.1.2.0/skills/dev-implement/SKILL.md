---
name: dev-implement
description: Implement a bug fix or feature unit by unit, from the approved plan in the ticket's task file (written by dev-impl-plan) or from a bug/feature description. Two modes, Manual (confirm each unit) and Auto (front-load questions, then implement and commit without pausing). Checks every step against the project profile's forbidden paths and commands, and ends with a summary of what changed plus local test steps. Use when the developer says "implement this", "fix this bug", "build the plan", "start coding TICKET-123", or invokes /dev-implement. Also the skill a hub-dispatched agent runs for one task in its own worktree.
role: implementation
---

# dev-implement

Turns an approved plan or a bug/feature description into committed code, one logical unit at a time, and hands back a result the developer (or a hub session) can check.

## Invocation

```
/dev-implement [--auto | --manual] [TICKET-ID]
```

- `--auto`: ask all questions up front, then implement and commit each unit without pausing.
- `--manual`: confirm each unit before implementing it.
- No mode flag: ask the developer to pick before starting.
- No ticket ID: derive it from the branch name (see `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`), or work from the description the developer gave.

| | Manual | Auto |
|---|---|---|
| Questions | Before implementation | All up front, before implementation |
| Each unit | Wait for confirmation | Run immediately, one progress line after each |
| Commits | Automatic after each unit | Automatic after each unit |
| Blockers | Report and stop | Try to resolve from available information; otherwise report and pause |

**Spoke mode.** When a hub session dispatches this skill to an agent, the dispatch brief says so (for example "spoke mode" or "report to the hub"). Nobody is in the session to answer, so spoke mode runs as Auto mode. An approved plan in the task file or the hub brief counts as approval, so skip the plan-approval wait in step 3. Stop instead of waiting only for a real open question, a missing or unapproved plan, a forbidden-rule exception, or a blocker that needs a choice. A spoke commits each unit on its own worktree branch and never pushes (see the read-only rule in `agent-contract.md`). It returns `blocked` + `NEEDS_DECISION` with an `escalation` (`question`, `options`, `recommendation`, `why`) per the contract. Without such a statement in the brief, assume a developer is present.

## 1. Load the profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show
```

Treat the output as `<profile>`. Use `settings.base_branch` (fallback: the remote's default branch from `git symbolic-ref refs/remotes/origin/HEAD`), `settings.forbidden.paths`, `settings.forbidden.commands`, and the sections "How the application works", "How we build things here", and "Local testing flow".

With no profile (`{"profile": null, ...}`), fall back to the env configuration in `conventions.md`, treat the forbidden lists as empty, and suggest `/dev-profile-init` once in the end-of-run report. A missing profile never stops the run.

**Forbidden rules apply to every step**, including subagent briefs: never edit a path matching `forbidden.paths`, never run a command matching `forbidden.commands`. If the plan needs one, stop and ask the developer, naming the rule; the profile records these because they are unsafe or owned by someone else.

## 2. Intake

Read the input:

- **Task file** `{task_files_dir}/{ticket-number}.md` (profile `task_files_dir`, fallback `tasks/`): use its `## Approach`, `## Acceptance Criteria`, and `## Verification` as the plan. This is the normal path after `/dev-impl-plan`.
- **Ticket only**, no plan: fetch it with `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py` and wrap summary and description in `<ticket>`.
- **Description** from the developer: treat it as the requirements.

**Premise check before coding.** Run `git fetch origin` then check the plan against `origin/<base_branch>`: do the files, functions, and line numbers it names still exist, and is the bug still present (or the feature still missing)? Someone may have fixed or moved it since the plan was written. If the premise no longer holds, report what changed and stop.

## 3. Break down, clarify, plan

Read the relevant code (don't guess the root cause) and split the work into **units**: the smallest independently committable changes that together satisfy the requirements. "Fix three paths in one parser" is one unit; "update the agent count" is another.

Collect every open question into one numbered message: ambiguities, behaviour choices where the change could go several ways, scope (tests, docs). Skip anything the code answers. Wait for answers.

Present the plan and wait for approval (in spoke mode with an approved plan, print it and continue):

```
Implementation plan — {TICKET-ID or short title}

Units:
  1. {description} — {files} — commit: "{message}"
  2. ...

Mode: {Auto | Manual}
Proceed?
```

## 4. Implement

For each unit:

1. **Manual mode:** say what you are about to do and wait for "go".
2. When the unit touches a format, protocol, or external API (TOML, HTTP, a REST/GraphQL API, an RFC, a platform's config schema), read its spec first and implement what it requires, not what seems intuitive; Don't rely on memory of the spec, because specs change and have subtle rules. If no spec is available, ask rather than guess.
3. Make the change, following "How we build things here" in `<profile>`.
4. Run the tests covering the change (use `.venv/bin/python` / `.venv/bin/pytest` when the repo has a `.venv`). Record each command and exit code; they go into the final payload. When a unit has no tests (docs, config), verify it by reading the changed file back and record that `file:line` as evidence.
5. Commit in the project's style (read `git log --oneline -10` once and match prefix, tense, and ticket placement).
6. **Auto mode:** print one progress line, e.g. `Unit 2/4 committed: fix(parser): escape dotted keys — tests: exit 0. Next: update callers.`

**Delegation.** Work directly by default; units usually share state. Delegate to subagents only for units that are independent of each other, one subagent per repo for multi-repo work. Each brief contains: the goal, the files to read, what is already ruled out, the forbidden paths and commands from `<profile>`, the exact test commands (with `.venv/bin/python` where relevant), "do not commit; leave changes in the working tree" (in-session subagents never commit, per `agent-contract.md`), and the output contract: an `implementation` payload plus a `status` block per `${CLAUDE_PLUGIN_ROOT}/references/agent-contract.md`.

**Validate every subagent reply** before using it. Assign `MALFORMED_OUTPUT` when the `status` block is missing or invalid, the `implementation` payload does not parse, a `status: ok` block has no `evidence`, or a `NEEDS_DECISION` block has no `escalation`. For `NEEDS_DECISION`, put the `escalation` question, options, and recommendation to the developer. Route other non-OK results to the `ai-sdlc:error-handler` agent. After an interrupted subagent, check `git status` and `git diff` before re-dispatching. Review the delegated diff yourself, then commit it.

**Blockers.** In Auto mode, try to resolve a blocker from the code and plan. If it needs a human choice, stop, describe the options, and resume after the answer.

## 5. End-of-run report

Finish with a report to the developer:

```
Done — {TICKET-ID or short title}

Commits:
  {sha} {message}
  ...
Files changed: {list}
Tests run:
  {cmd}: exit {code}
Open items: {follow-ups, blockers resolved by the developer, or "none"}
Next: /dev-pr-open (it runs the CI pre-flight itself; use /dev-pr-preflight only to check early).

Local test steps:
  1. ...
```

Build **local test steps** from the profile's "Local testing flow", adapted to this change: which service to start, which endpoint or screen to hit, what result to expect. Steps that need `.env` values or the Databricks CLI are written as commands for the developer to run themselves, since this skill never opens `.env` or uses those credentials. Without a profile, derive the steps from the README and the tests, and suggest `/dev-profile-init`.

When running as a spoke agent dispatched by a hub session, end instead with the contract hand-back: an `implementation` block followed by one `status` block as the last thing in the message.

````
```implementation
{"files_changed": ["src/app/parser.py", "tests/test_parser.py"],
 "tests_run": [{"cmd": ".venv/bin/pytest tests/test_parser.py", "exit_code": 0}],
 "local_test_steps": ["make run", "curl localhost:8000/parse -d @sample.toml  # expect 200"],
 "notes": "Commits a1b2c3d, d4e5f6a. Dotted keys now escaped per TOML v1.0.0."}
```

```status
{"status": "ok", "code": "OK", "detail": "", "retryable": false,
 "evidence": [".venv/bin/pytest tests/test_parser.py: exit 0", "src/app/parser.py:88"]}
```
````

A `status: ok` without `evidence` is rejected by the hub as `MALFORMED_OUTPUT`, so list every test command with its exit code. Use `blocked` + `NEEDS_DECISION` with an `escalation` when a human choice is needed, and `partial` + `PARTIAL_COVERAGE` when some units were not done, naming them in `detail`.
