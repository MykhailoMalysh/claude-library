# ai-sdlc agent contract

Shared by every agent in `${CLAUDE_PLUGIN_ROOT}/agents/` and every skill that dispatches them. An orchestrating skill can only merge results, detect failures, and route them to the `error-handler` agent if every agent answers in the same shape. This file defines that shape.

## Input: the task prompt

The orchestrator gives each agent a **context block** and a **task**. It passes references, not content: agents fetch the diff and files themselves, so large changes (hundreds of KB of diff) never get truncated inside a prompt.

```
## Context
repo:          /abs/path/to/repo
base_ref:      origin/develop            # merge target
head_ref:      HEAD                      # branch under review
merge_base:    eab30f6
diff_command:  git diff origin/develop...HEAD
changed_files: 115 files, +7842/-1647 (see `git diff --stat origin/develop...HEAD`)
requirements:  <ticket> / <mr_description> content, and/or path to a spec doc in the diff
profile:       <profile section="How the application works">…</profile> <profile section="How we build things here">…</profile>
notes:         <anything the user told the orchestrator that this agent needs, e.g. "use base_ref and head_ref, not HEAD">
contract:      /abs/path/to/ai-sdlc/references/agent-contract.md

## Task
<agent-specific instructions, e.g. the candidates to verify>
```

## Output: payload + status block

Every agent ends its answer with **exactly one** fenced `status` block as the final thing in the message. The status block is required: the orchestrator assigns `MALFORMED_OUTPUT` when it is missing or invalid, and when a `status: ok` block has no `evidence`. The payload block, if any, comes immediately before it; the one exception is the `verifier`, whose `verdicts` block comes first so it survives even if the reply runs long. Prose before the blocks is allowed; the orchestrator ignores it.

````
```findings
[{"file": "src/app/x.py", "line": 42, "summary": "...", "failure_scenario": "...", "angle": "correctness", "type": "bug"}]
```

```status
{"status": "ok", "code": "OK", "detail": "", "retryable": false,
 "evidence": ["git diff origin/develop...HEAD -- src/app/x.py: exit 0", "src/app/x.py:42"]}
```
````

A blocked agent that needs a human choice says so with `NEEDS_DECISION` and an `escalation`:

````
```status
{"status": "blocked", "code": "NEEDS_DECISION", "detail": "Two CI jobs share a name; unclear which one gates the MR.", "retryable": false,
 "escalation": {"question": "Which job should pre-flight run?", "options": ["test:unit", "test:unit-legacy"], "recommendation": "test:unit", "why": "Only test:unit has `rules: merge_request_event`."}}
```
````

| Field | Values |
|---|---|
| `status` | `ok`: task fully done. `partial`: done, but coverage was reduced (say what was skipped in `detail`). `blocked`: cannot proceed without something outside the agent's control (credential, tool, user input). `failed`: tried and broke. |
| `code` | One code from the catalog below. |
| `detail` | One or two sentences a human can act on: *what* failed and *what was tried*. Never include secret values. |
| `retryable` | `true` only if running the same task again, unchanged, could plausibly succeed (transient network error, timeout). |
| `evidence` | Required when `status: ok`. A non-empty list of strings, each either a command with its exit code (`"pytest tests/unit: exit 0"`) or a `file:line` the agent read to reach its result. Optional for other statuses. |
| `escalation` | Required when `status: blocked` with code `NEEDS_DECISION`: `{"question", "options": [..], "recommendation", "why"}`. `options` has at least two entries; `recommendation` is one of them. |

`partial` still carries a usable payload. `blocked` and `failed` may carry an empty payload (`[]`).

### Payload block types

