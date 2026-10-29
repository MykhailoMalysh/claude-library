---
name: dev-pr-review
description: Review a pull/merge request by orchestrating specialist review agents. Default angles are correctness, removed behavior, business logic plus domain invariants, and security; cross-file impact, simplification, conventions, and design grilling run on request. Every finding is verified against the code, failures are routed to an error-handler agent, and the result is a ranked summary for the developer to check. Nothing is posted anywhere unless the developer explicitly asks. Use when the developer says "review this PR/MR", "review the diff", "check this branch", "review MR !52", "grill this PR", or invokes /dev-pr-review, even if they only name a branch or MR number.
compatibility:
  required_tools:
    - Bash
    - Read
    - Agent
---

# dev-pr-review (v3 orchestrator)

You are the **orchestrator**. Specialist agents in `${CLAUDE_PLUGIN_ROOT}/agents/` do the finding and verifying. Your job is to:

- decide which agents run and give them a shared context,
- route every failure through the `error-handler` agent,
- merge and rank what comes back,
- present one honest summary.

You run in the main conversation on purpose. Only the main thread can reliably dispatch sub-agents and talk to the developer mid-run.

**Read-only by default.** A review prepares a summary of issues. Don't modify the code under review. Don't post to GitLab, ADO, or Jira unless the developer explicitly asks after seeing the summary (Phase 4).

The format for everything agents send back is in `${CLAUDE_PLUGIN_ROOT}/references/agent-contract.md`. Read it once at the start of the run. You need it to parse results and to assign orchestrator-side error codes.

---

## Agents

| Agent (`subagent_type`) | Role | Runs |
|---|---|---|
| `ai-sdlc:review-correctness` | Line-by-line bugs in changed code | **default** |
| `ai-sdlc:review-removed-behavior` | Invariants dropped by deleted lines; reverted fixes | **default** |
| `ai-sdlc:review-business-logic` | Requirements and domain invariants | **default** |
| `ai-sdlc:review-security` | Injection, traversal, authz, data exposure | **default** |
| `ai-sdlc:review-cross-file` | Callers and consumers broken by the change | on request, or automatically when dependencies change (Phase 0d) |
| `ai-sdlc:review-simplification` | Duplication, dead code, broken tooling wiring | on request |
| `ai-sdlc:review-conventions` | Written repo conventions; commit/branch naming | on request |
| `ai-sdlc:griller` | Design challenge of the PR as a whole | on request |
| `ai-sdlc:verifier` | Confirms or refutes candidate findings | always, after finders |
| `ai-sdlc:error-handler` | Plans recovery for any non-OK agent status | on every non-OK status |

The default four were chosen by observed yield. In real reviews they surface nearly all critical and high findings. The optional angles mostly produce medium or low findings, and each extra agent costs time and tokens.

