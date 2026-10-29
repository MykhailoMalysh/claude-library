# ai-sdlc shared conventions

Read via `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` from any skill. This is the canonical source for configuration (env variables and profiles), working gotchas, and the branch/ticket naming convention shared across `ai-sdlc` skills — individual `SKILL.md` files should link here instead of re-documenting these values.

## Configuration

Variables live in the `env` block of the target repo's gitignored `.claude/settings.local.json`; Claude Code puts them in the process environment of every skill, agent, and `lib/` CLI. Skills and agents never open `.env` files and never print secret values. No skill hardcodes a project key, org name, or instance URL — everything below is repo-specific and read at runtime.

```json
{
  "env": {
    "AI_SDLC_PROFILE": "myproject",
    "JIRA_URL": "https://jiraeu.epam.com",
    "JIRA_PROJECT": "EPMPMVISTC"
  }
}
```

### Profile lookup order

Per-project settings beyond credentials (base branch, branch pattern, Jira statuses, forbidden paths/commands) come from a private profile, read with `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show [--section NAME]`:

1. `AI_SDLC_PROFILE` (env) names the profile: `<profiles dir>/<name>.md`.
2. Otherwise, the profile whose frontmatter `remotes` matches `git remote get-url origin`.
3. Otherwise there is no profile: fall back to the env variables below and suggest `/dev-profile-init`. A missing profile is never an error.

The profiles dir is `~/.claude/ai-sdlc/profiles/`, overridable with `AI_SDLC_PROFILES_DIR`. Template: `${CLAUDE_PLUGIN_ROOT}/references/profile-template.md`.

### Variables

| Variable | Required by | Purpose |
|---|---|---|
| `JIRA_PROJECT` | `pm-create-ticket`, `dev-task-start`, `dev-pr-open`, `dev-pr-review` | Jira project key (e.g. `EPMPMVISTC`), combined with the numeric ticket suffix parsed from the branch name to form a ticket key. |
| `JIRA_URL` | `pm-create-ticket`, `dev-task-start`, `dev-impl-plan`, `dev-pr-open`, `dev-pr-review` | Base URL of the Jira instance (e.g. `https://jiraeu.epam.com`) — the Jira REST API base used by `lib/jira_client.py`, and also used to build ticket links in `dev-pr-open`'s success message. |
| `JIRA_USERNAME` | `pm-create-ticket`, `dev-task-start`, `dev-impl-plan`, `dev-pr-open`, `dev-pr-review` | Jira account (e.g. `first_last@epam.com`) — the basic-auth username for the Jira REST API, also used for ticket assignment and querying "assigned to me". Optional where the skill only reads tickets; skills fall back to asking the user. |
| `JIRA_API_TOKEN` | `pm-create-ticket`, `dev-task-start`, `dev-impl-plan`, `dev-pr-open`, `dev-pr-review` | Jira Personal Access Token — the basic-auth password for the Jira REST API, paired with `JIRA_USERNAME`. |
| `JIRA_IN_REVIEW_STATUS` | `dev-pr-open` | The literal Jira status name backing the "In Review" board column for this project's workflow (workflows vary — the column is not always literally named "In Review"). Optional but recommended; ask the user once if unset. |
| `GIT_USERNAME` | `dev-task-start`, `dev-pr-open` | Short username used in branch names (e.g. `mykhailo`). |
| `ADO_ORG` | `dev-pr-open` (Azure DevOps repos only), `dev-pr-address-comments`, `dev-pr-review` (posting on request only) | Azure DevOps organization name. |
| `ADO_PROJECT` | `dev-pr-open` (Azure DevOps repos only), `dev-pr-address-comments`, `dev-pr-review` (posting on request only) | Azure DevOps project name. |
| `ADO_REPO` | `dev-pr-open` (Azure DevOps repos only), `dev-pr-address-comments`, `dev-pr-review` (posting on request only) | Azure DevOps repository name. |
| `ADO_PAT` | `dev-pr-open` (Azure DevOps repos only), `dev-pr-address-comments`, `dev-pr-review` (posting on request only) | Personal Access Token with "Code (Read & Write)" scope. Generate at `https://dev.azure.com/{ADO_ORG}/_usersSettings/tokens`. |
| `GITLAB_URL` | `dev-pr-review`, `dev-pr-open` (GitLab repos only) | Base URL of the GitLab instance — must be the instance root (e.g. `https://git.epam.com`), not a project URL. Used by `lib/gitlab_client.py` to read MR context during review, post comments only when the developer explicitly asks, and (for `dev-pr-open`) check for/create merge requests. |
| `GITLAB_TOKEN` | `dev-pr-review`, `dev-pr-open` (GitLab repos only) | GitLab access token sent as `PRIVATE-TOKEN`. `read_api` scope is enough for `dev-pr-review`'s default read-only use; `api` scope is needed to post comments or for `dev-pr-open` to check for/create merge requests. |
| `GITLAB_PROJECT` | `dev-pr-review`, `dev-pr-open` (both optional) | Project path (`group/subgroup/repo`). Derived from the `origin` remote when unset. |
| `PRE_PR_VERIFY_CMD` | `dev-pr-preflight`, `dev-pr-open` (optional) | Overrides the pipeline-derived pre-flight plan with a single command. Use only when the pipeline can't be reproduced locally. Confirmed pipeline-derived plans are saved outside the repo in `~/.claude/ai-sdlc-data/preflight/`. |