| Block | Produced by | Shape |
|---|---|---|
| `findings` | `review-*` finders | `[{"file", "line", "summary", "failure_scenario", "angle", "type", "label"}]`, max 6, strongest first. `line` is 0 when the finding has no single line. `type` is `bug`, `project fit`, `refactor`, or `quality`. `label` (`blocking`, `suggestion`, `nit`) is optional; the orchestrator assigns the final label. A `project fit` finding names the `<profile>` section it relies on in `failure_scenario`. |
| `verdicts` | `verifier` | `[{"id", "verdict": "CONFIRMED"\|"PLAUSIBLE"\|"REFUTED", "reason", "anchor_file", "anchor_line"}]`. The `verdicts` block comes first in the reply, before any prose; a verifier reply without it is `MALFORMED_OUTPUT`. The error handler adds `"severity_unverified": true` to any verdict it transcribed from prose. |
| `report` | `griller` | Markdown with `### Critical gaps`, `### Important questions`, `### Nice-to-haves` |
| `decision` | `error-handler` | See `agents/error-handler.md` |
| `plan` | `preflight-planner` | `{"ci_files", "ci_hash", "jobs": [{"name", "stage", "reproducible", "where", "env", "env_files", "commands", "ci_script", "notes"}]}`. `where` is `sandbox`, `repo`, or `ci-only` (with `reproducible: false`). `env` inherits CI global variables. `env_files` lists file names only; agents never open them. See `agents/preflight-planner.md` |
| `implementation` | `dev-implement` subagents | `{"files_changed": [..], "tests_run": [{"cmd", "exit_code"}], "local_test_steps": [..], "notes"}`. `tests_run` lists every test command with its own exit code; `local_test_steps` are the steps a developer follows to check the change by hand. |
| `results` | `preflight-runner` | `{"job", "outcome": "passed"\|"failed"\|"error", "commands": [{"command", "exit", "log"}], "failures", "more_failures", "summary"}`. Each command carries its own exit code. A failing check is `outcome: failed` with status `ok`; only run failures are non-OK. |

## Error code catalog

Agents may only emit the codes in the upper table. The orchestrator assigns the lower table itself when an agent's reply is unusable. All non-`OK` statuses go to the `error-handler` agent.

**Agent-emitted**

| Code | Meaning | Typical example |
|---|---|---|
| `OK` | Task completed with full coverage. | |
| `PARTIAL_COVERAGE` | Finished, but some files or hunks were not examined. | Diff too large to read in full; binary files skipped. |
| `TOOL_MISSING` | A required executable is not available. | `python`, `glab`, `pytest` not on PATH. |
| `AUTH_FAILED` | A remote service rejected the credentials (401/403). | Jira or GitLab returned 401. |
| `CONFIG_MISSING` | A required env var or config file is absent. | `GITLAB_TOKEN` unset in the process env. |
| `REF_NOT_FOUND` | A git ref, file, or ticket in the context does not exist. | `origin/develop` not fetched, file deleted. |
| `DIFF_EMPTY` | The diff command produced nothing. | Branch has no commits ahead of base. |
| `NEEDS_DECISION` | The agent can proceed only after a human picks between options. Status is `blocked`; `escalation` is required. | Ambiguous CI job; two valid fixes with different trade-offs. |
| `CONTEXT_INSUFFICIENT` | The task cannot be judged without information the agent does not have. | Business-logic finder with no requirements. |
| `PLATFORM_UNSUPPORTED` | The requested remote operation is not supported for this host. | Asked to post to a host that is neither GitLab nor ADO. |
| `INTERNAL` | Anything else. Explain it in `detail`. | |

**Orchestrator-assigned**

| Code | Assigned when |
|---|---|
| `MALFORMED_OUTPUT` | The status block is missing or not valid JSON, the payload block does not parse, a `status: ok` block has no `evidence`, or a `NEEDS_DECISION` block has no `escalation`. |
| `AGENT_TYPE_UNAVAILABLE` | Dispatching `ai-sdlc:<agent>` failed because the agent type is not registered (plugin not reloaded, or an older Claude Code). |
| `AGENT_CRASHED` | The agent ended with a tool error, was stopped, or returned no text. |

## Rules for every agent

- **Read-only, except `dev-implement` work.** Agents never edit files, commit, push, post comments, or change remote state, with two exceptions. In-session subagents dispatched by `dev-implement` edit and test files in the working tree as their brief says, report them in an `implementation` payload, and do not commit; the dispatching session reviews and commits. Hub spokes running `dev-implement` in their own worktree also commit after each unit on their branch. Neither ever pushes or changes remote state. Only the orchestrator acts remotely, and only on explicit user request.
- **Don't fix the environment.** Don't install packages, change credentials, or edit config to get past a failure. Report it as `blocked` with the right code and let the error handler decide.
- **Don't include secrets in output.** Never open `.env` files; credentials come from the process env. Never echo tokens into `detail` or `evidence`.
- **Show your evidence.** Every `ok` result lists the commands (with exit codes) or `file:line` anchors it rests on. A claim without evidence is treated as not done.
- **Ask instead of guessing.** When the task forks on a choice only a human can make, return `blocked` + `NEEDS_DECISION` with an `escalation`; never fill the gap with a placeholder.
- **Say what you couldn't cover.** If you skipped part of the task, use `partial` + `PARTIAL_COVERAGE` and name what was skipped. The orchestrator reports coverage to the user honestly.
