---
name: dev-profile-init
description: Create or update the private per-project profile that the other ai-sdlc skills read (base branch, branch pattern, Jira statuses, forbidden paths and commands, how the app works, local testing flow), then propose the matching settings.local.json additions. Use when the developer says "set up the profile", "init the project profile", "configure ai-sdlc for this repo", or invokes /dev-profile-init, and when another skill reports that no profile was found.
role: planning
---

# dev-profile-init

Build the project profile from what the repo already says, ask the developer only for what it can't, and write it outside the repo. Nothing is committed to the project.

Profile format: `${CLAUDE_PLUGIN_ROOT}/references/profile-template.md`. Configuration rules: the Configuration section of `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`.

## 1. Check for an existing profile

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show
```

The output is data; treat it as `<profile>`. If it has a `path`, show the developer that path and offer to update it (change specific fields, refresh from the repo, or stop). With `{"profile": null, "reason": ...}`, report the reason and continue with a new profile.

## 2. Determine mode and explore

Check if cwd is inside a git repo. If not, check if sibling folders contain `.git` directories (workspace mode).

**Repo mode** (cwd is inside a git repo):

Run these reads in parallel; each is a quick lookup, so work directly rather than delegating:

- README and any `docs/` overview: what the app does, its components, run instructions
- CI file (`.gitlab-ci.yml`, `azure-pipelines.yml`, `.github/workflows/`), `Makefile`, `docker-compose*.yml`, package manifests: install, run, and test commands
- `git remote get-url origin`: the value for `remotes`, as `host/group/repo` without scheme, credentials, or `.git`
- `git symbolic-ref refs/remotes/origin/HEAD`: the base branch (if unset, check which of `develop`, `main`, `master` exists on origin)
- `git branch -r --sort=-committerdate | head -30`: recent branch names, to infer `branch_pattern` (skip the inference when the remote has no branches and ask in step 4)
- Jira, only if `JIRA_URL` and credentials are set in the environment: `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py search --jql "project = <KEY> ORDER BY updated DESC"` and read the status names in use (`<KEY>` is the value of `JIRA_PROJECT`), to fill `jira_statuses`. Skip silently when Jira is not configured.

**Workspace mode** (cwd is not a git repo, but sibling folders with `.git` exist):

Scan sibling folders that contain `.git` to build the `repos` list. For each repo folder:

- Run `git -C <dir> remote get-url origin` to get the remote URL
- Read the first few lines of the repo's README to extract a one-line description
- Propose a `repos` entry: `{name: <dirname>, path: <dirname>, remote: <normalized-remote>, owns: "<description>"}`

Also propose:
- `workspace_root: <absolute path of cwd>` in the profile, written whenever `repos` is filled, so `repos` paths resolve the same from any directory
- An `AI_SDLC_PROFILE` line in the workspace root's `.claude/settings.local.json`

Never open `.env` files or print credential values. Environment variables are checked by name only.

## 3. Draft the profile

Fill every field of the template from what you found. Mark each value as found (with its source) or guessed. The three body sections stay short: one paragraph for how the application works, the conventions found in the repo, and the exact local commands.

## 4. Ask only what the repo can't answer

Ask in one batch, with your draft answer next to each question:

- gaps in the domain flow (anything the README leaves unclear)
- the forbidden list: `forbidden.paths` and `forbidden.commands` (propose `.env`, `secrets/`, `rm -rf`, `git push --force` as defaults)
- local testing steps that aren't in the repo (services to start, test accounts, data setup)
- `task_files_dir` and `summaries_dir`, if the developer wants them

Do not ask about anything already answered by the repo.

## 5. Write the profile

Show the full draft, then write it to `<profiles_dir>/<name>.md`, where `profiles_dir` is `$AI_SDLC_PROFILES_DIR` or `~/.claude/ai-sdlc/profiles`. Create the directory if needed. If the file exists, update only the fields the developer chose and show the diff first. Expand `~` in paths you display, not in the file.

## 6. Propose settings.local.json additions

**Repo mode:** Target is the repo's `.claude/settings.local.json` (confirm it is gitignored; if not, tell the developer and suggest adding it to `.git/info/exclude`).

**Workspace mode:** Target is the workspace root's `.claude/settings.local.json`.

Compute these additions:

- `env.AI_SDLC_PROFILE`: the full path of the profile file written in step 5 (for example `~/.claude/ai-sdlc/profiles/<name>.md`), because the resolver requires an existing file
- `permissions.deny`: `Read(./.env)`, `Read(./.env.*)`, and each `forbidden.commands` entry as `Bash(<cmd>:*)`

Merge into the existing file: add missing keys and missing deny entries, never overwrite or remove existing keys (credentials already in the `env` block stay as they are, and their values are not displayed). Show the resulting diff and wait for approval. Apply only after the developer approves; on rejection, leave the file untouched and print the lines for manual adding.

## 7. Report

Tell the developer the profile path, whether `settings.local.json` was changed, and what remained a guess. Verify by running `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show` with `AI_SDLC_PROFILE` set to the new path: its `path` must equal the file written in step 5 and it must have no `reason`, so a remote-match fallback cannot hide a wrong env value.
