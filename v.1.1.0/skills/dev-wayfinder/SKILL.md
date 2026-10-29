---
name: dev-wayfinder
description: Plan a huge chunk of work (more than one agent session can hold) as a shared map document with decision points, and resolve them one at a time until the way to the destination is clear. Use when the developer faces a large, foggy effort that needs to be charted before it can be executed — multi-sprint initiatives, complex migrations, or architectural changes where the full path isn't visible yet. Also use when the developer says "this is too big to plan in one go", "let's map this out", "chart the way forward", or invokes /dev-wayfinder.
compatibility:
  required_tools:
    - Bash
    - Read
    - Write
---

# dev-wayfinder

A loose idea has arrived, too big for one agent session, and wrapped in fog: the way from here to the **destination** isn't visible yet. Wayfinding is about finding that way, not charging at the destination. This skill charts the way as a **shared map document** (markdown file), then works its **decision points** (questions whose resolution is a decision, not slices of a build to execute) one at a time until the route is clear.

## When to Use

- Multi-sprint initiatives where the full scope emerges over time
- Complex migrations or refactors where dependencies reveal themselves gradually
- Architectural changes that need exploration before commitment
- Developer says "this is too big to plan in one go", "let's break this down", "chart the way forward"
- Developer invokes `/dev-wayfinder`
- When `/dev-impl-plan` reveals the work is too large for a single plan

Do not use this for work that fits in a single sprint or can be planned in one session — that's `/dev-impl-plan`. Wayfinder is for efforts measured in weeks or months, not days.

## Prerequisites

None required. This skill works standalone using markdown files for the map and decision tracking. Optionally integrates with Jira when working within a ticket context (can reference a parent Epic or initiative ticket).

## Core Concepts

### The destination

The destination varies per effort, and naming it is the first act of charting: it shapes every ticket. It might be a spec to hand off and iterate on, a decision to lock before planning starts, or a change made in place like a data-structure migration. The map is domain-agnostic: engineering work, course content, whatever fits the shape.

### Plan, don't do

Wayfinder is **planning** by default: each ticket resolves a decision, and the map is done when the way is clear, with nothing left to decide before someone goes and does the thing. The pull to just do the work is usually the signal you've reached the edge of the map and it's time to hand off. An effort can override this in its **Notes**, carrying execution into the map itself, but absent that, produce decisions, not deliverables.

### The Map (Markdown Document)

The map is a **markdown file** at `wayfinder/{initiative-name}/MAP.md`, the canonical artifact. Decision points are tracked as items in this document and linked to separate decision files.

The map is an **index**, not a store. It lists the decisions made and points to the files that hold their detail; a decision lives in exactly one place, its file, so the map never restates it, only gists it and links.

#### Map structure

```markdown
# Wayfinder Map: {Initiative Name}

## Destination

<what reaching the end of this map looks like: the spec, decision, or change this effort is finding its way to. One or two lines; every session orients to it before choosing a decision.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Related Tickets

<!-- Optional: link to parent Jira Epic or initiative ticket if one exists -->
- Parent: [PROJ-123](link)

## Decisions so far

<!-- the index: one line per completed decision, enough to judge relevance, then zoom the link for the detail the file holds -->

- ✅ [Decision 1: {question}](decisions/01-question-slug.md): <one-line gist of the answer>
- ✅ [Decision 2: {question}](decisions/02-question-slug.md): <one-line gist of the answer>

## Open decisions

<!-- decisions ready to be worked, not blocked by anything -->

- 🔲 [Decision 3: {question}](decisions/03-question-slug.md) `[type: research]`
- 🔲 [Decision 4: {question}](decisions/04-question-slug.md) `[type: grilling]` **← Next**

## Blocked decisions

<!-- decisions that can't be worked yet because they depend on open decisions -->

- 🔲 [Decision 5: {question}](decisions/05-question-slug.md) `[type: prototype]` **Blocked by:** Decision 3, Decision 4

## Not yet specified

<!-- see "Fog of war": in-scope fog you can't document yet; graduates as the frontier advances -->

- Area to explore: {vague description}
- Possible decision about: {another vague area}

## Out of scope

<!-- see "Out of scope": work ruled beyond the destination; never graduates -->

- {work ruled out}: {why it's out of scope}
```

### Decision Files

Each decision is a **markdown file** in `wayfinder/{initiative-name}/decisions/`. Naming: `{number}-{slug}.md` (e.g., `01-api-schema-design.md`).

```markdown
# Decision {number}: {Question}

**Type:** `research` | `prototype` | `grilling` | `task`
**Status:** `open` | `in-progress` | `completed`
**Blocks:** {list of other decision numbers this blocks, if any}

## Question

<the decision or investigation this resolves>

## Context

<relevant background, constraints, what led to this question>

## Resolution

<!-- Filled in when completed -->

<the answer, findings, or outcome>

## Assets

<!-- Links to prototypes, research notes, code branches, etc. -->

- [Prototype](../prototypes/feature-xyz/)
- [Research notes](../research/api-comparison.md)
```

