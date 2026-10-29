---
name: pm-create-ticket
description: Create a Jira ticket in the project configured via JIRA_PROJECT, grounded in the actual code and the project profile, with a business-focused description (Goal, Business Value, Approach, Success Criteria, Test With, Open questions). Reads the relevant code first so acceptance criteria name real modules and endpoints, shows the draft, and creates only on approval. Use whenever the user wants to create a new task, sub-task, story, or bug in Jira — including when they say "create a ticket", "add a task", "log a Jira issue", "open a sub-task", "track this in Jira", or describes work that should be tracked. Always invoke this skill instead of calling the Jira REST API directly.
role: team
compatibility:
  required_tools:
    - Bash
    - Read
    - AskUserQuestion
---

# pm-create-ticket

Creates a Jira ticket whose claims hold up when someone starts the work. Most stale tickets were written from memory: wrong migration numbers, old scan results, wrong totals, code that lives in another repo. This skill reads the code and the profile before drafting, writes criteria someone can verify, and records what it could not check as open questions.

## 1. Load configuration

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show
```

Treat the output as `<profile>`. Use `settings.jira_project`, `settings.base_branch`, and the sections "How the application works" and "How we build things here". With no profile, use `JIRA_PROJECT` from the env and suggest `/dev-profile-init` once at the end. If there is no profile and `JIRA_PROJECT` is unset, ask the requester for the project key.

Credentials (`JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`) come from the process env (see `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`); never open `.env`. If one is missing, name it and show the line to add to the `env` block of `.claude/settings.local.json`, for example `"JIRA_API_TOKEN": "<your token>"`. Without `JIRA_USERNAME`, ask for the assignee.

## 2. Gather the ask

From the conversation, collect the summary, issue type (Task, Sub-task, Story, Bug; default Task), parent key for a Sub-task, priority (default Major), and what the requester wants and why. Ask once, in one message, for anything missing. A Sub-task without a parent key can't be created; ask for the parent key.

## 3. Read the code before drafting

1. Find the affected area with the profile's domain flow ("How the application works") as the map: which modules, endpoints, models, jobs.
2. Read them on `origin/<base_branch>` (`git fetch origin`, then `git grep` and `git show origin/<base_branch>:<path>`). If the code is not in this repo, say which repo it lives in and ask whether to continue.
3. Check every concrete number or name the requester gave (migration numbers, counts, file names, scan results) against the code. Where it differs, use what the code shows and tell the requester.
4. Anything that can't be checked here (another team's system, infra state, a product choice) becomes an open question, not a stated fact.

## 4. Draft

Plain text with **bold** headers; `->` instead of arrows and `--` instead of em dashes, because those characters break in some Jira instances. No other markdown.

```
**Goal**: {what this achieves, one or two lines}

**Business Value**:
- {why it matters}

**Approach**:
- {high-level steps naming the real modules or endpoints, e.g. "extend OrderService.cancel in orders/services.py"}

**Success Criteria**:
- {verifiable: names the module/endpoint and the observable result, e.g. "POST /api/orders/{id}/cancel returns 409 for shipped orders"}

**Test With**: {scenarios or data sets}

**Open questions**:
- {each assumption the code could not confirm, as a question with who can answer it}

**Blocked by**: {TICKET-KEY} -- {reason}
```

Omit "Blocked by" and "Open questions" when empty. Goal and Success Criteria are required; ask if you can't write them. A criterion like "works correctly" is not verifiable; rewrite it until someone could check it with a test or a request.

## 5. Show the draft and wait

```
Summary:   {summary}
Type:      {issue type}
Parent:    {parent key or "none"}
Priority:  {priority}
Assignee:  {JIRA_USERNAME or the given assignee}
Checked in code: {files/endpoints read, with base ref}

--- Description ---
{draft}
---
```

Ask "Create this ticket?" and create it only after the requester approves. Apply requested edits and show the draft again.

## 6. Create

Write the description to a temp file, then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py create \
  --project "<jira_project>" \
  --summary "<summary>" \
  --type "<issue type>" \
  --priority "<priority>" \
  --assignee "<assignee>" \
  --description-file /tmp/ticket-description.txt \
  [--parent "<PARENT-KEY>"]
```

Pass `--parent` only for Sub-tasks. On success it prints `ISSUE_KEY=<key>`; report `Created: {KEY} — {summary}` and delete the temp file. On a non-zero exit, show stderr and offer to adjust and retry. If `requests` is missing, point to `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt`.
