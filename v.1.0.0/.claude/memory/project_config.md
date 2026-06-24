# Project Config

Configuration read by the task lifecycle skills (`start-task`, `plan-task`, `implement-task`,
`finish-pr`) and the board scripts (`start_pr.py`, `finish_pr.py`).

## Required fields

```
ISSUES_REPO: owner/repo
```
The GitHub repo where issues, sub-issues, and the Projects board live.
Example: `myorg/my-project`

```
BOARD_NUMBER: <number>
```
The GitHub Projects (v2) board number attached to ISSUES_REPO.
Find it in the board URL: `github.com/orgs/<org>/projects/<number>`.

## Optional fields

```
CODE_REPO: owner/repo
```
The GitHub repo where feature branches are created. Defaults to `ISSUES_REPO` when absent —
use this only when the board and the code live in separate repos.
Example: `myorg/my-service`

---

<!-- Copy this block and fill in your values: -->
<!--
ISSUES_REPO: <owner/repo>
BOARD_NUMBER: <number>
CODE_REPO: <owner/repo>   (optional — omit if same as ISSUES_REPO)
-->
