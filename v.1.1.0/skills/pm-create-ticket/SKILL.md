---
name: pm-create-ticket
description: Create a Jira ticket in the project configured via JIRA_PROJECT with a business-focused description format (Goal, Business Value, Approach, Success Criteria, Test With). Use whenever the user wants to create a new task, sub-task, story, or bug in Jira — including when they say "create a ticket", "add a task", "log a Jira issue", "open a sub-task", "track this in Jira", or describes work that should be tracked. Always invoke this skill instead of calling the Jira REST API directly.
compatibility:
  required_tools:
    - Bash
    - Read
    - AskUserQuestion
---

# pm-create-ticket

This skill creates a Jira ticket in the configured project using a business-focused description format. It gathers the required information conversationally (Goal, Business Value, Approach, Success Criteria, Test With), confirms the full ticket before creating it, and posts it as plain text with **bold** section headers.

## When to Use

Invoke this skill when the user:
- Says "create a ticket", "add a task", "log a ticket", "open a Jira issue"
- Wants to break down work into sub-tasks
- Describes a feature, bug, or refactoring that should be tracked in Jira

## Prerequisites

- `.env` file in the repository root — see `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` for the full schema. This skill reads `JIRA_PROJECT`, `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`.
  `JIRA_USERNAME` is also used as the default assignee — without it, ask the user for an assignee instead of auto-filling.
- The Jira calls run through the shared `lib/` Python package at `${CLAUDE_PLUGIN_ROOT}/lib/`. It needs `requests` installed — `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt` if it isn't already available.

If `.env` is missing or `JIRA_PROJECT` is not set, ask the user for the project key directly and suggest adding it to `.env` for future runs.

## Workflow

### Step 1: Read Configuration and Gather Information

Read `.env` from the repository root to get `JIRA_PROJECT`, `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`.

Ask the user for the following. Collect everything in one conversational exchange if possible:

1. **Summary** — one-line ticket title
2. **Issue type** — Task, Sub-task, Story, Bug (default: Task)
3. **Parent ticket** — required if issue type is Sub-task (e.g. `{JIRA_PROJECT}-54`)
4. **Priority** — Major, Minor, Critical (default: Major)
5. **Description content** — gather per section:
   - **Goal**: one-line or short paragraph describing what this ticket achieves
   - **Business Value**: bullet list of benefits this delivers (why it matters)
   - **Approach**: bullet list of how to implement it (high-level steps)
   - **Success Criteria**: bullet list of conditions that define done
   - **Test With**: bullet list of test scenarios or data sets
   - **Blocked by** *(optional)*: ticket keys or dependencies that block this work
   - **Additional Notes** *(optional)*: any extra context (e.g., "If successful: close TICKET-X")

### Step 2: Format the Description

Compose the description using this business-focused template. Use **bold** for section headers (confirmed to work in this Jira instance).

```
**Goal**: {one-line or short paragraph describing what this achieves}

**Business Value**: 
- {benefit 1}
- {benefit 2}
- {benefit 3}

**Approach**:
- {high-level step 1}
- {high-level step 2}
- {high-level step 3}

**Success Criteria**:
- {criterion 1}
- {criterion 2}
  - {sub-criterion if needed}

**Test With**: {test scenarios, data sets, or document types}

**Blocked by**: {TICKET-KEY} -- {reason}

**{Additional section if needed}**: {content}
```

Omit "Blocked by" if there are no blockers. Omit additional sections if not needed.

Use `->` instead of `→` (arrow character causes encoding issues in some Jira instances).

### Step 3: Confirm Before Creating

Show the user the full ticket as it will be created:

```
Summary:   {summary}
Type:      {issue type}
Parent:    {parent key or "none"}
Priority:  {priority}
Assignee:  {JIRA_USERNAME from .env, or "me"}

--- Description ---
{formatted description}
---
```

Ask: "Shall I create this ticket?"

Only proceed after confirmation.

### Step 4: Create the Ticket

Write the formatted description from Step 2 to a temp file, then:

```bash
export JIRA_URL JIRA_USERNAME JIRA_API_TOKEN
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py create \
  --project "<JIRA_PROJECT from .env>" \
  --summary "<confirmed summary>" \
  --type "<confirmed issue type>" \
  --priority "<confirmed priority>" \
  --assignee "<JIRA_USERNAME from .env, or the user-provided assignee>" \
  --description-file /tmp/ticket-description.txt \
  [--parent "<PARENT-KEY>"]
```

Pass `--parent` for Sub-tasks (this links the Sub-task to its parent directly via the Jira REST API's `parent` field — no description workaround needed). Omit it for any other issue type.

On success it prints `ISSUE_KEY=<key>`. On failure, show the stderr message and offer to retry or adjust the input.

### Step 5: Report Result

On success, report:

```
Created: {TICKET-KEY} — {summary}
```

If creation fails, show the error and offer to retry or adjust the description.

## Description Format Rules

These rules are confirmed to work in this Jira instance. The Jira REST API accepts plain text with markdown **bold** formatting.

- Section headers use `**Header**:` format (bold with colon)
- Bullets use `- ` (dash + space)
- Nested bullets use `  - ` (two spaces + dash + space)
- Use `->` instead of `→` (arrow character)
- Use `--` instead of `—` (em dash)
- **Bold** is allowed and renders correctly
- No other markdown (no italics, no code blocks, no headers with #)

## Error Handling

- **Missing Goal or Success Criteria**: these are required — ask the user before proceeding
- **Sub-task without parent**: ask for the parent ticket key
- **Jira API error on create** (`cli_jira.py` exits non-zero): show the raw stderr message and let the user correct the input
- **`.env` missing or `JIRA_PROJECT` not set**: ask the user for the project key directly, suggest adding `JIRA_PROJECT` to `.env`
- **`.env` missing `JIRA_URL`/`JIRA_API_TOKEN`**: tell the user which are missing and point to where to generate a Jira API token
- **`JIRA_USERNAME` not set**: skip assignee auto-fill and ask the user for their Jira username
- **`requests` not installed**: tell the user to run `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt`
