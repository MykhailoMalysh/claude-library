---
name: dev-bug-fix
description: Structured bug fix workflow with two modes — Manual (confirm each implementation step) and Auto (front-load all clarification, then implement and commit autonomously). Use this skill whenever the user invokes /dev-bug-fix, mentions fixing a bug or ticket, or starts a bug fix session. Works for any type of bug in any project. Integrates with Jira via dev-task-start.
---

# dev-bug-fix

Structured bug fix workflow. Two modes, same commit discipline, same phase structure.

---

## Invocation

```
/dev-bug-fix [--auto | --manual] [TICKET-ID ...]
```

- `--auto` — front-load all clarification, then implement and commit without pausing
- `--manual` — confirm each implementation step before executing
- No mode flag — ask the user to pick before starting
- Ticket IDs optional — if omitted, invoke `dev-task-start` to pick from the sprint board

---

## Mode Difference

| | Manual | Auto |
|---|---|---|
| Clarification | Asked before implementation starts | Asked all upfront before implementation starts |
| Each fix unit | Wait for user confirmation before executing | Execute automatically |
| Commits | Automatic after each fix unit (no confirmation) | Automatic after each fix unit |
| Blockers | Surface and stop | Attempt self-fix; if unresolvable, flag and pause for manual review |

Commits are **always automatic** in both modes — no confirmation needed for the commit itself.

---

## Phases

Run all phases in order. In Auto mode, phases 1–4 complete before any code changes.

### Phase 1 — Ticket Intake

If ticket IDs were passed as arguments, fetch each ticket's Jira details directly.  
If no ticket IDs were passed, invoke the `dev-task-start` skill to let the user pick from the sprint board.

After fetching:
- Summarize each ticket: title, description, acceptance criteria (if any)
- If more than one ticket: warn the user

> **Multi-ticket reminder:** Implementing multiple tickets in one branch is recommended only for small, closely related bugs. Confirm the user wants to proceed before continuing.

### Phase 2 — Requirements Breakdown

Analyze the ticket(s) and the codebase to identify:
- Root cause (read the relevant files — don't guess)
- Logical fix units: the smallest independently committable changes that together resolve the ticket
- Files and lines involved in each fix unit
- Expected outcome of each fix unit

A logical fix unit is one coherent change — e.g., "fix three `_build` paths in SKILL.md" is one unit even if it touches three lines. "Fix agent count" is a separate unit. Use judgment.

### Phase 3 — Clarification

Collect all questions before implementation. Ask them in a single message, numbered.

Good questions to ask:
- Ambiguities in the ticket description
- Behavior choices where the fix could go multiple ways
- Scope decisions (e.g., should tests be updated?)
- Anything that would block or significantly alter the plan

Do not ask about things you can determine by reading the code. Do not ask unnecessary questions.

Wait for answers before proceeding.

### Phase 4 — Plan

Present the full implementation plan for user approval:

```
Fix Plan — [TICKET-ID(s)]

Fix units:
  1. [Short description] — [file(s)] — commit: "[inferred message]"
  2. [Short description] — [file(s)] — commit: "[inferred message]"
  ...

Mode: [Auto | Manual]
Proceed?
```

Wait for approval before starting implementation.

### Phase 5 — Implementation

Execute fix units one by one.

**Manual mode:** Before each fix unit, state what you are about to do and wait for the user to confirm (e.g., "Ready to implement fix unit 1: [description]. Proceed?").

**Auto mode:** Execute each fix unit immediately. No confirmation needed.

**CRITICAL — Read Specifications First:**

Before implementing ANY fix unit, check if it involves a format, protocol, standard, or system with formal specifications:

- **File formats** (TOML, JSON, YAML, XML, etc.) — read the format specification
- **Protocols** (HTTP, WebSocket, MCP, etc.) — read the protocol documentation
- **APIs** (REST, GraphQL, etc.) — read the API specification
- **Standards** (semantic versioning, RFC documents, etc.) — read the standard
- **Platform requirements** (Claude Code, Codex, Devin, etc.) — read the platform documentation

**How to handle specifications:**

1. **Identify the spec:** Determine what formal documentation governs the fix (e.g., "TOML v1.0.0", "Codex agent configuration docs")
2. **Locate it:** Check if you have a reference URL in the codebase or ask the user directly: "What specification should I reference for [system/format]?"
3. **Read it BEFORE coding:** Fetch and read the relevant sections of the specification before writing any code
4. **Base the fix on the spec:** Implement exactly what the specification requires, not what seems intuitive or what worked in similar contexts

**Never:**
- Fix based on assumptions about how a format/protocol "should" work
- Rely on memory of specifications (they evolve and have nuances)
- Implement "good enough" solutions without verifying against the authoritative source
- Skip this step even for "simple" fixes — simple formats often have subtle requirements (e.g., TOML key escaping rules)

**If no specification exists or you can't find it:** Ask the user for the reference documentation before proceeding. Do not guess.

**For each fix unit:**
1. Read relevant specifications (if applicable — see above)
2. Make the change based on the specification
3. Verify it is correct (read the file back, check adjacent logic, verify against spec)
4. Commit with a message that matches the project's git log style (read recent commits to infer)
5. Report: "✓ Fix unit N committed: [commit message]"

**Blocker handling (Auto mode):**
- If a blocker appears (unexpected state, conflicting logic, missing context), attempt to resolve it using available information
- If unresolvable: stop, report the blocker clearly, and ask for manual input before continuing
- Resume auto execution after the blocker is resolved

### Phase 6 — Summary

After all fix units are done:

```
Summary — [TICKET-ID(s)]

Completed:
  ✓ Fix unit 1: [description] — [commit SHA short]
  ✓ Fix unit 2: [description] — [commit SHA short]

Open items:
  ⚠ [anything that needs follow-up, e.g., 98-1 pending discussion]

Next steps:
  - [e.g., create PR, update Jira status, run tests]
```

If there were any blockers that required manual intervention, note them explicitly in Open items.

---

## Commit Style

Before committing, read the last 5–10 commits in the project:

```bash
git log --oneline -10
```

Match the format exactly — prefix style, tense, casing, ticket reference placement. Do not invent a format.

---

## Notes for Future Plugin Migration

This skill is authored as a global skill (`~/.claude/skills/dev-bug-fix/`). When a plugin system is available, copy this file into the plugin's skills directory. The `dev-task-start` dependency should also be included in the plugin.