A decision is **claimed** by setting status to `in-progress` before any work. A decision is **unblocked** when every decision it's blocked by is completed. The **frontier** is the open, unblocked, unclaimed decisions.

## Decision Types

Every decision is either **HITL** (human in the loop, worked _with_ a human who speaks for themselves) or **AFK**, driven by the agent alone. A HITL decision only resolves through that live exchange; the agent never stands in for the human's side of it.

- **Research** (AFK): Reading documentation, third-party APIs, or local resources to surface a fact a decision waits on. Resolved by a subagent. Findings captured in the decision file's Resolution section.
  
- **Prototype** (HITL): Build a cheap, rough, concrete artifact to react to by calling `/dev-prototype`. Links the prototype in Assets. Use when "how should it look" or "how should it behave" is the key question.
  
- **Grilling** (HITL): Conversation. The default case. Call `/dev-grill-me` or similar to explore the question with the developer.
  
- **Task** (HITL or AFK): Manual work that must happen before a _decision_ can be made: signing up for a service, provisioning access, moving data. The agent drives it alone where it can (AFK); otherwise hands the human a checklist (HITL). Resolved when done; the answer records what was done and any resulting facts.

## Fog of war

The map is _deliberately_ incomplete: don't chart what you can't yet see. Beyond the live decisions lies the **fog of war**: the dim view of decisions you can tell are coming but can't yet pin down. Resolving a decision clears the fog ahead of it, graduating whatever's now specifiable into fresh decision files, one at a time, until the way to the destination is clear.

The map's **Not yet specified** section is where that dim view is written down: the suspected question, the area to revisit later. It's the undiscovered frontier _toward_ the destination: everything here is in scope, just not sharp enough to document as a decision.

**Fog or decision?** The test is whether you can state the question precisely now, _not_ whether you can answer it now.

- **Create a decision file when** the question is already sharp, even if it's blocked and you can't act on it yet.
- **Leave in "Not yet specified" when** you can't yet phrase it that sharply.

## Out of scope

Work beyond the destination is **out of scope**. It gets its own **Out of scope** section on the map: work you've consciously ruled out of _this_ effort. Scope, not sharpness, lands it here.

When a decision turns out to sit past the destination, **remove it from the open/blocked lists** and leave one line in **Out of scope**: the gist plus why it's out of scope. The decision file can be deleted or moved to an `out-of-scope/` subdirectory. It stays out of **Decisions so far**, which records the route actually walked.

## Invocation

Two modes. **Never resolve more than one decision per session**, with the exception of research decisions which can be parallelized.

### Chart the map

User invokes with a loose idea or large initiative.

1. **Name the destination.** Use `/dev-grill-me` to pin down what this map is finding its way to: the spec, decision, or change. The destination fixes the scope, so it's settled first.

2. **Map the frontier.** Grill again, **breadth-first**: fan out across the whole space, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog** (the way is already clear, the whole journey small enough for one session), you don't need a map. Stop and suggest `/dev-impl-plan` instead.

3. **Create the map structure**:
   ```bash
   # Create directory structure
   mkdir -p wayfinder/{initiative-slug}/{decisions,prototypes,research}
   
   # Create MAP.md
   cat > wayfinder/{initiative-slug}/MAP.md <<'EOF'
   # Wayfinder Map: {Initiative Name}
   
   ## Destination
   
   {what this effort is finding its way to}
   
   ## Notes
   
   - Domain: {relevant domain}
   - Skills to consult: /dev-grill-me, /dev-prototype
   
   ## Related Tickets
   
   <!-- Optional: link to parent Jira Epic if one exists -->
   
   ## Decisions so far
   
   <!-- Filled as decisions are completed -->
   
   ## Open decisions
   
   <!-- Ready to work, not blocked -->
   
   ## Blocked decisions
   
   <!-- Can't be worked yet due to dependencies -->
   
   ## Not yet specified
   
   {fog: vague areas to explore later}
   
   ## Out of scope
   
   <!-- Work ruled beyond the destination -->
   EOF
   ```

4. **Create the initial decision files** numbered sequentially:
   ```bash
   # For each decision identified
   cat > wayfinder/{initiative-slug}/decisions/01-{slug}.md <<'EOF'
   # Decision 1: {Question}
   
   **Type:** research | prototype | grilling | task
   **Status:** open
   **Blocks:** {decision numbers, if any}
   
   ## Question
   
   {the decision or investigation this resolves}
   
   ## Context
   
   {relevant background}
   
   ## Resolution
   
   <!-- Filled when completed -->
   
   ## Assets
   
   <!-- Links to prototypes, research, etc. -->
   EOF
   ```

5. **Update MAP.md** with links to all decision files in the appropriate sections (open, blocked).

6. **Fire research subagents** for any `research` type decisions, capturing findings on throwaway branches.

7. **Stop**: charting is one session's work; it hand-resolves nothing. Show the developer the map location and explain the frontier.

### Work through the map

