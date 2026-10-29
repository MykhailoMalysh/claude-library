# ai-sdlc

A Claude Code plugin for the Jira → branch → PR → review → merge workflow: board a ticket, plan it, implement it, open the PR, review it, and close out reviewer comments — without leaving the terminal.

## Skills

### Planning

| Skill | Use it when... |
|---|---|
| [`dev-profile-init`](skills/dev-profile-init/SKILL.md) | You're setting up a repo: creates or updates the private project profile (base branch, branch pattern, Jira statuses, forbidden paths, how the app works) and proposes the `settings.local.json` additions. |
| [`dev-wayfinder`](skills/dev-wayfinder/SKILL.md) | A large initiative is too big for one session — chart it as a map of decision points in a markdown document, resolve decisions one at a time until the path is clear. |
| [`dev-prototype`](skills/dev-prototype/SKILL.md) | You need to answer a design question with throwaway code — either a shareable HTML demo for logic/state, or multiple UI variations to explore options. |
| [`dev-impl-plan`](skills/dev-impl-plan/SKILL.md) | You've picked up a ticket and want a written implementation plan (via Claude Code's plan mode) before touching any code. Plans only — never implements. |
| [`dev-grill-me`](skills/dev-grill-me/SKILL.md) | You want to be challenged on your approach — adversarial interview to poke holes in a plan or design before implementation. |
| [`dev-pr-review`](skills/dev-pr-review/SKILL.md) | You want a project-aware review of your own branch or a teammate's MR. Uses the profile's "How the application works" and "How we build things here"; quick (small diffs), standard (default), or full level; verifies every finding and returns one shareable review block. Nothing is posted unless you ask. |

### Implementation

| Skill | Use it when... |
|---|---|
| [`dev-task-start`](skills/dev-task-start/SKILL.md) | You're ready to start work: shows your assigned sprint tickets, creates a feature branch, moves the ticket to In Progress. |
| [`dev-implement`](skills/dev-implement/SKILL.md) | You're ready to implement a bug fix or feature from the approved plan or a description, unit by unit, Manual (confirm each) or Auto mode. Honors the profile's forbidden paths and ends with local test steps. |
| [`dev-pr-preflight`](skills/dev-pr-preflight/SKILL.md) | You want to know whether CI will pass before opening a PR. Reads the pipeline file, runs its checks locally in check-only mode, changes nothing in the repo. |
| [`dev-pr-open`](skills/dev-pr-open/SKILL.md) | Your branch is ready for review: runs pre-flight CI checks, then opens the Azure DevOps PR and updates the linked Jira ticket. |
| [`dev-pr-address-comments`](skills/dev-pr-address-comments/SKILL.md) | You're the PR author working through reviewer comments — fix, reply, resolve, or skip each one, one at a time. Azure DevOps only for now; GitLab support is pending. |
| [`dev-task-summary`](skills/dev-task-summary/SKILL.md) | The task is done or its MR is open: saves a short note on how the ticket was solved to the Obsidian vault. |

### Team

| Skill | Use it when... |
|---|---|
| [`pm-create-ticket`](skills/pm-create-ticket/SKILL.md) | You want to create a new Jira ticket (task, sub-task, story, or bug) with the team's standard description format. |