If a required variable isn't set, the invoking skill names it, shows the exact line to add to the `env` block of `.claude/settings.local.json` (for example `"GITLAB_TOKEN": "<your token>"`), and stops — or asks the user directly, for optional variables. Never guess a project-specific value.

## Working gotchas

- **macOS.** BSD `sed` needs `sed -i ''` for in-place edits. Use `python3`, not `python`.
- **Virtualenvs.** When the project has a `.venv`, write `.venv/bin/python` (or `.venv/bin/pytest`) into subagent briefs; a fresh shell does not inherit an activated venv.
- **After an interrupted subagent,** inspect disk and git state (`git status`, `git diff`, `git log -3`) before re-dispatching; part of the work may already be done.
- **Destructive commands** (database resets, fixture reloads, `docker compose down -v`): pass the test level or target explicitly, and confirm with the developer what gets dropped and recreated before running.

## Branch naming and ticket-key derivation

Feature branches follow the profile's `branch_pattern`, by default:

```
user/{username}/{ticket}-{description}
```

`{username}` is the git username, `{ticket}` the numeric part of the ticket key, `{description}` the short slug. A custom `branch_pattern` uses the same three placeholders.

Example: `user/mykhailo/42-optimize-database-query-cach`.

To derive the full Jira ticket key from a branch name: match the branch against the pattern, take the `{ticket}` part, and prefix it with `JIRA_PROJECT`. Example: `JIRA_PROJECT=EPMPMVISTC` + branch `user/mykhailo/42-foo` → `EPMPMVISTC-42`.

If a branch doesn't match this pattern, ask the user for the Jira ticket key (or PR/ticket description) directly rather than guessing. This parsing logic is also centralized programmatically in `${CLAUDE_PLUGIN_ROOT}/lib/branch_utils.py` for skills that shell out to the `lib/` CLIs — this document describes the same rule for skills (like `dev-pr-review`) that apply it directly in prose rather than through a script call.

## Task file convention

Each ticket has one **task file** at:

```
{task_files_dir}/{ticket-number}.md
```

`task_files_dir` comes from the profile (default `tasks/`); the file name is the numeric part only, e.g. `tasks/42.md` for `EPMPMVISTC-42`. Create the directory at the repo root if it doesn't exist. The file is the running record for the ticket, so a developer looks in one place for everything known about it:

- `dev-task-start` creates and seeds it.
- `dev-impl-plan` extends it with the approach instead of writing a separate plan document.
- `dev-implement` builds from its Approach, Acceptance Criteria, and Verification sections.
- `dev-grill-me` and `dev-prototype` read it for context; `dev-prototype` may add findings under "Decisions already made".

**Structure** (sections are additive — later skills append/extend, they don't replace earlier content):

```markdown
# {TICKET-KEY} — {summary}

- **Type:** ... | **Status:** ... | **Priority:** ...
- **Assignee:** ... | **Reporter:** ...
- **Created:** ... | **Updated:** ...

## Context
[From the ticket description/comments — why this work exists, not restated boilerplate]

## Decisions already made
[Settled facts and choices — no team input needed. Each one must be traceable to either (a) the
ticket/comments, (b) something the developer explicitly confirmed, or (c) something verified
directly in the code (see "Verify in code" below) — never an assumption stated as fact.]

## Questions for the team — raise in standup
[Only what's still genuinely open, each as a one-line ready-to-ask question. When a question is
fully answered, delete it from this list and fold the resolved content into "Decisions already
made" — don't leave it here annotated as "[ANSWERED]". If only part of a question is resolved,
split it: move the settled part to Decisions, keep only the narrower remaining unknown here.]

## Findings
[Investigation detail and reasoning — reference material, not for reading aloud in standup.]

## Approach
[Added by dev-impl-plan: the design, naming real files/functions/line numbers found during
exploration — never placeholders.]

## Acceptance Criteria
[From the ticket, or drafted with the developer if the ticket doesn't have any]

## Verification
[Added by dev-impl-plan: how each Acceptance Criterion will be checked once implemented — maps
one-to-one to the criteria above]

## Blocked by
[External dependencies — access, another team's ticket, an admin action]

## Testing
[What test tier/type covers this, once known]
```

**Verify in code, don't assume from the ticket text.** Before writing anything into "Decisions
already made" or "Findings" as settled fact, check it against the actual code — grep for the
relevant endpoint/class/function and read it, don't infer behavior from the ticket description or
a comment alone. A ticket's own description can be wrong or stale (e.g. mischaracterizing what a
linked branch actually implements) — the code is the source of truth. If something can't be
verified this way (it depends on a decision only a person can make, or on infrastructure state
outside the repo), it belongs in "Questions for the team", not "Decisions already made".
