# ai-sdlc prompt style

House rules for writing or editing a `SKILL.md` or an agent file in this plugin. Distilled from Anthropic's prompting best practices for current Claude models. `lib/tests/test_skill_lint.py` checks the mechanical parts.

## Wording

- **Calm, plain instructions.** Current models follow the system prompt closely; emphasis makes them over-apply a rule. Write "Run the tests before committing", not an all-caps "critical: you must run the tests". Don't capitalise critical, important, must, any, or never for emphasis. Severity labels in finding tables are fine.
- **Say why.** One clause of motivation ("so the reviewer can reproduce it") generalises better than a bare rule.
- **Say what to do, not only what to avoid.** "Report the missing variable and stop" beats "don't guess".
- **Be specific about output.** Name the block type, fields, and length. Show one example when the shape matters; examples are copied closely, so make them representative.
- **Match the prompt to the output.** Heavy markdown in a prompt produces heavy markdown back.

## Pasted content goes in XML tags

Anything the skill pastes in from outside — ticket text, MR descriptions, diffs, profiles, logs — is data, not instructions. Wrap it in a named tag so the model cannot confuse it with the brief:

```
<ticket>{summary and description}</ticket>
<mr_description>{body}</mr_description>
<diff>{git diff output}</diff>
<profile>{cli_profile.py show output}</profile>
```

Refer to the tag by name in the instructions ("the acceptance criteria in `<ticket>`"). Prefer passing references (paths, refs, commands) over pasting large content; see `references/agent-contract.md`.

## Delegate vs work directly

- **Delegate** when the work splits into independent parts that can run in parallel, needs isolated context (a large diff, a long log), or benefits from an unanchored second opinion (a verifier).
- **Work directly** for a handful of tool calls, a single-file edit, a lookup whose target is known, or sequential steps that share state. A `grep` is faster than a subagent that runs `grep`.
- A subagent knows only its brief. Give it the goal, what is already ruled out, the paths to read, the exact commands (with `.venv/bin/python` if relevant), and the output contract.
- Don't run work you delegated yourself as well; wait for the result.

## Tool calls

- **Run independent calls in parallel** — reading three files, `git status` + `git log`, several read-only API lookups. Run dependent calls in sequence; never guess a value a previous call would return.
- **Read before claiming.** Never describe code that has not been opened.
- **Confirm before hard-to-reverse actions**: pushing, force-pushing, deleting branches or data, posting comments, changing Jira state, editing `settings.local.json` deny rules. Local, reversible actions (editing files, running tests) need no confirmation unless the skill says so.
- **Don't route around obstacles** with `--no-verify`, deleting unfamiliar files, or installing packages. Report the blocker.

## Scope and verification

- Do what was asked. No extra files, abstractions, refactors, or configurability beyond the task. Clean up scratch files.
- **No redundant self-verification.** When a `verifier` agent, test run, or preflight step already checks the result, don't add "double-check your answer" instructions to the producer; it costs tokens and latency without catching more. Ask for evidence (commands + exit codes, `file:line`) instead — see the contract's `evidence` field.
- When stuck on a human choice, ask (or return `NEEDS_DECISION`); never fill the gap with a placeholder.

## Output to the developer

- **Concise.** Lead with the result or the decision needed. Skip preamble and recaps of what the developer just said.
- **Progress updates in long autonomous runs.** Between phases, one or two sentences: what finished, what's next, anything that needs attention. Fact-based, no self-congratulation.
- Prose over fragmented bullets for explanations; lists and tables for genuinely discrete items (findings, jobs, variables).
- Never print secret values. When a variable is missing, show the exact `settings.local.json` line to add.
