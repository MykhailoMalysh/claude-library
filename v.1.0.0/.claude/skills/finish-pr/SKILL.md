---
name: finish-pr
description: "Merges verified PRs, closes their linked issues, and moves the corresponding board items to Done — all via a script to avoid spending tokens on mechanical shell commands. Use whenever the user says 'merge PR', 'finish PR', 'close PR', 'ship PR', 'finish PR 17 and 18', or any similar phrase asking to land one or more verified pull requests. If no PR number is given, list open PRs and ask which to finish."
---

# Finish PR

Runs `scripts/finish_pr.py` to do all the mechanical work in one shot. Claude's only job here is to resolve which PRs to finish and then invoke the script — not to issue gh commands step by step.

## Step 1 — Resolve the PR(s)

- **Explicit numbers** ("finish PR 17 and 18") → pass them directly.
- **Current branch** ("finish current PR") → `git rev-parse --abbrev-ref HEAD`, find the matching open PR.
- **Nothing specified** → run the script in list mode, show the output to the user, and ask which PRs to finish before proceeding.

```bash
python3 .claude/skills/finish-pr/scripts/finish_pr.py --list
```

## Step 2 — Run the script

Pass PR numbers in merge order (base PRs first; stacked PRs last):

```bash
python3 .claude/skills/finish-pr/scripts/finish_pr.py 17 18
```

The script will:
1. Merge each PR (squash + delete branch). Skips PRs already merged or auto-closed.
2. Parse `Closes #N` / `Fixes #N` from each PR body and close those issues.
3. Discover the project board IDs at runtime (reads project number from `.claude/memory/project_config.md`).
4. Move each closed issue's board item to **Done**.

## Step 3 — Report

Show the script's stdout to the user. No further action needed unless the script reports an error.

## When the script fails

- **Merge conflict** → tell the user to resolve the conflict locally and re-run, or retarget the PR manually.
- **Project board not found** → check that `project_config.md` has the board number, or pass `--project N` explicitly.
- **Issue not on board** → the script warns and continues; not a blocker.