Typical flow: `pm-create-ticket` → `dev-task-start` → [`dev-wayfinder` for large initiatives] → `dev-impl-plan` → [`dev-prototype` to validate design] → `dev-implement` → [`dev-pr-preflight`] → `dev-pr-open` → `dev-pr-review` (on someone else's branch) / `dev-pr-address-comments` (on your own, once reviewed).

## Installation

Load it locally while developing:

```bash
claude --plugin-dir /path/to/ai-sdlc
```

Or install it from wherever it's distributed (marketplace, git) per your team's usual plugin install process, then run `/reload-plugins`.

All Jira and Azure DevOps access goes through the shared `lib/` Python package, driven by plain REST calls — no MCP server required. Credentials live in each project's `.claude/settings.local.json` (see below), not in plugin-level config.

## Per-project setup

Each project you use these skills in needs an `env` block in its gitignored `.claude/settings.local.json` — project-specific values (Jira project key/URL/token, ADO org/repo/PAT) that must never be hardcoded into the plugin itself. Start from [`references/settings-local.example.json`](references/settings-local.example.json). Skills never read `.env` files.

Setup in three steps:

1. Run `/dev-profile-init` to create the private profile (base branch, branch pattern, Jira statuses, forbidden paths and commands, how the app works, local testing flow). It lives in `~/.claude/ai-sdlc/profiles/` and is selected by `AI_SDLC_PROFILE` or by matching its `remotes` against `origin`.
2. Put `AI_SDLC_PROFILE` and the credentials in the `env` block of `.claude/settings.local.json`.
3. Add the proposed deny rules (for example reading `.env`) to the same file. They are shown to you and applied only on approval.

Without a profile the skills fall back to env-var config and suggest `/dev-profile-init`.

See [`references/conventions.md`](references/conventions.md) for:
- The full `env` variable schema — what each variable does and which skills need it
- The `user/{username}/{ticket}-{description}` branch naming convention and how the Jira ticket key is derived from it

Not every variable is needed for every skill — a project that only uses `pm-create-ticket` and `dev-task-start` doesn't need the `ADO_*` variables, for instance. Each skill's own Configuration section lists exactly which variables it reads.

## Shared agents (`agents/`)

Review work is done by plugin-level agents that any skill can dispatch as `ai-sdlc:<name>`:

| Agent | Used by | Role |
|---|---|---|
| `review-correctness`, `review-business-logic`, `review-security` | `dev-pr-review` (standard level) | Finders for the core review angles |
| `review-removed-behavior`, `review-cross-file`, `review-simplification`, `review-conventions` | `dev-pr-review` (full level; cross-file also on dependency changes) | Finders for optional angles |
| `verifier` | `dev-pr-review` | Confirms, downgrades, or refutes candidate findings with evidence |
| `griller` | `dev-grill-me`, `dev-pr-review` (on request) | Adversarial design interviewer |
| `preflight-planner`, `preflight-runner` | `dev-pr-preflight` (and `dev-pr-open` via it) | Translate the CI pipeline into local check-only commands; run one job and summarise failures |
| `error-handler` | `dev-pr-review`, `dev-grill-me`, `dev-pr-preflight` | Diagnoses any non-OK agent status and picks the next step (one retry, then ask you) |

Every agent follows [`references/agent-contract.md`](references/agent-contract.md): a shared context block in, a payload plus a `status` block with an error code out. All agents are read-only.

## Shared `lib/` package

`pm-create-ticket`, `dev-task-start`, `dev-impl-plan`, `dev-pr-open`, and `dev-pr-review` drive Jira through a shared Python package at `lib/`, and `dev-pr-open` and `dev-pr-address-comments` drive Azure DevOps the same way (`dev-pr-review` uses ADO or GitLab only when asked to post) (not a single CLI — plain modules + small argparse entrypoints, built to be unit-tested):

- `jira_client.py` — `JiraClient`, all Jira REST calls (get/search issues, create issue, transition, add comment)
- `ado_client.py` — `ADOClient`, all ADO REST calls (PR check/create/update, comment thread list/post/reply/resolve)
- `gitlab_client.py` + `cli_gitlab.py` — `GitLabClient`, MR read (`mr-get`) and note/inline-discussion posting (`note`), used by `dev-pr-review`
- `branch_utils.py` — shared branch-name → ticket-key parsing
- `cli_jira.py` / `cli_pr.py` / `cli_comment.py` — thin CLI wrappers the skills shell out to

Requires `requests` (and `pytest` for running the tests):

```bash
pip install -r lib/requirements.txt
python3 -m pytest lib/tests/ -q
```

Skills reference this package via `${CLAUDE_PLUGIN_ROOT}/lib/...`, which Claude Code substitutes with the plugin's actual install path — this works regardless of how the plugin was installed (skills-dir, marketplace, `--plugin-dir`), so there's nothing to configure here beyond the `pip install`.

## Migrating from v1.1.0

- `dev-bug-fix` is replaced by `dev-implement` (bug or feature, Manual or Auto mode).
- Credentials move from `.env` to the `env` block of `.claude/settings.local.json`; skills no longer read `.env`. Start from `references/settings-local.example.json`.
- Run `/dev-profile-init` in each project to create the new profile.
