---
name: pm-create-ticket
description: Create a Jira bug, task, story, or sub-task in the project configured via JIRA_PROJECT, grounded in the actual code of the right component repo (works from a workspace root or a single repo), with a short Jira wiki-markup description (separate Bug and Task templates) and an epic picked from the project's open epics. Shows the draft and creates only on approval. Use whenever the user wants to create a new task, sub-task, story, or bug in Jira — including when they say "create a ticket", "add a task", "log a bug", "log a Jira issue", "open a sub-task", "track this in Jira", or describes work that should be tracked. Always invoke this skill instead of calling the Jira REST API directly.
role: team
compatibility:
  required_tools:
    - Bash
    - Read
    - AskUserQuestion
---

# pm-create-ticket

Creates a Jira ticket that someone can pick up and act on. Good tickets here are short: the core problem in two or three sentences, a few checkable outcomes that name real components, nothing else. Details that don't change what gets built are left out, because they bury the problem. Claims are checked against the code first, since tickets written from memory go stale (wrong numbers, code that lives in another repo).

## 1. Load configuration

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show
```

Treat the output as `<profile>`. Use `mode`, `repos`, `settings.jira_project`, `settings.base_branch`, and the sections "How the application works" and "How we build things here". With no profile and `mode: workspace`, offer `/dev-profile-init` before drafting, since without `repos` the ticket can't be checked against code. If the developer declines, continue ungrounded. With no profile in repo mode, use `JIRA_PROJECT` from the env and suggest `/dev-profile-init` once at the end. If there is no profile and `JIRA_PROJECT` is unset, ask for the project key.

Credentials (`JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`) come from the process env (see `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`); never open `.env`. If one is missing, name it and show the line to add to the `env` block of `.claude/settings.local.json`, for example `"JIRA_API_TOKEN": "<your token>"`. Without `JIRA_USERNAME`, ask for the assignee.

## 2. Decide the issue type first

Bug (something that worked or should work is broken) or Task/Story (new or changed behaviour). Sub-task is a Task with a parent key. The type picks the template in step 5. If the conversation doesn't make it clear, ask, in the same message as anything else missing: summary, parent key for a Sub-task (required; it can't be created without one), priority (default Major).

## 3. Read the code

The goal is to name real modules and endpoints and to correct wrong numbers or names from the requester.

- Workspace mode (`mode: workspace`, typical when run from the team's workspace root): pick the component(s) from `<profile>` `repos` by their `name` and `owns` against the ask. Skip entries with `exists: false` and say so in one line ("skipped ingestion: folder missing"). For each picked repo, read `origin/<base_branch>`:
  ```bash
  git -C <abs_path> fetch -q origin
  git -C <abs_path> grep -n "<term>" origin/<base_branch>
  git -C <abs_path> show origin/<base_branch>:<path>
  ```
  If `fetch` fails for a repo, read the local `origin/<base_branch>` and add "may be stale" to that repo's line in "Checked in code", or skip the repo with a one-line note. A failed fetch never stops the draft.
- Repo mode: the same in the current repo (`git fetch origin`, `git grep`, `git show origin/<base_branch>:<path>`). If the code lives in another repo, say which and ask whether to continue.
- No repo reachable (no `repos`, all missing, or no local `origin/<base_branch>` to read): draft from the conversation only and say so in the draft summary ("Checked in code: nothing — drafted from conversation").

Use the profile's "How the application works" section as the map. Where a number or name the requester gave differs from the code, use the code and tell them. What can't be checked here (another team's system, infra state, a product choice) goes to Open questions, not into stated facts.

## 4. Pick an epic

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py epics --project "<jira_project>"
```

It prints a JSON list of `{"key", "summary", "status"}` (open epics only; add `--include-done` if the developer asks for closed ones). Propose the best match by summary and component, or "no epic" when nothing fits, and let the developer choose from the list. If stderr says `showing first N of M epics`, tell the developer the list is partial and offer to search by name. If the command fails or the list is empty, say "no epic support detected" (or "no open epics") and continue without one.

## 5. Draft in Jira wiki markup

The description goes to Jira Server/DC, which renders wiki markup, not Markdown. Use `h3.` headers, `*` bullets, `#` numbered lists. Put code, paths or names containing `*` or `{`, and JSON or logs in `{code}` or `{noformat}` blocks, so wiki markup doesn't turn them into bold text or macros. In prose, wrap identifiers and paths containing `_`, `+`, `-`, or `[` in `{{...}}` (for example `{{order_service}}`, `{{feature-flags}}`), since those characters also format text. Leave out sections with nothing to say, and leave out nuances that don't change what gets built. Never use Markdown bold or Markdown `#` headings.

Bug:

```
h3. Problem
{2-3 sentences: what breaks, for whom}

h3. Steps to reproduce
# {step}
# {step}

h3. Expected vs actual
Expected: {what should happen}
Actual: {what happens}

h3. Environment
{env, version, component}

h3. Impact
{who is affected and how badly}

h3. Notes
{optional: only what changes the fix}
```

Task / Story / Sub-task:

```
h3. Goal
{2-3 sentences: the core problem and the outcome}

h3. Why
{the reason it matters, one or two lines}

h3. Done when
* {checkable outcome naming a real component/module, e.g. "POST /api/orders/{id}/cancel returns 409 for shipped orders"}
* {2-4 items in total}

h3. Notes
{optional}

h3. Open questions
* {optional: each assumption the code couldn't confirm, with who can answer it}
```

A "Done when" item like "works correctly" can't be checked; rewrite it until a test or a request could verify it. If you can't write the Goal or Problem, ask.

## 6. Show the draft and wait

```
Summary:   {summary}
Type:      {issue type}
Parent:    {parent key or "none"}
Epic:      {EPIC-KEY — epic summary, or "none"}
Priority:  {priority}
Assignee:  {JIRA_USERNAME or the given assignee}
Checked in code: {repo: files/endpoints read, with base ref; or "nothing — drafted from conversation"}

--- Description ---
{draft, in full}
---
```

Ask "Create this ticket?" and create it only after the developer approves. Apply requested edits and show the full draft again.

## 7. Create

Write the description to a temp file, then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py create \
  --project "<jira_project>" \
  --summary "<summary>" \
  --type "<issue type>" \
  --priority "<priority>" \
  --assignee "<assignee>" \
  --description-file /tmp/ticket-description.txt \
  [--parent "<PARENT-KEY>"] \
  [--epic "<EPIC-KEY>"]
```

Pass `--parent` only for Sub-tasks and `--epic` only when an epic was chosen. On success it prints `ISSUE_KEY=<key>`; report:

```
Created: {KEY} — {summary}
Link:    {JIRA_URL}/browse/{KEY}
Epic:    {EPIC-KEY or "none"}
```

Then delete the temp file.

Epic failures:

- stderr starts with `Epic Link field not found`: the instance has no Epic Link field. Say "no epic support detected" and, with the developer's approval, retry once without `--epic`.
- stderr mentions the epic field or "not on the appropriate screen": the field exists but isn't on the create screen. Create without `--epic`, then set it:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py set-epic --key "<KEY>" --epic "<EPIC-KEY>"
  ```
  It prints `{"key", "epic"}` on success. If it fails, report the ticket as created and add `epic not set: <stderr>`.

On any other non-zero exit, show stderr and offer to adjust and retry. If `requests` is missing, point to `pip install -r ${CLAUDE_PLUGIN_ROOT}/lib/requirements.txt`.
