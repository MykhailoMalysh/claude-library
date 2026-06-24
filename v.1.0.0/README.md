# Claude Task Lifecycle Library

A set of Claude Code skills that implement a GitHub-board-driven task lifecycle:
**start → plan → build → validate → triage → merge**.

Each stage is a skill Claude invokes automatically. The skills handle board discovery, branch
creation, test-driven development, PR opening, automated review, and board status updates — all
without you issuing shell commands manually.

---

## Skills

| Skill | Trigger phrase | What it does |
|---|---|---|
| `start-task` | "start a task", "what's next" | Picks the next issue from the board, checks blockers, cuts a branch |
| `plan-task` | "plan the task", "make a plan" | Reads the issue spec, writes a test-first plan to `.plans/` |
| `implement-task` | "implement the task", "build this" | Runs preflight, builds TDD from the plan, opens the PR |
| `validate-pr` | "validate PR", "review PR" | Reads the diff, posts a structured review comment on GitHub |
| `triage-pr-findings` | "triage PR findings" | Grades each finding: Critical / Medium / Low / Trivial / Resolved |
| `finish-pr` | "finish PR", "merge PR" | Squash-merges, closes linked issues, moves board items to Done |

The `/run-task` command orchestrates all six stages end-to-end as subagents, pausing for your
approval between stages (or running fully autonomously with `auto`).

---

## Applying to a project

### 1. Copy the versioned folder

Copy the `.claude` folder from the version you want into the **root of your project repo**:

```
cp -r path/to/claude-library/v.1.0.0/.claude  your-project/
```

If your project already has a `.claude` folder, merge the contents manually — particularly
`settings.json` (plugins) and the `skills/` and `commands/` directories.

### 2. Configure your project

Edit `.claude/memory/project_config.md` and fill in the three variables:

```
ISSUES_REPO: owner/repo-name       # GitHub repo where issues and the Projects board live
BOARD_NUMBER: 5                    # GitHub Projects (v2) board number
CODE_REPO: owner/other-repo        # Repo where branches are created (omit if same as ISSUES_REPO)
```

Finding `BOARD_NUMBER`: open the board in GitHub — the number is the last segment of the URL:
`github.com/orgs/<org>/projects/<number>`.

### 3. Create your local settings

Create `.claude/settings.local.json` (this file is gitignored — do not commit it):

```json
{
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
  },
  "permissions": {
    "allow": [],
    "defaultMode": "bypassPermissions"
  },
  "enabledMcpjsonServers": [
    "github"
  ]
}
```

The token needs `repo` and `project` scopes.

### 4. Enable the required Claude Code plugins

The skills depend on these plugins being enabled in Claude Code:

- `superpowers` — core skill-loading and workflow primitives
- `github` — GitHub MCP server (issues, PRs, board)
- `code-review` — used by `validate-pr`
- `code-simplifier` — used during refactor passes
- `feature-dev` — TDD scaffolding
- `security-guidance` — security checks during review

These are already declared in `.claude/settings.json`. Claude Code will prompt you to enable
any that are missing when it starts.

### 5. Adapt the preflight script (optional)

`.claude/skills/implement-task/scripts/preflight.sh` runs before every test suite execution.
Out of the box it checks that Docker is reachable. Extend it for your project's actual needs:

```bash
# examples of what to add:
export DATABASE_URL="postgres://localhost:5432/mydb"
pg_isready -q || fail "Postgres not running — start it before running tests."
```

If your project has no environment preconditions, the default no-op script works fine.

---

## Versions

| Version | Folder | Notes |
|---|---|---|
| 1.0.0 | `v.1.0.0/` | Initial release — GitHub board lifecycle, generic (no project-specific assumptions) |

---

## How the config file is read

All scripts and skills read from `.claude/memory/project_config.md`. The file is plain Markdown;
the scripts extract values by regex, so the format is flexible — just make sure each key appears
on its own line followed by a colon and the value:

```
ISSUES_REPO: myorg/my-project
BOARD_NUMBER: 5
CODE_REPO: myorg/my-service
```

The `board.py` library resolves the file relative to its own location inside `.claude/skills/_lib/`,
so the path always resolves correctly regardless of which directory you run commands from.
