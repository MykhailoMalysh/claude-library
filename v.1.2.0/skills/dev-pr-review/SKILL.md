---
name: dev-pr-review
description: Review a pull/merge request (your own branch or a teammate's MR) against how this project's application works and how things are built here, using the project profile. Picks a review level (quick for small diffs, standard by default, full on request or when dependencies change), orchestrates specialist finders, verifies every finding against the code, routes failures to an error-handler agent, and returns one shareable review block. Nothing is posted anywhere unless the developer explicitly asks. Use when the developer says "review this PR/MR", "review the diff", "check this branch", "review MR !52", "grill this PR", or invokes /dev-pr-review, even if they only name a branch or MR number.
role: planning
compatibility:
  required_tools:
    - Bash
    - Read
    - Agent
---

# dev-pr-review (v4 orchestrator)

You are the **orchestrator**. Specialist agents in `${CLAUDE_PLUGIN_ROOT}/agents/` do the finding and verifying. Your job is to:

- build a shared context that includes how this project works,
- pick the review level and the agents that run,
- route every failure through the `error-handler` agent,
- merge, rank, and present one shareable review.

You run in the main conversation on purpose: only the main thread can reliably dispatch sub-agents and talk to the developer mid-run.

**Read-only by default.** A review prepares comments. Don't modify the code under review. Don't post to GitLab, ADO, or Jira unless the developer explicitly asks after seeing the review (Phase 4).

The format for everything agents send back is in `${CLAUDE_PLUGIN_ROOT}/references/agent-contract.md`. Read it once at the start of the run; you need it to parse results and to assign orchestrator-side error codes.

The review is the same whether the branch is the developer's own or a teammate's MR: one block written for the author, ready to share.

---

## Agents

| Agent (`subagent_type`) | Role | Level |
|---|---|---|
| `ai-sdlc:review-correctness` | Line-by-line bugs in changed code | standard, full |
| `ai-sdlc:review-business-logic` | Requirements, domain invariants, and project fit | standard, full |
| `ai-sdlc:review-security` | Injection, traversal, authz, data exposure | standard, full |
| `ai-sdlc:review-removed-behavior` | Invariants dropped by deleted lines; reverted fixes | full |
| `ai-sdlc:review-cross-file` | Callers and consumers broken by the change | full, or added when dependencies change (Phase 0e) |
| `ai-sdlc:review-simplification` | Duplication, dead code, project helpers not reused | full |
| `ai-sdlc:review-conventions` | Written and profile conventions; commit/branch naming | full |
| `ai-sdlc:griller` | Design challenge of the PR as a whole | on request |
| `ai-sdlc:verifier` | Confirms or refutes candidate findings | always |
| `ai-sdlc:error-handler` | Plans recovery for any non-OK agent status | on every non-OK status |

### Review levels

| Level | When | Who reviews |
|---|---|---|
| **quick** | ≤ 50 changed lines and ≤ 3 files (from `git diff --numstat`), unless the developer asks for more | You review the diff directly against the profile, then one `verifier` checks your candidates. No finder fan-out. |
| **standard** | Default | `review-correctness`, `review-business-logic` (project fit), `review-security` |
| **full** | "Full", "thorough", "all angles", or the diff changes dependencies | All seven finders. Add `griller` when asked ("grill", "challenge the design", "poke holes"). |

Adjusting from the request:
- Named extras ("also check cross-file impact", "add conventions") → the level's finders plus those.
- "Only security", "just correctness" → exactly those finders.
- "Grill" at any level → add `griller`.
- Dependencies changed (Phase 0e) → add `review-cross-file` even at standard level, so a swapped library is followed to its callers. If the developer asked for specific angles only, respect that: don't add it, and say in the announcement that dependencies changed and cross-file is available. A dependency change also moves a small diff off the quick path, because a one-line manifest change can break callers the diff never shows.

Before dispatching, say in one line which level and angles you're running, and why if you chose them yourself ("standard + cross-file: dependencies changed"), so the developer can redirect you.

---

## Phase 0: Build the review context

**0a. Refs.** Don't assume `master`. Find the merge target:
1. The base the developer named, if any.
2. The MR's `target_branch` (Phase 0b), if an MR was named.
3. Otherwise `git symbolic-ref refs/remotes/origin/HEAD`, stripped to `origin/<name>`.
4. Otherwise the first existing ref among `origin/develop`, `origin/main`, `origin/master`.

**0b. Which branch is under review.** Always refresh the base first, also for the developer's own branch, so the diff is against the current target:

```bash
git fetch origin <base-branch> -q
```

If the developer named an MR or a branch that isn't the current checkout, also fetch it (`git fetch origin <source_branch> -q`) and offer a temporary worktree so agents can read files at the right version:

```bash
git worktree add --detach /tmp/review-<iid-or-branch> origin/<source_branch>
```

- Accepted → set `repo` to the worktree path and `head_ref: HEAD`. Remove it at the end of the run with `git worktree remove /tmp/review-<...>`.
- Declined → keep `repo` as is, set `head_ref: origin/<source_branch>`, and put this line in `notes`: "Use base_ref and head_ref, not HEAD: the branch under review is not checked out. Read files with `git show <head_ref>:<path>`."

Then capture:
```bash
git merge-base <base> <head>
git log --oneline <base>..<head>
git diff --shortstat <base>...<head>
git diff --numstat <base>...<head>
```
If the diff is empty, stop and tell the developer the branch has no changes against `<base>`.

**0c. Requirements.** Gather what the change is supposed to do from every source that's cheap to reach:
- **Jira.** Credentials come from the process environment (`JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`; see Configuration in `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`). Take the key from the branch name, or a key or URL the developer gave, and run `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py get --key <KEY>`. Pass the result wrapped in `<ticket>`.
- **GitLab MR (read-only).** If the developer gave an MR number and `GITLAB_URL` and `GITLAB_TOKEN` are set: `python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_gitlab.py mr-get --iid <N>`. It returns title, description, and source/target branches. Pass the description wrapped in `<mr_description>`. Reading changes nothing, so no confirmation is needed.
- **Spec or design docs in the diff** (`docs/**`, `*spec*`, `*design*`, ADRs). Pass their paths; agents read them directly.

A missing variable only removes that source; name it with the `settings.local.json` line to add in the closing "Not checked locally" line. Never open `.env` files and never print credential values.

If every source is thin (for example, a one-line ticket with no description), say so and ask the developer once for requirements. If they have nothing more, proceed; `review-business-logic` still checks invariants and project fit and reports the gap.

**0d. Project profile.** Load the two sections that make the review about this project rather than generic best practice:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show --section "How the application works"
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_profile.py show --section "How we build things here"
```
Pass each in the context block wrapped in `<profile section="...">`. With no profile (`{"profile": null, ...}`) or an empty section, review generically, say so in one line of `notes`, and add one line to the end of the review suggesting `/dev-profile-init`. A missing profile never stops the run.

**0e. Dependency changes.** A change that swaps or upgrades a library can break callers without touching them, so check before choosing the level:
```bash
git diff --name-only <base>...<head> | grep -E '(^|/)(requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|Pipfile(\.lock)?|package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|go\.(mod|sum)|Cargo\.(toml|lock)|pom\.xml|build\.gradle(\.kts)?|Gemfile(\.lock)?|composer\.(json|lock))$'
```
If anything matches:
1. Add `review-cross-file` (see "Adjusting from the request").
2. Put one line in `notes` naming the packages added and removed, read from the manifest diff, so finders know which call sites to compare.
3. When it's cheap, check whether the added packages are installed in the repo's environment (for Python, `pip show <name>`). Don't install them. If they aren't installed, claims about the new library rest on reading code; report that under "Not checked locally".
4. Optional runtime check, only if the developer wants it. Ask once: "Dependencies changed. If you have an environment with the old or the new version, give me its interpreter path and the verifiers can run read-only comparisons against it. Say skip if not." Pass answers in `notes` as `old_env:` and `new_env:`. Never create environments or install packages yourself.

If nothing matches, skip this step silently.

**0f. Context block.** Assemble it as the contract describes: `repo`, `base_ref`, `head_ref`, `merge_base`, `diff_command`, `changed_files`, `requirements` (with `<ticket>` / `<mr_description>`), `profile` (the `<profile>` sections), `notes`, `contract` (absolute path). Every agent gets the same block. Pass refs and paths, never the diff itself: large diffs get truncated in prompts, and agents read more carefully per file.

---

## Phase 1: Find

**Quick level.** Read the diff yourself (`git diff <base>...<head>`) and the enclosing functions, with the profile in mind: correctness, project fit, security, and anything the deleted lines stop doing. Write up to 6 candidates in the `findings` shape, then go to Phase 2c with them as one verifier batch.

**Standard and full levels.** Dispatch every selected finder (and `griller`, if requested) in a single message so they run in parallel. Each prompt is the context block plus: "Review this change from your angle and return findings per the contract." Add angle-specific notes only when you have them (for example, tell `review-removed-behavior` "the branch was rebased; check whether recent base-branch fixes survived").

While finders run, post one short line as each result lands: the angle and its most serious candidate. Skip notes that carry nothing new.

For each result, parse the final `status` block and the payload block (`findings` or `report`):
- `ok` with a non-empty `evidence` list and a parseable payload → keep the payload.
- Anything else → Phase 1b.

### Phase 1b: Error handling

Every non-OK result goes to `ai-sdlc:error-handler`, including failures that look obvious. First assign orchestrator-side codes yourself:
- No status block, invalid JSON, an unparseable payload, a `status: ok` block without `evidence`, or a `verdicts` block missing from a verifier reply → `MALFORMED_OUTPUT`.
- The `ai-sdlc:<name>` agent type isn't recognised → `AGENT_TYPE_UNAVAILABLE`.
- The agent errored, was stopped, or returned nothing → `AGENT_CRASHED`.

A verifier that answers in prose without a `verdicts` block is `MALFORMED_OUTPUT`, never a result: don't read verdicts out of its prose yourself.

Dispatch the error handler with `step` (agent name and level), `attempt` (1 on first failure), `status_block`, `payload_excerpt` (first ~40 lines), `original_task`, and the context block. Failures from different agents can be handled in parallel. Apply the handler's `decision`:

| Action | You do |
|---|---|
| `retry` | Re-dispatch the same task. The step's attempt count becomes 2. |
| `retry_modified` | Re-dispatch `modified_task`. Attempt becomes 2. |
| `use_fallback_agent` | Dispatch `general-purpose` with the body of `${CLAUDE_PLUGIN_ROOT}/agents/<name>.md` (without frontmatter) prepended to the task. Attempt becomes 2. |
| `accept_partial` | Keep the payload. Record `coverage_note`. Verdicts marked `severity_unverified: true` count as unverified (Phase 2c). |
| `skip` | Drop the step. Record `coverage_note`. |
| `ask_user` | Show the diagnosis and `user_question`, then wait. Continue with the developer's answer. |
| `abort` | Stop the run and report the reason. |

**Budget: one retry per step.** If a retried step fails again, call the error handler with `attempt: 2`. It is told not to retry then; if it says to retry anyway, treat that as `ask_user`. The budget keeps recovery from looping.

The error handler can't grant anything you couldn't do yourself. If a decision implies installing software, changing credentials, editing config, or posting remotely, ask the developer instead.

---

## Phase 2: Merge and verify

**2a. Merge.** Merge candidates that describe the same defect: same file and nearby line, or the same root cause seen from two angles. Keep the clearest wording. Agreement across angles is a signal.

**2b. Select.** If there are more than ~16 candidates, pick the 16 most likely to matter: data loss, security, broken access, and broken core flows first. Mention the rest under "Not checked locally" instead of silently dropping them.

**2c. Verify.** Split the selected candidates into batches of 2 (quick level: one batch with all of yours). Dispatch one `ai-sdlc:verifier` per batch, all in one message. Give each candidate an `id`, the claim, the file:line, the failure scenario, and its `type`. Verifier failures go through Phase 1b.

- Keep `CONFIRMED` and `PLAUSIBLE`.
- Drop `REFUTED` from the comments; list each in the closing "Checked and fine" line.
- Use the verifier's `anchor_file:anchor_line` instead of the finder's line; finders drift.
- A verdict with `severity_unverified: true` was transcribed from prose by the error handler. Treat its candidate as unverified: re-verify it in the next batch if budget allows, otherwise report it as a `suggestion` at most, with `*(from reading the code)*`, never as blocking.

Never present an unverified finding as a confirmed issue. If the verifiers can't run at all, every comment carries `*(from reading the code)*` and the Verdict line says the review is unverified.

---

## Phase 3: Present

Turn each surviving finding into one author-facing comment.

**Label** (how much it matters):
- `blocking`: data loss or leak, security hole, broken core flow, or a requirement not met. The MR shouldn't merge as is.
- `suggestion`: wrong behavior in reachable edge cases, a clear departure from how this project does things, real maintenance cost.
- `nit`: small cleanup the author can take or leave.

**Type** (what kind of problem): `bug` (wrong behavior), `project fit` (works, but not how this application or codebase does it), `refactor` (structure, duplication, reuse), `quality` (tests, naming, readability, tooling).

Use the finder's `type` when it set one; adjust it if the verifier's reason shows otherwise. A project-fit comment states the profile pattern in plain words ("Elsewhere this service reads config through `Settings`, not `os.environ`"), so the author sees the rule without needing the profile.

Output exactly one block, the same for the developer's own branch and a teammate's MR:

```
## Review: <ref> <head> → <base>

Verdict: <Approve | Approve with comments | Request changes> — <N> blocking, <N> suggestions, <N> nits

---
📍 1 · path/to/file.py:42
**blocking · bug** — What is wrong and why it matters for this application. *(verified: ran the failing case against the new code)*
Fix: what to change, when it's clear.

---
📍 2 · path/to/other.py:10
**suggestion · project fit** — What differs from how this project does it, and the pattern it should follow. *(from reading the code)*

---
Checked and fine: <refuted claims, one short phrase each>. Not checked locally: <coverage gaps>.
```

Rules for the block:
- `<ref>` is the MR (`!52`) or branch name; `<head>` and `<base>` are short SHAs or branch names.
- Verdict: `Request changes` if any comment is blocking; `Approve with comments` if there are only suggestions or nits; `Approve` if there are none.
- Order comments blocking → suggestion → nit; within a label, most serious first. Show up to 10 comments; fold the rest into one line at the end listing `path:line` and a few words each.
- `*(verified: <how>)*` comes from the verifier's reason (what was read or run); use `*(from reading the code)*` when the verdict is `PLAUSIBLE` because nothing was run, or the finding is unverified.
- Number comments 1, 2, 3 in display order in the `📍` line, so the developer can refer to them ("post comments 1 and 3").
- `Fix:` only when the fix is clear. Drop `:line` from `📍` when the finding has no single line.
- Closing line: `Checked and fine:` lists refuted claims; `Not checked locally:` lists every coverage note, skipped or failed angle, unverified candidate, uninstalled dependency, and missing credential. Omit a half that would be empty.
- If `griller` ran, add its critical gaps and important questions as `suggestion · quality` comments phrased as questions to the author, anchored on the most relevant file.
- Neutral wording addressed to the author: describe the code, not the person. No internal severity codes, agent names, angle names, or verdict words (CONFIRMED, PLAUSIBLE).
- With no profile, add one line after the block: "No project profile found, so this review uses generic checks. Run /dev-profile-init to make it project-aware."

If nothing survives verification, the block is the header, `Verdict: Approve — no issues found`, and the closing line.

---

## Phase 4: Act only on request

After the review, stop. Offer follow-ups, but do nothing unprompted. Only when the developer explicitly asks (for example, "post comments 1 and 3", using the numbers in the `📍` lines):

**Post to GitLab.** When the remote host is GitLab. Needs `GITLAB_URL` and `GITLAB_TOKEN`; `GITLAB_PROJECT` is optional and otherwise derived from the remote. Walk the comments the developer named one at a time: show the comment, ask "Post this to MR !<iid>?", and accept yes, no, or edited text. For each approved one, write the comment text (without the `📍` line) to `/tmp/mr-comment-<n>.md` and run:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_gitlab.py note --iid <N> --content-file /tmp/mr-comment-<n>.md [--file <path> --line <N>]
```
With `--file` and `--line` it posts an inline discussion on the diff; without them, a general note. Report `NOTE_ID=` or the error for each, then summarise how many were posted and skipped.

**Post to Azure DevOps.** When the remote is ADO. Same one-at-a-time walk. Find the PR with `cli_pr.py check --source <branch>`, then post with `cli_comment.py post`.

**Anything else that changes remote state** (approving, setting labels, commenting on the Jira ticket): confirm the exact action first, every time.

If credentials for the requested action are missing, name the variable, show the `settings.local.json` line to add, and stop. Don't fall back to another platform.

---

## Why it's built this way

- **The profile is the reviewer's knowledge of the project.** Generic best practice misses what matters here; the "How the application works" and "How we build things here" sections let finders say "this isn't how this project does it" and cite why.
- **Levels by size and risk.** A 20-line change doesn't need seven agents; a dependency swap needs the one that follows callers.
- **Finders find, verifiers verify.** Finders don't re-check their own work; a separate verifier does, and its `verdicts` block is required so severity always rests on a real check.
- **An error handler on every failure.** The one-retry cap and the hard limits keep recovery from looping or quietly working around a missing credential.
- **One shareable block.** The same output works for self-review and for a teammate, and comments can be posted as they are.
- **No posting by default.** The developer owns what lands on a PR.

## Integration with other skills

- **`/dev-grill-me`** uses the same `griller` agent for plans before code exists. Here it grills the design of finished code.
- **`/dev-pr-address-comments`** is the author-side counterpart: it works through review comments already on a PR.
- **`/dev-profile-init`** creates the profile this review reads.