User invokes with a map path (e.g., `/dev-wayfinder wayfinder/graphql-migration`) or just `/dev-wayfinder` if only one map exists. A decision number is optional: without one, you pick the next decision.

1. **Load the map**: Read MAP.md to get the overview.
   ```bash
   cat wayfinder/{initiative-slug}/MAP.md
   ```

2. **Choose the decision**:
   - If the user named one (e.g., "decision 3"), use it
   - Otherwise take the first from "Open decisions" list (marked as **← Next** or just the first one)
   - If all open decisions are claimed (status: in-progress), ask which one to work on

3. **Claim it**: Update the decision file status before any work.
   ```bash
   # Edit decisions/{number}-{slug}.md
   # Change: **Status:** open
   # To:     **Status:** in-progress
   ```

4. **Resolve it**:
   - Read the full decision file
   - Follow the decision type: call `/dev-prototype`, `/dev-grill-me`, or execute the task
   - For research decisions, spawn a subagent

5. **Record the resolution**:
   - Fill in the Resolution section in the decision file
   - Update status to `completed`
   - Add any links to Assets section (prototypes, research notes, etc.)
   - Move the decision from "Open decisions" to "Decisions so far" in MAP.md with a one-line gist

6. **Add newly-surfaced decisions**: 
   - Create decision files for anything the resolution made specifiable
   - Graduate fog from "Not yet specified" to new decision entries
   - Update blocking relationships
   - Add new decisions to MAP.md in the appropriate section

7. **Check if done**: If no open or blocked decisions remain and no fog, the map is complete. Update MAP.md status and hand off to implementation.

## Integration with ai-sdlc workflow

**Before wayfinding:**
- Large initiative identified (by PM or tech lead)
- Too big for `/dev-impl-plan` to handle in one session
- May start from `/pm-create-ticket` for the overall initiative Epic in Jira

**During wayfinding:**
- Each decision is resolved in its own session
- Use `/dev-prototype`, `/dev-grill-me`, or research as needed
- Update MAP.md after each decision
- The map directory can be committed to a branch for collaboration

**After wayfinding:**
- The map is complete when all decisions are made
- Break the work into sprint-sized tickets using `/pm-create-ticket`
- Each implementation ticket references the wayfinder map location for context
- Use `/dev-task-start` → `/dev-impl-plan` → `/dev-bug-fix` for each implementation ticket
- The wayfinder directory can be kept in the repo as documentation or archived

## Example flow

```bash
# 1. Chart the map
Developer: "We need to migrate from REST to GraphQL but I'm not sure how to approach it"
→ /dev-wayfinder
→ Creates wayfinder/graphql-migration/ with MAP.md
→ Destination: "Decision on GraphQL migration strategy and phased implementation plan"
→ Creates decision files:
   - 01-schema-design-patterns.md (type: research, status: open)
   - 02-client-data-fetching.md (type: prototype, status: open, blocks: 03)
   - 03-migration-approach.md (type: grilling, status: open, blocked by: 01, 02)

# 2. Work the frontier
→ /dev-wayfinder wayfinder/graphql-migration
→ Claims decision 01 (research, unblocked)
→ Spawns subagent to research schema patterns
→ Resolution filled in decisions/01-schema-design-patterns.md
→ Status updated to completed, moved to "Decisions so far" in MAP.md

# 3. Continue
→ /dev-wayfinder wayfinder/graphql-migration
→ Claims decision 02 (prototype, now unblocked)
→ Calls /dev-prototype to build sample queries
→ Developer reviews, decision made
→ Prototype linked in Assets, status completed

# 4. Repeat until map complete
→ All decisions resolved, findings captured in decision files
→ MAP.md shows all decisions completed, no fog remains
→ Create implementation tickets with /pm-create-ticket
→ Normal ai-sdlc flow resumes with /dev-task-start
```

## Directory Structure

A complete wayfinder map looks like this:

```
wayfinder/
└── graphql-migration/
    ├── MAP.md                           # The index
    ├── decisions/
    │   ├── 01-schema-design-patterns.md  # Completed
    │   ├── 02-client-data-fetching.md    # Completed
    │   ├── 03-migration-approach.md      # In progress
    │   └── 04-rollback-strategy.md       # Open
    ├── prototypes/
    │   └── client-queries/               # From decision 02
    │       └── prototype-queries.html
    ├── research/
    │   └── schema-patterns-notes.md      # From decision 01
    └── out-of-scope/
        └── 05-graphql-subscriptions.md   # Ruled out
```

## Anti-patterns to avoid

- Don't use wayfinder for work that fits in one sprint (use `/dev-impl-plan` instead)
- Don't resolve multiple decisions in one session (except research decisions)
- Don't skip the "claim decision" step (update status to in-progress before working)
- Don't leave fog vague forever (graduate it to decision files when possible)
- Don't implement while wayfinding unless explicitly noted in MAP.md Notes section
- Don't create decision files for work that's out of scope (move to out-of-scope/ and document why in MAP.md)
- Don't forget to commit the map directory to a branch for collaboration
- Don't duplicate information between MAP.md and decision files (MAP.md is an index only)
