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
requirements:  <ticket summary + description, MR description, and/or path to a spec doc in the diff>
notes:         <anything the user told the orchestrator that this agent needs>
contract:      /abs/path/to/ai-sdlc/references/agent-contract.md

## Task
<agent-specific instructions, e.g. the candidates to verify>
```

## Output: payload + status block

Every agent ends its answer with **exactly one** fenced `status` block as the final thing in the message. The payload block, if any, comes immediately before it. Prose before the blocks is allowed; the orchestrator ignores it.

````
```findings
[{"file": "src/app/x.py", "line": 42, "summary": "...", "failure_scenario": "...", "angle": "correctness"}]
```

```status
{"status": "ok", "code": "OK", "detail": "", "retryable": false}
```
````

| Field | Values |
|---|---|
| `status` | `ok`: task fully done. `partial`: done, but coverage was reduced (say what was skipped in `detail`). `blocked`: cannot proceed without something outside the agent's control (credential, tool, user input). `failed`: tried and broke. |
| `code` | One code from the catalog below. |
| `detail` | One or two sentences a human can act on: *what* failed and *what was tried*. Never include secret values. |
| `retryable` | `true` only if running the same task again, unchanged, could plausibly succeed (transient network error, timeout). |

`partial` still carries a usable payload. `blocked` and `failed` may carry an empty payload (`[]`).

### Payload block types

| Block | Produced by | Shape |
|---|---|---|
| `findings` | `review-*` finders | `[{"file", "line", "summary", "failure_scenario", "angle"}]`, max 6, strongest first. `line` is 0 when the finding has no single line. |
| `verdicts` | `verifier` | `[{"id", "verdict": "CONFIRMED"\|"PLAUSIBLE"\|"REFUTED", "reason", "anchor_file", "anchor_line"}]` |
| `report` | `griller` | Markdown with `### Critical gaps`, `### Important questions`, `### Nice-to-haves` |
| `decision` | `error-handler` | See `agents/error-handler.md` |
| `plan` | `preflight-planner` | `{"ci_files", "ci_hash", "jobs": [{"name", "stage", "reproducible", "where", "env", "env_files", "commands", "ci_script", "notes"}]}`; see `agents/preflight-planner.md` |
| `results` | `preflight-runner` | `{"job", "outcome": "passed"\|"failed"\|"error", "commands", "failures", "more_failures", "summary"}`. A failing check is `outcome: failed` with status `ok`; only run failures are non-OK. |

## Error code catalog

Agents may only emit the codes in the upper table. The orchestrator assigns the lower table itself when an agent's reply is unusable. All non-`OK` statuses go to the `error-handler` agent.

**Agent-emitted**

| Code | Meaning | Typical example |
|---|---|---|
| `OK` | Task completed with full coverage. | |
| `PARTIAL_COVERAGE` | Finished, but some files or hunks were not examined. | Diff too large to read in full; binary files skipped. |
| `TOOL_MISSING` | A required executable is not available. | `python`, `glab`, `pytest` not on PATH. |
| `AUTH_FAILED` | A remote service rejected the credentials (401/403). | Jira or GitLab returned 401. |
| `CONFIG_MISSING` | A required env var or config file is absent. | `GITLAB_TOKEN` unset, no `.env`. |
| `REF_NOT_FOUND` | A git ref, file, or ticket in the context does not exist. | `origin/develop` not fetched, file deleted. |
| `DIFF_EMPTY` | The diff command produced nothing. | Branch has no commits ahead of base. |
| `CONTEXT_INSUFFICIENT` | The task cannot be judged without information the agent does not have. | Business-logic finder with no requirements. |
| `PLATFORM_UNSUPPORTED` | The requested remote operation is not supported for this host. | Asked to post to a host that is neither GitLab nor ADO. |
| `INTERNAL` | Anything else. Explain it in `detail`. | |

**Orchestrator-assigned**

| Code | Assigned when |
|---|---|
| `MALFORMED_OUTPUT` | The status block is missing or not valid JSON, or the payload block does not parse. |
| `AGENT_TYPE_UNAVAILABLE` | Dispatching `ai-sdlc:<agent>` failed because the agent type is not registered (plugin not reloaded, or an older Claude Code). |
| `AGENT_CRASHED` | The agent ended with a tool error, was stopped, or returned no text. |

## Rules for every agent

- **Read-only.** Agents never edit files, commit, push, post comments, or change remote state. Only the orchestrator acts, and only on explicit user request.
- **Don't fix the environment.** Don't install packages, change credentials, or edit config to get past a failure. Report it as `blocked` with the right code and let the error handler decide.
- **Don't include secrets in output.** When an env file is needed, read variable names, not values. Never echo tokens into `detail`.
- **Say what you couldn't cover.** If you skipped part of the task, use `partial` + `PARTIAL_COVERAGE` and name what was skipped. The orchestrator reports coverage to the user honestly.
