---
name: dev-pr-open
description: Create a pull/merge request from the current branch (Azure DevOps or GitLab, detected from the origin remote) and update the linked Jira ticket (transition to the "In Review" board column, add a comment with the PR/MR link). Use when the developer says "open a PR", "create the PR/MR", "open a pull request for this branch", or invokes /dev-pr-open.
role: implementation
compatibility:
  required_tools:
    - Bash
    - Read
---

# dev-pr-open

Create a pull request (Azure DevOps) or merge request (GitLab) for the current branch with a generated description, then update the linked Jira ticket. The host is detected from `git remote get-url origin`.

## Configuration

Credentials come from the process environment (`env` block of `.claude/settings.local.json`); if one is missing, name it, show the line to add (e.g. `"GITLAB_TOKEN": "<your token>"`), and stop. See `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` (Configuration) and `${CLAUDE_PLUGIN_ROOT}/references/settings-local.example.json`.

- Always: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` (Jira calls and the ticket link in the final message).
- Azure DevOps (origin host `dev.azure.com` or `*.visualstudio.com`): `ADO_ORG`, `ADO_PROJECT`, `ADO_REPO`, `ADO_PAT` (Code Read & Write).
- GitLab (any other host): `GITLAB_URL` (instance root, not a project URL), `GITLAB_TOKEN` (`api` scope), optionally `GITLAB_PROJECT`.

Load the profile and treat the output as `<profile>`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show
```

| Setting | Fallback |
|---|---|
| `base_branch` | the branch `origin/HEAD` points to, never a hard-coded name |
| `jira_project` | `JIRA_PROJECT` |
| `jira_statuses.in_review` | `JIRA_IN_REVIEW_STATUS`, else ask once |

With no profile, use the fallbacks and suggest `/dev-profile-init` in the final message. Never fail on a missing profile. The API calls need `requests` (`pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt`).

## Workflow

### Step 0: Pre-flight verification

Before anything is created, run the `dev-pr-preflight` workflow (`${CLAUDE_PLUGIN_ROOT}/skills/dev-pr-preflight/SKILL.md`). It reproduces the project's CI pipeline locally in check-only mode and changes nothing in the repo.

- **Pipeline would pass:** continue, and keep the report for the Testing section in Step 5.
- **A job failed or couldn't be verified:** show the report and stop. Offer three choices:
  - fix first (the default; stop here)
  - open the PR anyway
  - re-run pre-flight
  
  If the developer chooses to open anyway, continue, and state in the Testing section which jobs failed or weren't verified. A reviewer should not assume a green pre-flight that didn't happen.
- The developer can skip pre-flight by saying so explicitly ("open the PR, skip checks"). In that case, write "Pre-flight: skipped" in the Testing section.

### Step 1: Detect the host

```bash
git remote get-url origin
```

If the URL's host is `dev.azure.com` or `*.visualstudio.com`, this is an ADO repo; otherwise it is a GitLab repo (self-hosted instances are common, so match on "not ADO" rather than a hostname).

If any variable required for the detected host is missing, report it as described in Configuration and stop.

### Step 2: Identify the Jira ticket

Get the current branch:
```bash
git branch --show-current
```

Parse it against the profile `branch_pattern` (fallback `user/{username}/{ticket}-{description}`). Combine `jira_project` (profile, else `JIRA_PROJECT`) with the numeric ticket number (e.g. `JIRA_PROJECT=EPMPMVISTC` + branch `user/mykhailo/42-foo` → `EPMPMVISTC-42`). If the branch doesn't match the pattern, ask the user for the Jira ticket key directly.

Fetch the ticket:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py get --key <TICKET-KEY>
```
Extract `summary` for the PR title.

### Step 3: Check for an existing PR/MR

ADO:
```bash
CURRENT_BRANCH=$(git branch --show-current)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_pr.py check --source "$CURRENT_BRANCH"
```

GitLab:
```bash
CURRENT_BRANCH=$(git branch --show-current)
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_gitlab.py check --source "$CURRENT_BRANCH"
```

If it exits 0, it printed `PR_ID=`/`PR_URL=` (ADO) or `MR_IID=`/`MR_URL=` (GitLab). Report the existing PR/MR URL to the user and stop — do not create a duplicate.

If it exits 1, none exists yet — continue. Exit 2 means an API error occurred — show the stderr message and stop.

### Step 4: Determine the target branch

Use `base_branch` from the profile. Without a profile, use the repository's default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`); on GitLab also check `.gitlab-ci.yml` workflow rules, which usually name the accepted target branches.

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
- Pre-flight vs <pipeline file>: <N passed / N failed / N not run> — from Step 0, not invented
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

The board column labeled "In Review" does not always correspond to a status literally named "In Review" — it's a workflow-specific mapping (e.g. on the EPMPMVISTC project's workflow, the "In Review" column is backed by the status named `Resolved`, not `In Review`; `Verified` is the "Ready for Testing" column). Don't assume `"In Review"` is a valid status name.

To find the right value:
1. Use `jira_statuses.in_review` from the profile, else `JIRA_IN_REVIEW_STATUS`.
2. Otherwise ask once: "What's the exact Jira status name behind the 'In Review' board column for this project?" Do not guess after a failed attempt. Suggest storing it in the profile (`/dev-profile-init`) or as `"JIRA_IN_REVIEW_STATUS": "<answer>"` in `settings.local.json`.

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
| Missing `ADO_*`, `GITLAB_*`, or `JIRA_*` variable | Name it, show the `settings.local.json` line, stop before touching that service |
| `GITLAB_URL` is a project URL | `cli_gitlab.py` strips it to scheme and host; mention it so the developer can fix the value |
| Branch doesn't match the naming convention | Ask the user for the Jira ticket key |
| Existing active PR/MR for this branch | Report its URL, stop |
| `create` fails | Show stderr, stop before touching Jira |
| `transition` reports "No transition found to status: X" | The status name is wrong for this workflow; ask for the exact name |
| Jira transition or comment fails after PR/MR succeeds | Report PR/MR success and Jira failure separately; do not roll back |
| `requests` not installed | Give the pip command, stop |