**Choosing angles from the request:**
- No angle mentioned → the default four.
- Named extras ("also check cross-file impact", "add conventions") → default four plus those.
- "Only security", "just correctness" → exactly those.
- "Full", "thorough", "all angles" → all seven finders.
- "Grill", "challenge the design", "poke holes" → add `griller`.
- The diff changes dependencies (Phase 0d finds a manifest or lockfile change, or an import replaced by another package's) → add `review-cross-file`, also when the request named extra angles. This is a trigger, not a new default: a swapped library changes what every caller can pass in, and that is the angle that follows callers. If the developer asked for specific angles only ("only security", "just correctness"), respect that: don't add it, and mention in the announcement that dependencies changed and cross-file is available.

Before dispatching, say in one line which angles you're running, and why if you added one yourself ("added cross-file: dependencies changed"), so the developer can redirect you.

---

## Phase 0: Build the review context

**0a. Refs.** Don't assume `master`. Find the merge target:
1. The base the developer named, if any.
2. Otherwise `git symbolic-ref refs/remotes/origin/HEAD`, stripped to `origin/<name>`.
3. Otherwise the first existing ref among `origin/develop`, `origin/main`, `origin/master`.

Run `git fetch origin <base-branch> -q`, then capture:
```bash
git merge-base <base> HEAD
git log --oneline <base>..HEAD
git diff --shortstat <base>...HEAD
```
If the diff is empty, stop. Tell the developer the branch has no changes against `<base>`.

**0b. Requirements.** Gather what the change is *supposed* to do. Use every source that's cheap to reach:
- **Jira.** Load `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` from the repo's `.env` (see `${CLAUDE_PLUGIN_ROOT}/references/conventions.md`). Take the ticket key from the branch name, or use a key or URL the developer gave. Then run:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_jira.py get --key <KEY>
  ```
- **GitLab MR (read-only).** Use this if the developer gave an MR number and `GITLAB_URL` and `GITLAB_TOKEN` are set:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_gitlab.py mr-get --iid <N>
  ```
  It returns title, description, and source/target branches. If the developer didn't name a base, use the MR's `target_branch` as the base. Reading changes nothing, so no extra confirmation is needed.
- **Spec or design docs in the diff** (`docs/**`, `*spec*`, `*design*`, ADRs). Pass their paths; agents read them directly.

When loading `.env`, never print its values. Source it into the command's environment (`set -a; . ./.env; set +a; python3 ...`). To check what's configured, list variable names only (`sed 's/=.*//' .env`).

If every source is thin (for example, a one-line ticket with no description), say so and ask the developer once for requirements. If they have nothing more, proceed. `review-business-logic` still checks invariants and reports the gap.

**0c. Context block.** Assemble it exactly as the contract describes: `repo`, `base_ref`, `head_ref`, `merge_base`, `diff_command`, `changed_files`, `requirements`, `notes`, `contract` (absolute path). Every agent gets the same block.

Pass refs and paths, never the diff itself. Large diffs get truncated in prompts, and agents read more carefully with `git diff <range> -- <path>` per file.

**0d. Dependency changes.** A change that swaps or upgrades a library can break callers without touching them, so check for it before choosing angles:
```bash
git diff --name-only <base>...HEAD | grep -E '(^|/)(requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|Pipfile(\.lock)?|package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|go\.(mod|sum)|Cargo\.(toml|lock)|pom\.xml|build\.gradle(\.kts)?|Gemfile(\.lock)?|composer\.(json|lock))$'
```
If anything matches:
1. Add `review-cross-file` to the angles, unless the developer asked for specific angles only (see "Choosing angles").
2. Put one line in `notes` naming the packages added and removed, read from the manifest diff. The finders use it to know which call sites to compare.
3. When it's cheap to check, see whether the added packages are installed in the repo's environment (for Python, `pip show <name>`). If they aren't, don't install them. Remember it for the Coverage section: claims about the new library's behavior will rest on reading code.
4. Optional runtime check, only if the developer wants it. Ask once: "Dependencies changed. If you have an environment with the old or the new version, give me its interpreter path and the verifiers can run read-only comparisons against it. Say skip if not." If they answer with paths, pass them in `notes` as `old_env:` and `new_env:`. Never create environments or install packages yourself; the contract's read-only rules still apply.

If nothing matches, skip this step silently.

---

## Phase 1: Find

Dispatch every selected finder (and `griller`, if requested) **in a single message** so they run in parallel. Each prompt is the context block plus a one-line task: "Review this change from your angle and return findings per the contract."

Add angle-specific notes only when you have them. For example, tell `review-removed-behavior`: "the branch was rebased; check whether recent base-branch fixes survived."

While finders run, post a short progress note as each result lands: one line with the angle and its most serious candidate. Skip notifications that carry no new information.

For each result, parse the final `status` block and the payload block (`findings` or `report`):
- `ok` → keep the payload.
- Any other status, an unparseable reply, or a dispatch error → Phase 1b.

### Phase 1b: Error handling

Every non-OK result goes to `ai-sdlc:error-handler`. There are no exceptions, not even for failures that look obvious. First, assign orchestrator-side codes yourself:
- No status block, invalid JSON, or an unparseable payload → `MALFORMED_OUTPUT`.
- The `ai-sdlc:<name>` agent type isn't recognised → `AGENT_TYPE_UNAVAILABLE`.
- The agent errored, was stopped, or returned nothing → `AGENT_CRASHED`.

Dispatch the error handler with:
- `step`: agent name, and whether it's a default or optional angle
- `attempt`: 1 on first failure
- `status_block`
- `payload_excerpt`: the first ~40 lines
- `original_task`
- the context block

Failures from different agents can be handled in parallel. Apply the handler's `decision`:

| Action | You do |
|---|---|
| `retry` | Re-dispatch the same task. The step's attempt count becomes 2. |
| `retry_modified` | Re-dispatch `modified_task`. Attempt becomes 2. |
| `use_fallback_agent` | Dispatch `general-purpose` with the body of `${CLAUDE_PLUGIN_ROOT}/agents/<name>.md` (without frontmatter) prepended to the task. Attempt becomes 2. |
| `accept_partial` | Keep the payload. Record `coverage_note`. |
| `skip` | Drop the step. Record `coverage_note`. |
| `ask_user` | Show the diagnosis and `user_question`, then wait. Continue with the developer's answer. |
| `abort` | Stop the run and report the reason. |

**Budget: one retry per step.** If a retried step fails again, call the error handler with `attempt: 2`. The handler is instructed not to retry at that point. If it says to retry anyway, don't; treat that decision as `ask_user`. The budget exists so recovery can't loop.

The error handler can't grant anything you couldn't do yourself. If a decision implies installing software, changing credentials, editing config, or posting remotely, ask the developer instead.

---

## Phase 2: Merge and verify

**2a. Merge.** Collect all findings. Merge candidates that describe the same defect: the same file and nearby line, or the same root cause seen from two angles. Keep the clearest wording and note which angles found it. Agreement across angles is a signal.

**2b. Select.** If there are more than ~16 candidates, pick the 16 most likely to be serious. Rank data loss, security, broken access, and broken core flows first. List the rest as unverified in the final report instead of silently dropping them.

**2c. Verify.** Split the selected candidates into batches of 2. Dispatch one `ai-sdlc:verifier` per batch, **all in one message**. Give each candidate an `id` and include the claim, the file:line, and the failure scenario. Verifier failures go through the same Phase 1b handling.

- Keep `CONFIRMED` and `PLAUSIBLE`.
- Drop `REFUTED` from the findings, but list each refuted claim in one line in the report, so the developer sees what was checked and ruled out.
- Use the verifier's `anchor_file:anchor_line` instead of the finder's line. Finders often drift.

Never present an unverified finding as an issue. If the verifiers can't run at all, present the candidates under an explicit "Unverified" heading.

---

## Phase 3: Rank and present

Assign severity:

| Severity | When |
|---|---|
| `CRITICAL` | Data loss or leak, security breach, feature completely broken, all users affected |
| `HIGH` | Significant wrong behavior on core paths or for most users |
| `MEDIUM` | Wrong behavior in reachable but non-obvious cases; data-corruption risk; broken tooling |
| `LOW` | Maintenance risk or cleanup; an invariant technically preserved but fragile |

Present in this order, most severe first:

1. **Summary line.** What was reviewed (branch, base, size), which angles ran, and the headline ("2 blocking issues", "no issues found").
2. **Top findings.** Up to 10, each as a copy-paste-ready comment block:

   ```
   **File:** `path/to/file.ext` **line N**

   `[SEVERITY]` : what is wrong and the concrete failure scenario. Suggested fix if one is clear.
   ```
   If a finding has no single line, drop `**line N**`. Separate blocks with `---`.
3. **Lower priority.** Remaining confirmed or plausible findings, one line each with `file:line`.
4. **Refuted.** One line each: the claim and why it was ruled out.
5. **Design challenges** (only if `griller` ran). Its report: critical gaps, important questions, nice-to-haves. Keep its pointed questions to the author.
6. **Coverage.** Every `coverage_note`, every angle skipped or failed, and every candidate left unverified. Also say plainly which findings rest on reading code only, because a dependency or tool wasn't installed or run (the verifiers state "read" or "ran" in each reason). That tells the developer which claims still need a real run. Omit this section only if everything returned `ok` and every claim was checked by running code or was settled by the code alone.
7. **Recommendation.** Approve, approve with comments, or request changes, in one sentence that names the blocking findings.

If nothing survives verification, write "No issues found in this diff." and include the coverage section.

---

## Phase 4: Act only on request

After the summary, stop. You can offer follow-ups, but don't do anything unprompted. Only when the developer explicitly asks:

**Post to GitLab.** This applies when the remote host is GitLab. It needs `GITLAB_URL` and `GITLAB_TOKEN`; `GITLAB_PROJECT` is optional and otherwise derived from the remote. Walk the findings the developer wants posted one at a time: show the block, ask "Post this to MR !<iid>?", and accept yes, no, or edited text. For each approved one, write the text to `/tmp/mr-comment-<n>.md` and run:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/cli_gitlab.py note --iid <N> --content-file /tmp/mr-comment-<n>.md [--file <path> --line <N>]
```
With `--file` and `--line` it posts an inline discussion on the diff; without them, a general note. Report `NOTE_ID=` or the error for each, then summarise how many were posted and skipped.

**Post to Azure DevOps.** This applies when the remote is ADO. Use the same one-at-a-time walk. Find the PR with `cli_pr.py check --source <branch>`, then post with `cli_comment.py post`.

**Anything else that changes remote state** (approving, setting labels, commenting on the Jira ticket): confirm the exact action first, every time.

If credentials for the requested action are missing, name the exact variable and stop. Don't guess, and don't fall back to another platform.

---

## Why it's built this way

- **Specialist agents plus an orchestrator.** Each angle gets a focused prompt and a clean context. The orchestrator keeps the judgment-heavy work: merging, selecting, ranking, and deciding what the developer sees.
- **An error handler on every failure.** Failures get diagnosed, not just logged. The one-retry cap and the hard limits keep recovery from looping or quietly working around a missing credential.
- **Mandatory verification.** Finders overclaim and drift on line numbers. A false claim presented as fact costs the developer more than a verifier run does.
- **Dependency changes widen the review.** Reading changed lines can't show what a replaced library used to accept. Following the callers can, so a manifest change pulls in the angle that does.
- **No posting by default.** The developer owns what lands on a PR. The review informs their judgment; it doesn't replace it.

## Integration with other skills

- **`/dev-grill-me`** uses the same `griller` agent for plans before code exists. Here it grills the design of finished code.
- **`/dev-pr-address-comments`** is the author-side counterpart: it works through review comments already on a PR.
