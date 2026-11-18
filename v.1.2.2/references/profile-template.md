---
name: my-project
remotes: [git.example.com/group/repo]
base_branch: main
branch_pattern: "user/{username}/{ticket}-{description}"
jira_project: PROJ
jira_statuses: {start: [Open, To Do], in_progress: In Progress, in_review: In Review, done: Done}
task_files_dir: docs/tasks
summaries_dir: ~/Obsidian/summaries
forbidden: {paths: [.env, secrets/], commands: [rm -rf, git push --force]}
# Optional: for multi-repo workspaces (team skills run from workspace root, not inside a repo)
# workspace_root: /Users/username/projects/my-workspace
# repos:
#   - {name: frontend, path: ui-app, remote: git.example.com/group/ui-app, owns: "UI layer"}
#   - {name: backend, path: api-service, remote: git.example.com/group/api, owns: "REST API"}
---

## Frontmatter fields

- `name`: Profile identifier
- `remotes`: List of git remote URLs (normalized to host/group/repo) for profile auto-matching
- `base_branch`: Default branch (main, develop, etc.)
- `branch_pattern`: Template for feature branches with {username}, {ticket}, {description}
- `jira_project`: Jira project key
- `jira_statuses`: Optional override of live Jira statuses (when status read fails or permissions are missing). Maps workflow stages to status names. Skills fall back to reading statuses live from Jira when this is omitted.
- `task_files_dir`: Directory for task files (default tasks/)
- `summaries_dir`: Directory for summaries
- `forbidden`: Lists of forbidden paths and commands
- `workspace_root`: (Optional) For multi-repo workspaces, the root directory containing component repos. When set, `repos` paths are relative to this. When omitted, the workspace root is the directory holding `.claude/settings.local.json` that set `AI_SDLC_PROFILE`, or the nearest ancestor of cwd containing `.claude/settings.local.json`, or cwd.
- `repos`: (Optional) List of component repositories in a multi-repo workspace. Each entry contains:
  - `name`: Short identifier for the repo
  - `path`: Path relative to workspace_root
  - `remote`: Git remote URL
  - `owns`: One-line description of what this repo owns

## How the application works
One short paragraph on what the app does, its main components, and how data flows between them.

## How we build things here
Conventions the agent must follow: code style, layering, test expectations, commit and PR habits.

## Local testing flow
The exact commands to install, run, and test locally, and anything that must be running first.
