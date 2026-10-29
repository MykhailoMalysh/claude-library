---
name: dev-task-start
description: Start work on a Jira ticket by selecting from your assigned sprint tasks, creating a feature branch, and moving the ticket to In Progress. Use this whenever a developer mentions "starting work", "pick up a ticket", "what should I work on", "create a branch for my task", "board a ticket", or any similar task-boarding workflow. Also trigger when the user wants to see their assigned tickets or sprint backlog.
compatibility:
  required_tools:
    - Bash
    - Read
    - AskUserQuestion
---

# dev-task-start

This skill helps developers start work on Jira tickets without opening Jira. It shows assigned tickets from the active sprint, lets the developer pick one, creates a feature branch following team conventions, and automatically moves the ticket to "In Progress".

## When to Use

Invoke this skill when the developer:
- Wants to start working on a new task
- Says "what's my next ticket" or "what should I work on"
- Mentions "picking up a ticket" or "boarding a ticket"
- Wants to see their assigned sprint tasks
- Needs to create a branch for a Jira ticket

## Prerequisites

The skill requires:
1. **Jira REST API access** — `.env` must have `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` (a Jira Personal Access Token, not your account password).
2. **`.env` file** in repository root — see `${CLAUDE_PLUGIN_ROOT}/references/conventions.md` for the full schema and branch naming convention. This skill reads `JIRA_PROJECT`, `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, `GIT_USERNAME`.

If `.env` is missing or `JIRA_PROJECT` is not set, guide the user to add it:
```bash
cp ${CLAUDE_PLUGIN_ROOT}/.env.example .env
# Edit .env with your personal values including JIRA_PROJECT
```
The `.env` file is gitignored and will not be committed.

The Jira calls run through the shared `lib/` Python package at `${CLAUDE_PLUGIN_ROOT}/lib/`. It needs `requests` installed — `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt` if it isn't already available.

## Workflow

### Step 1: Read Configuration

Read `.env` from repository root to get:
- `JIRA_PROJECT` — the Jira project key for this repository (e.g., `EPMPMVISTC`)
- `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — for authenticating to the Jira REST API
- `GIT_USERNAME` — for branch naming (e.g., "mykhailo")

If the file doesn't exist or `JIRA_PROJECT` is missing, inform the user to set it in `.env`.

### Step 2: Query Assigned Tickets

Search for tickets assigned to the user in the active sprint via the Jira REST API:

**JQL Query** (substitute `{JIRA_PROJECT}` with the value from `.env`):
```
project = {JIRA_PROJECT} AND assignee = currentUser() AND sprint in openSprints() AND status IN ("To Do", "In Progress")
```

```bash
export JIRA_URL JIRA_USERNAME JIRA_API_TOKEN
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py search --jql '<the JQL above>'
```

This prints a JSON array of `{"key", "summary", "description", "status"}` objects.

### Step 3: Display Tickets

Show all found tickets in this format:

```
Your assigned tickets in the active sprint:

[1] EPMPMVISTC-42: Optimize database query caching
    Status: To Do
    Description: We need to add a caching layer for read-heavy queries...

[2] EPMPMVISTC-45: Fix auth middleware session handling
    Status: In Progress
    Description: The session token storage doesn't meet compliance...
```

**Edge cases:**
- **No tickets found**: Tell the user "You have no tickets assigned in the active sprint. Check the Jira backlog to assign yourself a task."
- **One ticket**: Confirm with the user: "You have one active ticket. Shall I create a branch for it?"
- **Multiple tickets**: Ask the user to choose by number

### Step 4: Get Ticket Details

Once a ticket is selected, fetch full details:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py get --key <TICKET-KEY>
```

Display:
- Ticket number
- Title
- Description (full text)

This gives the developer complete context without opening Jira.

### Step 5: Quick context investigation

Before creating the branch, do a **light** pass over the codebase to ground the ticket in reality —
this is about understanding what's actually being asked, not designing the solution (that's
`dev-impl-plan`'s job). Grep for the entities/endpoints/terms the ticket description or comments
name, skim the directly relevant files, and note anything the ticket says that doesn't match what
the code actually does (tickets and comments can be stale or wrong — e.g. a linked branch described
as an "early step" toward something when it's actually a near-complete unrelated feature).

Keep this quick — a few targeted greps and reads, not a full exploration. Anything that would take
real design work to resolve belongs in `dev-impl-plan`, not here.

### Step 6: Create/seed the task file

Write (or update, if it already exists) `tasks/{ticket-number}.md` following the shared template in
`${CLAUDE_PLUGIN_ROOT}/references/conventions.md` ("Task file convention"). At this stage fill in:

- **Context** — from the ticket description and comments
- **Decisions already made** — only what's genuinely settled (confirmed by a person, or verified
  directly in code per the "Verify in code" rule) — leave empty if the quick pass didn't settle
  anything
- **Questions for the team** — anything ambiguous or contradictory the quick pass surfaced
- **Findings** — what the investigation turned up: relevant files/endpoints/functions, and any
  correction to what the ticket claims

Do not fill in Approach or Verification — those are `dev-impl-plan`'s sections.

### Step 7: Create Feature Branch

Generate the branch name following this template:
```
user/{git_username}/{ticket_number}-{short-description}
```

**Short description generation:**
1. Take the ticket title (everything after the colon in "EPMPMVISTC-42: Title here")
2. Convert to lowercase
3. Replace spaces and special characters with hyphens
4. Truncate to 30 characters
5. Remove trailing hyphens

**Example:**
- Ticket: "EPMPMVISTC-42: Optimize database query caching for read operations"
- GIT_USERNAME: "mykhailo"
- Branch: `user/mykhailo/42-optimize-database-query-cach`

**Git commands:**
```bash
git checkout master
git pull origin master
git checkout -b "user/{GIT_USERNAME}/{ticket_number}-{short-description}"
```

### Step 8: Transition Ticket to In Progress

If the ticket status is "To Do", transition it to "In Progress":

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py transition --key <TICKET-KEY> --status "In Progress"
```

**Important:** Skip this step if the ticket is already "In Progress".

### Step 9: Confirm Success

Report to the user:
```
✓ Branch created: user/mykhailo/42-optimize-database-query-cach
✓ Ticket EPMPMVISTC-42 moved to In Progress
✓ Task file seeded: tasks/42.md

You're all set! Here's your ticket context:

Title: Optimize database query caching for read operations
Description: We need to add a caching layer for read-heavy queries...

Open questions from the initial pass (see tasks/42.md for detail):
- [any Questions for the team the investigation surfaced]

Next: run /dev-impl-plan to turn this into an implementation plan.
```

## Error Handling

- **`.env` missing `JIRA_URL`/`JIRA_USERNAME`/`JIRA_API_TOKEN`**: List which are missing and point to where to generate a Jira API token
- **`.env` missing or `JIRA_PROJECT` not set**: Instruct the user to add `JIRA_PROJECT=<key>` to their `.env` file
- **`requests` not installed**: Tell the user to run `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt`
- **Git errors** (branch exists, dirty working tree): Report clearly and suggest fixes
- **Jira API errors** (`cli_jira.py` exits non-zero): Show the stderr message and suggest checking credentials/permissions

## Why This Workflow

This skill eliminates context-switching. Developers stay in their IDE/terminal and get:
- A clear view of what they should work on
- Ticket context loaded into the conversation
- Proper branch naming enforced automatically
- Jira status updated without manual clicking

The branch naming convention (`user/{username}/{ticket}-{description}`) makes it easy to identify who's working on what and connects branches to tickets at a glance.
