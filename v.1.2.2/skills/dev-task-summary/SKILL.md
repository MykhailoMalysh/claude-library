---
name: dev-task-summary
description: Save a short note of the important nuances of how an agent-driven ticket was solved to the Obsidian vault once the task is done or its MR is open. Use when the developer says "save a summary", "write the task summary", "document how we solved this", or invokes /dev-task-summary.
role: implementation
---

# dev-task-summary

Write one short markdown note about how this ticket was solved with the agent. It covers the process, not the ticket.

## Where

Load the profile with `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show` and treat the output as `<profile>`. Save to `{summaries_dir}/{ticket-number}-{short-slug}.md`. If `summaries_dir` is unset or there is no profile, ask the developer for the directory once and suggest `/dev-profile-init` to store it.

Keep the note outside the repo, and update the existing note for the same ticket instead of creating a second one.

## What to record

Only the important nuances, drawn from the whole session:

- steps that led to the solution and why they were chosen
- premises that turned out wrong or stale, and how they were checked
- non-obvious findings, decisions, and dead ends
- environment and tooling gotchas, with the fix
- what is left open

End with a **Not verified** section: what could not be verified or run, and why (no environment, no access, tests skipped). Write "Nothing" when everything was verified.

## What stays out

The ticket's business logic, description, or acceptance criteria; the MR description or diff contents (the repo records those); and secrets, tokens, credentials, or env values, including any that appeared in the session.

Keep it short: headed bullets, no long prose. Tell the developer the path of the saved note.
