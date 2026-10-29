---
name: dev-prototype
description: Build a throwaway prototype to answer a design question — a single shareable HTML file for testing state/logic, or several toggleable UI variations to explore what something should look like. Use when the developer wants to sanity-check whether a state model or logic feels right, or explore UI options before committing to an implementation. Also use when the developer says "prototype this", "build a quick demo", "let's see what this looks like", "test the state model", or invokes /dev-prototype.
role: planning
compatibility:
  required_tools:
    - Bash
    - Read
    - Write
---

# dev-prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

## When to Use

- Developer wants to explore "does this logic/state model feel right?" before implementing
- Developer wants to see "what should this look like?" with multiple UI variations
- Developer says "prototype this", "build a quick demo", "let's see what this looks like"
- Developer invokes `/dev-prototype`
- After `/dev-impl-plan` produces a plan but there's uncertainty about UX or state behavior

This skill creates throwaway artifacts to validate design decisions, not production code.

## Prerequisites

None required. This skill works standalone or alongside the ai-sdlc workflow. If working within a ticket context:
- Can reference the current task file at `{task_files_dir}/{ticket-number}.md` if it exists (created by `dev-task-start`)
- Can access branch context via `git branch --show-current`
- `task_files_dir` comes from the profile (`python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show`), default `tasks/`. Prototype files never go into a `forbidden.paths` location from the profile.

## Pick a branch

Identify which question is being answered, using the user's prompt, the surrounding code, or by asking if the user is around:

* **"Does this logic / state model feel right?"** → Build a single shareable HTML file (free-play buttons plus tabbed guided walkthroughs) that pushes the state machine through cases that are hard to reason about on paper, and that a non-developer can drive.
* **"What should this look like?"** → Generate several radically different UI variations on a single route, switchable via a URL search param and a floating bottom bar.

The two branches produce very different artifacts, so getting this wrong wastes the whole prototype. If the question is genuinely ambiguous and the user isn't reachable, default to whichever branch better matches the surrounding code (a backend module → logic; a page or component → UI) and state the assumption at the top of the prototype.

## Rules that apply to both

1. **Throwaway from day one, and clearly marked as such.** Locate the prototype code close to where it will actually be used (next to the module or page it's prototyping for) so context is obvious, but name it so a casual reader can see it's a prototype, not production. For throwaway UI routes, obey whatever routing convention the project already uses; don't invent a new top-level structure. Common naming patterns:
   - `prototype-{feature-name}.html`
   - `{module}-prototype/`
   - `prototypes/{feature}/`

2. **Trivial to run.** A UI prototype starts from one command in the project's task runner: `pnpm <name>`, `python <path>`, `bun <path>`, etc. A logic demo is a single HTML file the user double-clicks. Either way, no thinking required to start it.

3. **No persistence by default.** State lives in memory. Persistence is the thing the prototype is _checking_, not something it should depend on. If the question explicitly involves a database, hit a scratch DB or a local file with a clear "PROTOTYPE, wipe me" name.

4. **Skip the polish.** No tests, no error handling beyond what makes the prototype _runnable_, no abstractions. The point is to learn something fast.

5. **Surface the state.** After every action (logic) or on every variant switch (UI), print or render the full relevant state so the user can see what changed.

6. **Capture it when done.** Fold any validated decision into the real code, then capture the prototype itself as a **primary source**: commit it to a throwaway branch, out of main, and leave a context pointer to that branch on the implementation issue. Capture the answer too (the verdict and the question it settled) in the issue or a commit. The main branch keeps only the validated decision.

## Workflow

### Step 1: Understand the question

- If working in a ticket context, check for `{task_files_dir}/{ticket-number}.md` to understand requirements
- Clarify what question the prototype needs to answer
- Determine which branch (logic vs UI) fits the question
- Identify where the prototype code should live (near the related module/component)

### Step 2: Build the prototype

**For logic/state prototypes:**
- Create a single HTML file with embedded JavaScript
- Include free-play controls (buttons/inputs) to manipulate state
- Add tabbed sections showing guided walkthroughs of key scenarios
- Display the full state after each interaction
- Make it shareable (no build step, no dependencies)

**For UI prototypes:**
- Create 3-5 radically different variations
- Use URL search params to switch between them (`?variant=A`)
- Add a floating bottom bar with variant switcher
- Keep variations in one place (one file or one directory)
- Use inline styles or minimal CSS to avoid setup overhead

### Step 3: Document the prototype

At the top of the prototype file(s), include:
```
<!-- PROTOTYPE: {question being answered} -->
<!-- Created: {date} -->
<!-- Related ticket: {JIRA-123 if applicable} -->
<!-- DO NOT USE IN PRODUCTION -->
```

### Step 4: Run and validate

- Show the developer how to run it
- Walk through key scenarios
- Capture findings and decisions

### Step 5: Capture learnings

If working in a ticket context:
- Add findings to the task file at `{task_files_dir}/{ticket-number}.md` under "Decisions already made"
- Link to the prototype branch in the task file or Jira ticket
- Note which decisions were validated and which need more exploration

If working standalone:
- Document the decision and reasoning
- Commit the prototype to a throwaway branch with a clear name like `prototype/{feature}-{question}`

## Integration with ai-sdlc workflow

When used after `/dev-impl-plan`:
- Read the plan to understand what needs prototyping
- Reference the task file for context
- Update the task file with prototype findings before moving to `/dev-implement`

When used during `/dev-implement`:
- Can pause implementation to validate a design decision
- Prototype in a separate directory/file
- Resume implementation once the question is answered

## Examples

**Example 1: State model validation**
```
Developer: "I'm not sure if the order state transitions make sense. Can we prototype it?"
→ Create `prototype-order-states.html` with buttons to trigger state changes and a visual state diagram
```

**Example 2: UI exploration**
```
Developer: "We need a dashboard but I'm not sure what layout works best"
→ Create `prototype-dashboard/` with 4 variations: grid, list, cards, split-pane
→ Each accessible via ?variant=grid, ?variant=list, etc.
```

**Example 3: Integration with ticket workflow**
```
Developer: "/dev-task-start PROJ-123" → "/dev-impl-plan" → "/dev-prototype"
→ Read {task_files_dir}/{ticket-number}.md for context
→ Build prototype to answer open questions
→ Update task file with findings
→ Ready for "/dev-implement" with validated decisions
```

## Anti-patterns to avoid

- Don't build production-ready code (defeats the purpose)
- Don't create elaborate build setups (keep it simple)
- Don't leave prototypes in the main codebase without clear marking
- Don't skip the "capture learnings" step (the answer is more valuable than the code)
- Don't treat the prototype as the deliverable (it answers a question, not ships a feature)
