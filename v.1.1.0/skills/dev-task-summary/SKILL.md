---
name: dev-task-summary
description: Save a short note of the important nuances of how an agent-driven ticket was solved to the Obsidian vault once the task is done or its MR is open. Use when the developer says "save a summary", "write the task summary", "document how we solved this", or invokes /dev-task-summary.
---

# dev-task-summary

Write one short markdown note about the nuances of solving this ticket with the agent. It is about the **process**, not the ticket.

## Where

`/Users/Mykhailo_Malysh/Library/Mobile Documents/iCloud~md~obsidian/Documents/work_vault/work/activities/contribution/EPM-MVIS_Document-Activation-Accelerator/tasks/summaries/{ticket-number}-{short-slug}.md`

Never in the repo. Update the existing note for the same ticket instead of creating a second one.

## What to record

Only the important nuances of the agentic solution, drawn from the whole session:

- steps that led to the solution and why they were chosen
- premises that turned out wrong or stale, and how they were checked
- non-obvious findings, decisions, and dead ends
- what could not be verified or run, and why
- environment and tooling gotchas, with the fix
- what is left open

## What never goes in

- the ticket's business logic, description, or acceptance criteria
- the MR description or what the diff contains (the repo records that)
- secrets, tokens, credentials, or env values, including ones that appeared in the session

Keep it short: headed bullets, no long prose.

## After

Tell the developer the path of the saved note.
