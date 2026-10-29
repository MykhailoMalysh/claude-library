---
name: dev-pr-open
description: Create a pull/merge request from the current branch (Azure DevOps or GitLab, detected from the origin remote) and update the linked Jira ticket (transition to the "In Review" board column, add a comment with the PR/MR link). Use when the developer says "open a PR", "create the PR/MR", "open a pull request for this branch", or invokes /dev-pr-open.
compatibility:
  required_tools:
    - Bash
    - Read
---

# dev-pr-open

Creates a pull request (Azure DevOps) or merge request (GitLab) for the current branch with a generated description, then updates the linked Jira ticket to reflect that it's open. Which host to use is detected automatically from `git remote get-url origin` — no need to tell it which one.

## When to Use

- Developer says "open a PR", "create the PR/MR", "open a pull request for this branch"
- Developer invokes `/dev-pr-open`
- The current branch has commits ready for review and follows the `user/{username}/{ticket}-{desc}` naming convention

## Prerequisites

See `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` for the full `.env` schema and branch naming convention. This skill reads `GIT_USERNAME`, `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, `JIRA_IN_REVIEW_STATUS` always, plus one of the following depending on the detected host (Step 1):

- **Azure DevOps** (origin remote is `dev.azure.com` or `visualstudio.com`): `ADO_ORG`, `ADO_PROJECT`, `ADO_REPO`, `ADO_PAT`. Generate a PAT with "Code (Read & Write)" scope at `https://dev.azure.com/{ADO_ORG}/_usersSettings/tokens`.
- **GitLab** (any other origin remote host, e.g. a self-hosted instance like `git.epam.com`): `GITLAB_URL`, `GITLAB_TOKEN` (optionally `GITLAB_PROJECT`, otherwise derived from the origin remote). `GITLAB_URL` must be the instance root (e.g. `https://git.epam.com`), not a project URL — a project-path URL looks valid but every API call silently 404s into GitLab's HTML SAML-redirect page instead of JSON. Generate a token with `api` scope from the GitLab user settings' Access Tokens page.

`JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` authenticate the Jira REST API calls in Steps 2 and 7, and `JIRA_URL` also builds the Jira ticket link in the success message (Step 8).

`JIRA_IN_REVIEW_STATUS` is optional but recommended — see Step 7.

If `.env` is missing these values, tell the user to add them — `cp ${CLAUDE_PLUGIN_ROOT}/.env.example .env` gives them a starting template — and stop.

The ADO/GitLab and Jira calls run through the shared `lib/` Python package at `${CLAUDE_PLUGIN_ROOT}/lib/`. It needs `requests` installed — `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt` if it isn't already available.

## Workflow

### Step 0: Pre-flight verification

Before anything is created, run the `dev-pr-preflight` workflow (`${CLAUDE_PLUGIN_ROOT}/skills/dev-pr-preflight/SKILL.md`). It reproduces the project's CI pipeline locally in check-only mode and changes nothing in the repo.

- **Pipeline would pass:** continue, and keep the report for the Testing section in Step 5.
- **A job failed or couldn't be verified:** show the report and stop. Offer three choices:
  - fix first (the default; stop here)
  - open the PR anyway
  - re-run pre-flight
  
  If the developer chooses to open anyway, continue, and state in the Testing section which jobs failed or weren't verified. A reviewer should never assume a green pre-flight that didn't happen.
- The developer can skip pre-flight by saying so explicitly ("open the PR, skip checks"). In that case, write "Pre-flight: skipped" in the Testing section.

### Step 1: Detect the host and read configuration

```bash
git remote get-url origin
```

