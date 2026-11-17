---
name: dev-wayfinder
description: Plan a huge chunk of work (more than one agent session can hold) as a shared map document with decision points, and resolve them one at a time until the way to the destination is clear. Use when the developer faces a large, foggy effort that needs to be charted before it can be executed — multi-sprint initiatives, complex migrations, or architectural changes where the full path isn't visible yet. Also use when the developer says "this is too big to plan in one go", "let's map this out", "chart the way forward", or invokes /dev-wayfinder.
role: planning
compatibility:
  required_tools:
    - Bash
    - Read
    - Write
    - Agent
---

# dev-wayfinder

For an effort too big and too foggy for one session. The skill charts the way to a **destination** as a **map document**, then resolves its **decision points** one per session until nothing is left to decide. It plans; it doesn't build. When the pull to just do the work appears, the map has reached its edge and it's time to hand off to tickets and `/dev-impl-plan`. The map's Notes can opt an effort into execution; without that, produce decisions, not deliverables.

If one session could plan the whole thing, use `/dev-impl-plan` instead.

## Files

```
wayfinder/{initiative-slug}/
├── MAP.md                    # the index and resume point
├── decisions/NN-slug.md      # one file per decision; the only place its detail lives
├── prototypes/  research/    # assets linked from decisions
└── out-of-scope/             # decisions ruled beyond the destination
```

Load the profile with `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show` and treat it as `<profile>`; "How the application works" grounds the questions. Never put map files under a `forbidden.paths` entry. With no profile, continue and suggest `/dev-profile-init` once.

## The map

MAP.md is an index: it gists each decision in one line and links the file, never restating detail. It opens with a JSON status block that a fresh session reads first:

````markdown
# Wayfinder Map: {Initiative Name}

```json
{"destination": "Agreed GraphQL migration strategy and phased plan",
 "state": "charting | working | complete",
 "updated": "2026-10-29",
 "next": 4,
 "in_progress": [],
 "open": [3, 4], "blocked": {"5": [3, 4]}, "completed": [1, 2],
 "last_session": "Resolved 2: client keeps REST for uploads."}
```

## Destination
{one or two lines: the spec, decision, or change this effort is finding its way to}

## Notes
{domain, skills to consult, standing preferences, whether execution is allowed}

## Related tickets
{parent Epic, if any}

## Decisions so far
- [x] [1: {question}](decisions/01-slug.md): {one-line answer}

## Open decisions
- [ ] [4: {question}](decisions/04-slug.md) `grilling` <- next

## Blocked decisions
- [ ] [5: {question}](decisions/05-slug.md) `prototype`, blocked by 3, 4

## Not yet specified
- {fog: in-scope areas you can't phrase as a sharp question yet}

## Out of scope
- {work ruled out}: {why}
````

Keep the JSON block and the lists in sync; update both in the same edit.

A decision file:

```markdown
# Decision {N}: {Question}
**Type:** research | prototype | grilling | task
**Status:** open | in-progress | completed
**Blocked by:** {numbers or none}

## Question
## Context
## Resolution
## Assets
```

## Decision types

Each decision is either worked with the developer (HITL) or by the agent alone (AFK). The agent never answers the human's side of a HITL decision.

- **research** (AFK): surface a fact from docs, APIs, or the code. Dispatch a subagent; independent research decisions can run in parallel in one message. Findings go in Resolution with sources.
- **prototype** (HITL): build something to react to with `/dev-prototype`; link it in Assets.
- **grilling** (HITL, the default): work the question with the developer via `/dev-grill-me`.
- **task** (AFK or HITL): work that has to happen before a decision can be made (access, provisioning). Do it where you can; otherwise give the developer a checklist.

## Fog and scope

The map is deliberately incomplete. If you can state the question precisely now, even if it is blocked, make a decision file. If you can't phrase it sharply yet, leave it in "Not yet specified"; resolving decisions graduates fog into new files. Work beyond the destination goes to "Out of scope" with one line of why, and its file moves to `out-of-scope/`; it never appears in "Decisions so far", which records the route actually walked.

## Chart the map

1. **Name the destination** with `/dev-grill-me`. It fixes the scope, so settle it first.
2. **Map the frontier** breadth-first: grill across the whole space for open decisions and first steps. If no fog appears and the whole effort fits one session, stop and suggest `/dev-impl-plan`.
3. Create the directories, MAP.md (state `charting`), and numbered decision files. Set `next` to the first open, unblocked decision.
4. Dispatch subagents for research decisions, if any.
5. Set state to `working`, show the developer the map path and the frontier, and stop. Charting resolves nothing by hand.

## Work the map

One decision per session, except that independent research decisions can run together.

1. Load MAP.md (see the next section).
2. Pick the decision: the one the developer named, else `next`. If every open decision is in `in_progress`, ask which to take.
3. **Claim it** before any work: decision status `in-progress`, add its number to `in_progress`. This stops two sessions working the same decision.
4. Resolve it by type.
5. Record: fill Resolution and Assets, set status `completed`, move it to "Decisions so far" with a one-line gist, and update the JSON (`completed`, `in_progress`, `open`, `blocked`, `next`, `updated`, `last_session`).
6. Create files for anything the resolution made specifiable, graduate fog, and recompute what is unblocked.
7. If nothing is open, blocked, or foggy, set state `complete` and hand off (below). Otherwise stop and tell the developer the next decision.

## How a fresh session resumes

A new session has no memory of earlier ones; the map is the only shared state. On `/dev-wayfinder [path] [decision]`:

1. Find the map: the given path, else the only `wayfinder/*/MAP.md`; with several, list them and ask.
2. Read the JSON block first: `state`, `next`, `in_progress`, `last_session`. Then read only the decision files the chosen decision depends on, not the whole directory.
3. If `in_progress` is non-empty, open those files. A partly filled Resolution means an earlier session stopped mid-work: ask the developer whether to continue it or release the claim (back to `open`).
4. If the JSON and the lists disagree, trust the decision files' Status lines, fix the map, and say what you corrected.
5. Then continue at step 2 of "Work the map".

## Hand-off

When the map is complete:

- Turn the route into sprint-sized tickets with `/pm-create-ticket`; each references the map path and the decisions it relies on.
- Each ticket then goes through `/dev-task-start` -> `/dev-impl-plan` -> `/dev-implement`.
- Commit the map directory to a branch so the team can read it; keep or archive it as documentation.
