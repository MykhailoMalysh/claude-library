---
name: dev-pr-preflight
description: Run the project's CI pipeline checks locally before opening a pull/merge request. Reads the pipeline definition (GitLab CI, Azure Pipelines, GitHub Actions), derives local check-only commands, confirms them with the developer, runs them in parallel, and reports what would fail in CI. Changes nothing in the repository. Use when the developer says "will CI pass", "run the pipeline checks", "verify before PR", "pre-flight", "check my branch before the MR", or invokes /dev-pr-preflight. dev-pr-open runs it automatically before creating a PR.
compatibility:
  required_tools:
    - Bash
    - Read
    - Agent
---

# dev-pr-preflight

Answers one question before a PR exists: **will the pipeline pass?** The pipeline file is the source of truth, so the project doesn't need a special `make verify` target, and nothing in the repository is added or changed.

You are the orchestrator, running in the main thread. Two shared agents do the work:
- `ai-sdlc:preflight-planner` translates the pipeline into local commands.
- `ai-sdlc:preflight-runner` runs one job and summarises failures.

Every non-OK agent status goes to `ai-sdlc:error-handler`, exactly as in `dev-pr-review` Phase 1b: one retry per step, then ask the developer. The contract is in `${CLAUDE_PLUGIN_ROOT}/references/agent-contract.md`.

**Nothing is modified.** Jobs run CI's own script in a throwaway copy of the committed tree under `/tmp`, so setup steps like copying config files never touch the repo. Checks run in check-only mode (`black --check`, never `black`). Nothing is installed; the developer's existing local environment is used. If a check fails, report it. Don't fix it unless the developer asks after seeing the results.

---

## Step 1: Context

Build the standard context block (`repo`, `base_ref`, `head_ref`, `merge_base`, `contract`). Determine the base the same way as `dev-pr-review` Phase 0a: the developer's choice, then `origin/HEAD`, then `origin/develop` / `main` / `master`. Run `git fetch origin <base-branch> -q` first.

Jobs run in a sandbox copy of the **committed** tree, the same code CI will see. If `git status --porcelain` shows uncommitted changes, say that they're **not** checked, and suggest committing first if they belong in the PR.

## Step 2: Get a plan

**Override.** If the repo's `.env` sets `PRE_PR_VERIFY_CMD`, treat it as a single-job plan (`name: custom`) and skip to Step 3. It's the developer's escape hatch for projects whose pipeline can't be reproduced automatically.

**Saved plan.** Confirmed plans are stored **outside the repository** at `~/.claude/ai-sdlc-data/preflight/<repo-slug>.json`, where `<repo-slug>` is the repo root path with `/` replaced by `_`. If a saved plan exists, recompute the pipeline fingerprint:
```bash
cat <plan.ci_files in order> | shasum -a 256
```
- If it matches the saved `ci_hash`, reuse the plan. Say in one line "Using the saved pre-flight plan (pipeline unchanged)", listing the job names.
- If it differs, the pipeline changed. Say so and re-plan.

**New plan.** Dispatch `ai-sdlc:preflight-planner` with the context block. Handle non-OK statuses through the error handler.

## Step 3: Confirm the plan

Show the plan compactly, one row per job: name, stage, the local command(s), and notes. Include a separate list of jobs marked `reproducible: false` with their reasons. For example:

```
Pre-flight plan from .gitlab-ci.yml (MR → develop):
  check_commit_emails  lint   git log --format='%H %ae' <merge-base>..HEAD | awk ... @epam.com
  flake8               lint   isort --check-only · black --check · flake8 src · flake8 tests  (src/…/.venv)
  mypy                 mypy   mypy src/document_activation_ingestion  (src/…/.venv)
  pytest               test   pytest -vv -x src/tests/unit  (src/…/.venv, PYTHONPATH from CI)
Not reproducible locally: none
Run these? (yes / edit / no)
```

On a new or changed plan, wait for the developer's answer. On `edit`, apply their changes to the plan. On `yes`, save the confirmed plan (with `ci_hash`) to the saved-plan path. A reused saved plan runs without asking again, because the developer already approved these exact commands.

## Step 4: Run

Dispatch one `ai-sdlc:preflight-runner` per reproducible job, **all in one message**, so they run in parallel. Each gets the context block plus its job object from the plan. Route non-OK statuses (run failures, not check failures) through the error handler.

## Step 5: Report

```
Pre-flight vs .gitlab-ci.yml — 3 passed · 1 failed · 0 not run
  ✓ check_commit_emails   ✓ flake8   ✓ pytest (212 passed)
  ✗ mypy — 4 type errors in 2 files
      src/.../x.py:42  Argument 1 has incompatible type "str | None"; expected "str"
      ...
Verdict: the pipeline would fail at stage `mypy`.
```

- List failing jobs with up to 10 items each, plus the log path for the rest.
- Include jobs that were not run (`reproducible: false`, skipped by the error handler, or errored) and state plainly that pre-flight **didn't cover** them. Never count an unrun job as passed.
- **Suspect the plan before the code.** If a job fails mostly on files the branch didn't change, the translation is probably wrong. Say so, and offer to re-plan instead of presenting a wall of failures as real.
- End with a one-line verdict: "pipeline would pass", "would fail at <stage/job>", or "could not verify <jobs>".

Return the report to the caller. When `dev-pr-open` invoked this skill, it uses the report to decide whether to proceed and to fill the PR's Testing section.

## Why it works this way

- **The pipeline is the source of truth.** Local targets drift from CI. For example, a `make lint` without the formatting checks passes locally and fails in the pipeline. Reading the pipeline avoids that.
- **Run CI's script as written, in a sandbox.** Rewriting commands to avoid side effects (for example, replacing `cp pyproject.toml .` with tool flags) changes tool behaviour in subtle ways. A copy of the committed tree lets the script run unchanged.
- **Confirm once per pipeline version.** Deriving commands from CI YAML involves judgment: environments, working directories, variables. The developer checks that translation once. The fingerprint forces a re-check whenever the pipeline changes.
- **Check-only, no installs.** A verification step that reformats files or changes the environment isn't verification any more, and it would break the "no changes in repo" rule.
