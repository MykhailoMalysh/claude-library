---
name: dev-grill-me
description: Conduct a relentless, adversarial interview to sharpen an implementation plan, design, or technical approach before code is written. Use when the developer says "grill me on this plan", "challenge my approach", "poke holes in this design", "what am I missing", or invokes /dev-grill-me. Especially valuable after dev-impl-plan produces a plan but before implementation begins.
compatibility:
  required_tools:
    - Read
    - Agent
---

# dev-grill-me

A relentless interview process that stress-tests implementation plans, designs, and technical approaches through adversarial questioning. The goal is to find gaps, assumptions, edge cases, and potential failure modes before code is written — when changes are cheapest.

## When to Use

- Developer says "grill me on this plan", "challenge my approach", "what could go wrong with this design"
- Developer invokes `/dev-grill-me`
- After `/dev-impl-plan` creates a plan but before implementation starts — use this to validate the plan is solid
- Developer presents a technical design or architecture decision and wants it stress-tested
- Before committing to a large refactor or complex feature — surface risks early

Do not use this skill for:
- Simple, obvious implementations that don't benefit from deep questioning
- After code is already written (use code review instead)
- When the developer just wants you to execute their plan without challenge

## Prerequisites

Either:
- A written implementation plan (e.g., from `/dev-impl-plan` or manually drafted)
- A technical design/approach described in the conversation or in a file
- A ticket or specification that defines the work

## Workflow

### Step 1: Identify what to grill

If a plan file was mentioned or created earlier in the conversation, read it. If the developer referenced a ticket, fetch it. If they described an approach inline, work from that.

If nothing specific was provided, ask: "What plan or approach should I grill you on?"

### Step 2: Spawn the griller agent

Spawn a subagent with `subagent_type: ai-sdlc:griller`. It's a shared plugin agent defined in `${CLAUDE_PLUGIN_ROOT}/agents/griller.md`, and `dev-pr-review` uses it too. Pass it:
- The full text of the plan, design, or approach (or its file path)
- Any relevant context (ticket details, acceptance criteria, constraints mentioned by the developer)

The agent ends with a `report` block and a `status` block (see `${CLAUDE_PLUGIN_ROOT}/references/agent-contract.md`). If the status isn't `ok`, or the `ai-sdlc:griller` type isn't available, dispatch `ai-sdlc:error-handler` with the status and the original task, and follow its decision. You get one retry. For `use_fallback_agent`, dispatch `general-purpose` with the body of `agents/griller.md` prepended to the task.

The agent will conduct a structured adversarial interview, probing for:
- **Unstated assumptions**: What are you assuming will be true that might not be?
- **Edge cases**: What inputs, states, or conditions could break this?
- **Failure modes**: How could this fail in production? What's the blast radius?
- **Missing requirements**: What acceptance criteria or constraints aren't addressed?
- **Overlooked alternatives**: What other approaches were not considered, and why not?
- **Dependencies and risks**: What external systems, data, or teams could block or derail this?
- **Testing gaps**: How will each part be verified? What could slip through?
- **Performance and scale**: How does this behave under load, with large data, or over time?
- **Maintenance burden**: What complexity or technical debt is this introducing?
- **Rollback and recovery**: If this goes wrong in production, how do we recover?

### Step 3: Present the findings

Once the griller agent completes its session, it will return a structured report of findings — gaps identified, risks surfaced, questions the developer should answer before proceeding.

Present this report to the developer clearly, organized by severity:
1. **Critical gaps**: Things that would cause the plan to fail or cause production issues
2. **Important questions**: Assumptions or edge cases that need explicit decisions
3. **Nice-to-haves**: Suggestions for improvement that aren't blockers

For each finding, include:
- What the issue is
- Why it matters
- A question or suggestion for how to address it

### Step 4: Offer next steps

After presenting the findings, offer the developer these options:
- Revise the plan to address the critical gaps, then optionally re-grill
- Answer the questions and clarify assumptions, updating the plan inline
- Proceed with implementation, acknowledging the identified risks
- Abandon or significantly restructure the approach

## Example Grilling Flow

**Developer**: "I just finished the plan for PROJ-123, grill me on it"

**Claude**: *reads the plan file, spawns griller agent with plan content and ticket context*

**Griller agent returns findings**

**Claude presents**:
```
I've grilled your plan for PROJ-123. Here's what I found:

**Critical Gaps**:
1. The plan assumes the `users` table has an `email` column, but I don't see where that's verified — if it doesn't exist yet, the migration will fail
2. No error handling for when the external API times out — this could leave records in a partial state

**Important Questions**:
3. What happens if a user has multiple active sessions when you invalidate tokens? Does each session need individual handling?
4. The plan mentions "updating the auth middleware" but doesn't specify which middleware — there are 3 different auth layers in the codebase

**Suggestions**:
5. Consider adding a feature flag for rollback — if the new auth flow breaks, you'll want a quick escape hatch
```

**Developer**: "Good catches — let me update the plan to address 1 and 2, and I'll clarify the middleware question"

## Why This Workflow

Plans and designs often look solid on paper but have subtle gaps — unstated assumptions, unhandled edge cases, missing error paths. Catching these before code exists is 10x cheaper than catching them in code review, and 100x cheaper than catching them in production. A grilling session forces you to defend your approach against adversarial questioning, surfacing risks while they're still cheap to fix.

The griller agent is deliberately adversarial — it's not trying to validate your plan, it's trying to break it. This is the point. Better to have Claude poke holes now than to have production poke holes later.

## Integration with Other Skills

- **After `/dev-impl-plan`**: Plan → Grill → Implement (if plan survives grilling)
- **Before `/dev-bug-fix` on complex bugs**: Describe your fix approach → Grill → Implement
- **With `/dev-pr-review`**: Ask the review to "grill" the PR and it runs the same `griller` agent against the diff alongside the finders
