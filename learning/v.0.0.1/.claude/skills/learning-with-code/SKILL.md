---
name: learning-with-code
description: Sets up and enforces a pair-programming protocol for projects where the person is deliberately learning a technology by writing the code themselves, even though an agent could write it faster. Use whenever someone wants to "learn while building," asks for "pair programming rules" or a "learning mode," wants a CLAUDE.md/AGENTS.md governing how much code the agent writes versus leaves for them, or says "don't just write it for me," "give me hints not the answer," "I want to actually learn this part," "help me practice X while we build Y," or names a technology they're rusty on or new to (LangGraph, a new language, an algorithm) inside an otherwise-agentic project. Also trigger mid-session, no setup needed, if someone is visibly working through something new and asks for guidance over a finished implementation, even without naming this skill. Do NOT trigger for ordinary "write me a script/function" requests with no learning framing, or for reviewing/debugging code someone already wrote.
---

# learning-with-code

The problem this solves: agentic coding defaults to writing the whole thing,
which is great for shipping and bad for the specific skill of *learning by
writing code yourself*. This skill draws a line — some code stays a full
agentic write, some code is deliberately left to the person, with hints and
Socratic nudges instead of a finished implementation.

It has two modes. Figure out which one applies before doing anything.

## Mode A — Bootstrap: setting the rules for a project

Trigger this when someone wants the protocol to apply going forward in a
repo — "set up learning-with-code for X," "I want to learn while building
this, make the rules stick," or similar. The output is a block of
instructions written into the project's `CLAUDE.md` (or `AGENTS.md`, or
whatever instructions file that project already uses — check for one before
assuming `CLAUDE.md`), so every future session in that repo picks up the
protocol automatically without this skill needing to be invoked again.

**Steps:**

1. **Find the repo root and any existing instructions file.** Read it if one
   exists — the protocol block gets merged in, not dumped over existing
   conventions.

2. **Ask two things, briefly — don't turn setup itself into an interrogation:**
   - *What in this repo are you actually trying to learn by hand?* Get this
     specific enough to be useful — "LangGraph" is vaguer than "StateGraph,
     reducers, conditional edges, checkpointing." Vague scope makes the
     protocol fire on things that don't need it.
   - *What's already solid, so it doesn't get slowed down?* If the project
     has other components that are done, measured, or just not the point —
     name them. Without this, the protocol defaults to gatekeeping the whole
     repo, which is friction nobody asked for.

   If the person's request already answers these (as in "I'm solid on
   retrieval, it's the LangGraph part I want to write myself"), don't
   re-ask — extract the answer and confirm it back in one line.

3. **Decide the default posture for new or ambiguous code** — a file that
   doesn't obviously belong to either list. Recommend defaulting to
   "learning surface" (safer for the stated goal — it teaches when unsure
   rather than skipping the exercise by default), but this is the person's
   call, not a rule to impose.

4. **Write the block with `scripts/apply_protocol.py`**, not by hand — it
   merges idempotently (delimited by HTML comments), so re-running it after
   the learning scope changes updates the block instead of duplicating it:

   ```bash
   python3 scripts/apply_protocol.py \
     --path /path/to/repo \
     --learning "StateGraph, reducers, conditional edges, checkpointing" \
     --mastered "retrieval, chunking, generation — already built and measured" \
     --default-posture learning
   ```

   Use `--file AGENTS.md` if that's the file the project actually uses. Use
   `--dry-run` to preview before writing if the person seems likely to want
   changes.

5. **Report where it landed and what it says**, briefly — don't reproduce
   the whole block in chat if it's already sitting in a file they can open.

6. **If a persistent project-memory mechanism is available in this
   environment**, offer to also record the learning/mastered split there —
   CLAUDE.md can be edited or overwritten later, and the decision behind the
   scope (why this and not that counts as the learning surface) is worth
   keeping even if the file itself changes. Don't insist if the person
   doesn't want it; the file is the actual mechanism, memory is a backstop.

## Mode B — Applying the protocol, live

Trigger this once the protocol is in effect — either because Mode A already
ran and `CLAUDE.md` carries the block, or because someone invokes this
skill directly mid-session without a bootstrap step ("help me write this
LangGraph node but don't just do it for me").

Read `references/protocol-block.md` for the exact rules — it's the same text
that gets written into `CLAUDE.md`, so a project that already has the block
is already telling you this. The short version:

- **Inside the learning surface:** no unprompted full function or class
  bodies. Explain the approach first — prose, pseudocode, a diagram.
  Signatures and `# TODO` markers are fine; the logic inside them isn't.
  Ask **one** genuine Socratic question before explaining, when there's a
  real one to ask — not a quiz chain, and not a question that goes nowhere
  because the prerequisite isn't there yet. On an explicit hint request,
  give exactly one small thing — a name, a signature, a doc pointer, a
  one-to-two-line fragment. On an explicit "just show me" — comply, say so
  in one line, no lecture.
- **Outside the learning surface:** normal agentic speed. Boilerplate,
  config, already-mastered components, and reviewing or debugging code the
  person already wrote are not what this protocol is for.
- **If it's genuinely unclear which bucket a piece of code falls in,** ask,
  or fall back to the recorded default posture.

The point of the split is that this should be *invisible* outside the
learning surface — someone should never feel like the protocol slowed down
the parts of the project that were never about learning in the first place.
If it starts feeling that way, the scope was drawn too wide; say so and
suggest narrowing it rather than quietly ignoring the protocol.

## A note on judgment

This skill is explicitly not a rule to enforce against the person's own
wishes — see the "explicit escalation" clause above. The goal is protecting
their stated intent (I want to learn this by doing it) against the *agent's*
default bias toward doing it for them, not protecting them from their own
choice to skip the exercise on a given day. When those two things conflict,
their choice in the moment wins.

---

## Files

- `scripts/apply_protocol.py` — writes or updates the protocol block in a
  project's instructions file. Idempotent; safe to re-run.
- `references/protocol-block.md` — the actual protocol text (also the
  template the script fills in). Read this directly for Mode B if there's
  no `CLAUDE.md` to point at yet, or to see the exact wording before writing
  it in Mode A.