If the URL's host is `dev.azure.com` or `*.visualstudio.com`, this is an **ADO** repo. Otherwise it's a **GitLab** repo (self-hosted instances are common — match on "not ADO", don't hardcode a GitLab hostname).

Read `.env` from the repository root and extract `GIT_USERNAME` plus, depending on the host:
- ADO: `ADO_ORG`, `ADO_PROJECT`, `ADO_REPO`, `ADO_PAT`
- GitLab: `GITLAB_URL`, `GITLAB_TOKEN` (and `GITLAB_PROJECT` if set)

If any required var for the detected host is missing, tell the user which ones and stop.

### Step 2: Identify the Jira ticket

Get the current branch:
```bash
git branch --show-current
```

Parse it against `user/{username}/{ticket-number}-{desc}`. If `JIRA_PROJECT` is set in `.env`, combine it with the numeric ticket number (e.g. `JIRA_PROJECT=EPMPMVISTC` + branch `user/mykhailo/42-foo` → `EPMPMVISTC-42`). If the branch doesn't match this pattern, ask the user for the Jira ticket key directly.

Fetch the ticket:
```bash
export JIRA_URL JIRA_USERNAME JIRA_API_TOKEN
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py get --key <TICKET-KEY>
```
Extract `summary` for the PR title.

### Step 3: Check for an existing PR/MR

ADO:
```bash
export ADO_ORG ADO_PROJECT ADO_REPO ADO_PAT
CURRENT_BRANCH=$(git branch --show-current)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_pr.py check --source "$CURRENT_BRANCH"
```

GitLab:
```bash
export GITLAB_URL GITLAB_TOKEN GITLAB_PROJECT
CURRENT_BRANCH=$(git branch --show-current)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_gitlab.py check --source "$CURRENT_BRANCH"
```

If it exits 0, it printed `PR_ID=`/`PR_URL=` (ADO) or `MR_IID=`/`MR_URL=` (GitLab). Report the existing PR/MR URL to the user and stop — do not create a duplicate.

If it exits 1, none exists yet — continue. Exit 2 means an API error occurred — show the stderr message and stop.

### Step 4: Determine the target branch

ADO: default to `master`. GitLab: default to `develop` (the convention on GitLab repos in this org — check the repo's `.gitlab-ci.yml` workflow rules if present, since it usually names the accepted target branches explicitly). Either way, if the repository's actual default branch differs, use that instead (check with `git remote show origin | grep 'HEAD branch'`).

### Step 5: Build the PR description

Gather change context:
```bash
git log <target>..HEAD --oneline
git diff --stat <target>...HEAD
```

Write the description to a temp file following this format:

```markdown
# [Action] [Component/Feature]

## Summary
[One paragraph describing the change]
**[X files changed, Y insertions(+), Z deletions(-)]**

## What's Changed
### 1. [Major Change Category]
[Brief description with key points]

### 2. [Another Category]
[Brief description]

## Testing
- Pre-flight vs <pipeline file>: <N passed / N failed / N not run> — from Step 0, never invented
- [Any manual testing the developer describes]

## Migration Notes
[Compatibility and usage guidance, or "None" if not applicable]
```

Keep it under ~50 lines total. Save it to a temp file, e.g. `/tmp/pr-description-<ticket>.md`.

### Step 6: Create the PR/MR

For a GitLab repo, first push the branch if it isn't on the remote yet (`git push -u origin "$CURRENT_BRANCH"`) — GitLab needs the branch to exist server-side before an MR can point at it; ADO's `cli_pr.py create` doesn't need this.

ADO:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_pr.py create \
  --source "$CURRENT_BRANCH" \
  --target "<target-branch>" \
  --title "<TICKET-KEY>: <ticket summary>" \
  --description-file /tmp/pr-description-<ticket>.md
```

GitLab:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_gitlab.py create \
  --source "$CURRENT_BRANCH" \
  --target "<target-branch>" \
  --title "<TICKET-KEY>: <ticket summary>" \
  --description-file /tmp/pr-description-<ticket>.md
```

On success it prints `PR_ID=`/`PR_URL=` (ADO) or `MR_IID=`/`MR_URL=` (GitLab). On failure, report the stderr message to the user and stop (do not proceed to the Jira update).

### Step 7: Update the Jira ticket

The board column labeled "In Review" does not always correspond to a status literally named "In Review" — it's a workflow-specific mapping (e.g. on the EPMPMVISTC project's workflow, the "In Review" column is backed by the status named `Resolved`, not `In Review`; `Verified` is the "Ready for Testing" column). Do not assume `"In Review"` is a valid status name.

To find the right value:
1. If `.env` has `JIRA_IN_REVIEW_STATUS` set, use that status name directly.
2. Otherwise, ask the user once: "What's the exact Jira status name behind the 'In Review' board column for this project?" — do not guess further after one failed attempt. Suggest they add `JIRA_IN_REVIEW_STATUS=<answer>` to `.env` so future runs skip this question.

If ticket status is not already that status, transition it:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py transition --key <TICKET-KEY> --status "<resolved status name>"
```
This matches against the transition's target status name directly, so you don't need to know the exact transition name — only the status name.

Add a comment with the PR/MR link:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py comment --key <TICKET-KEY> --content-file /tmp/pr-comment-<ticket>.txt
```
where the content file holds: `Pull request opened: <PR/MR title> — <PR_URL or MR_URL>`

If either Jira call fails, report the PR/MR was created successfully but the Jira update failed, and show the stderr message — do not attempt to roll back the PR/MR.

### Step 8: Report success

Build the Jira ticket URL as `<JIRA_URL>/browse/<TICKET-KEY>`.

Report success in exactly this format — the Jira ticket key in brackets, a dash, a markdown link to the PR/MR with the link text `Azure DevOps Opened PR` (ADO) or `GitLab Opened MR` (GitLab), another dash, then a markdown link to the Jira ticket with the link text `Jira Ticket`:

```
[<TICKET-KEY>] - [Azure DevOps Opened PR](<PR_URL>) - [Jira Ticket](<JIRA_TICKET_URL>)
[<TICKET-KEY>] - [GitLab Opened MR](<MR_URL>) - [Jira Ticket](<JIRA_TICKET_URL>)
```

Examples:
```
[EPMPMVISTC-132] - [Azure DevOps Opened PR](https://dev.azure.com/EPMP-MVIS/migVisor%20SmartBuilder/_git/migvisor_smartbuilder_spec/pullrequest/927) - [Jira Ticket](https://jiraeu.epam.com/browse/EPMPMVISTC-132)
[EPMPMVISDA-139] - [GitLab Opened MR](https://git.epam.com/epma-dpaf/document-activation/document-activation-ingestion/-/merge_requests/54) - [Jira Ticket](https://jiraeu.epam.com/browse/EPMPMVISDA-139)
```

## Error Handling

| Situation | Action |
|---|---|
| Pre-flight reports a failing or unverified job | Show the report, stop, offer fix first / open anyway / re-run (Step 0) |
| `.env` missing required ADO_* vars (ADO repo) | List which are missing, point to where to generate a PAT, stop |
| `.env` missing `GITLAB_URL`/`GITLAB_TOKEN` (GitLab repo) | List which are missing, point to the GitLab user settings' Access Tokens page, stop |
| `GITLAB_URL` looks like it's a project URL, not an instance root | `cli_gitlab.py` normalizes this automatically (strips to scheme+host); no action needed, but worth mentioning to the user so they can fix `.env` for clarity |
| `.env` missing `JIRA_URL`/`JIRA_USERNAME`/`JIRA_API_TOKEN` | List which are missing, stop before touching Jira |
| Branch doesn't match naming convention | Ask the user for the Jira ticket key directly |
| Existing active PR/MR found for this branch | Report its URL, stop — do not create a duplicate |
| `cli_pr.py create` / `cli_gitlab.py create` fails | Show the stderr message, stop before touching Jira |
| `cli_jira.py transition` reports "No transition found to status: X" | The guessed status name is wrong for this project's workflow — ask the user for the exact status name instead of guessing further |
| Jira transition or comment fails after PR/MR succeeds | Report PR/MR success + Jira failure separately, do not roll back the PR/MR |
| `requests` not installed | Tell the user to run `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt`, stop |

## Why This Workflow

Eliminates the copy-paste round trip between the terminal, the ADO/GitLab web UI, and Jira. The branch naming convention already used by `dev-task-start` and `dev-pr-review` is reused here so the ticket key never needs to be typed twice. Detecting the host from the origin remote (rather than assuming ADO) means the same skill works across this org's mixed hosting — some repos on Azure DevOps, others on a self-hosted GitLab instance.
