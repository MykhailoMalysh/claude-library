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
---

## How the application works
One short paragraph on what the app does, its main components, and how data flows between them.

## How we build things here
Conventions the agent must follow: code style, layering, test expectations, commit and PR habits.

## Local testing flow
The exact commands to install, run, and test locally, and anything that must be running first.
