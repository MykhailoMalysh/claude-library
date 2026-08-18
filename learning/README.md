# Learning Skills

Claude Code skills for **learning while building** — projects where writing the
code by hand is part of the point, not just the deliverable. Distinct from the
task-lifecycle skills in [`v.1.0.0`](../v.1.0.0): those optimize for shipping,
these optimize for retaining the skill of writing the code yourself, in
exactly the parts of a project where that's the actual goal.

## Skills

| Skill | Trigger phrase | What it does |
|---|---|---|
| `learning-with-code` | "learn while building", "pair programming rules", "don't just write it for me" | Writes a scoped pair-programming protocol into a project's `CLAUDE.md` — hints and Socratic questions inside the named learning surface, full agentic speed everywhere else |

## Applying to a project

### 1. Copy the versioned folder

```
cp -r path/to/claude-library/learning/v.0.0.1/.claude your-project/
```

If your project already has a `.claude` folder, merge `skills/learning-with-code`
into the existing `skills/` directory rather than overwriting.

### 2. Invoke it once per project

In a Claude Code session inside the project:

> "Set up learning-with-code for this repo — I'm learning \<X\>, I'm already
> solid on \<Y\>."

The skill writes a delimited, idempotent block into `CLAUDE.md` (or
`AGENTS.md`) naming the learning surface and the mastered surface. Every
future session in that repo picks up the protocol automatically — no need to
invoke the skill again unless the scope changes.

### 3. What it changes

Inside the named learning surface: no unprompted full function/class bodies,
one genuine Socratic question before explaining, exactly one small hint on
request, and full compliance without friction on an explicit "just show me."
Outside it — boilerplate, mastered components, reviewing code you already
wrote — full agentic speed, untouched.

See `.claude/skills/learning-with-code/SKILL.md` for the full protocol and
`scripts/apply_protocol.py` for the merge mechanics.

## Versions

- **v.0.0.1** — initial release. `learning-with-code` only.
