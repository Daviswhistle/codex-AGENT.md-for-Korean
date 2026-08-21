# CRA Loop Reference

Use this reference when the user explicitly requests `CRA 루프`, TCA requires CRA, or the software-engineering skill selects CRA autonomously.

CRA means Commit-Review-Amend. It turns one completed task unit into one local commit, reviews that commit as a finished batch, and amends the same commit until the final review has no substantive findings or every remaining finding is explicitly rebuttable with current evidence.

The preferred implementation is the runtime CRA gate in `scripts/cra_gate.py`: a trusted Codex Stop hook launches an independent `codex exec review` thread and returns findings to the implementing agent as continuation feedback. This is stronger than relying on the implementing agent to remember every loop step, while keeping the reviewer isolated from the parent conversation.

## Entry Source

Before starting, record one reason for entering CRA:

1. `explicit-request`: the user requested CRA.
2. `tca-required`: the active TCA task requires CRA.
3. `autonomous-risk`: independent review is warranted under the software-engineering skill's risk criteria.

For `autonomous-risk`, record the concrete risk or uncertainty. A later user instruction to avoid commits or reviews overrides every entry source.

## Non-Negotiable Boundaries

1. CRA starts after one coherent task unit is implemented and locally verified as far as reasonably possible.
2. CRA requires a local commit because the reviewer inspects one exact commit boundary.
3. A local commit is not approval to push, deploy, migrate, approve snapshots, update production data, or mutate remote state.
4. Exclude generated files, caches, logs, CRA state, review output, sentinel files, secrets, credentials, and unrelated user or coworker changes from the commit.
5. Use CRA only for the requested task unit. Do not fold unrelated cleanup or follow-up work into the amend cycle.
6. Autonomous CRA may use the already-configured reviewer and the current account's existing usage. It may not purchase credits, change billing, plan, quota, provider, or account settings without explicit user approval.
7. Do not use CRA as a substitute for missing local validation, and do not arm it when a clean task-unit commit cannot be isolated safely.
8. Fixes stay in the same commit with `git commit --amend --no-edit`. A second task commit crosses the armed boundary and must be rejected.

## Preferred Runtime Gate

### One-Time Installation

Install the managed hooks from the kit checkout or installed kit path:

```bash
python3 scripts/cra_gate.py install-hook
```

The installer merges one `SessionStart` heartbeat and one `Stop` gate into `${CODEX_HOME:-$HOME/.codex}/hooks.json`, preserves unrelated hooks, and is idempotent. Codex requires the user to trust non-managed hooks. After installation or an update to the hook script:

1. review and trust the hook in Codex
2. start a new Codex session
3. verify configuration when needed with `python3 scripts/cra_gate.py doctor-hook`

The heartbeat is deliberate: `arm` refuses to rely on a hook that has merely been written to disk but has not actually executed in the current trusted Codex session.

### Arm One Commit

After implementation, local validation, and the task-unit commit:

```bash
CRA_GATE="${CODEX_HOME:-$HOME/.codex}/davis-agent-kit/scripts/cra_gate.py"
COMMIT_SHA="$(git rev-parse HEAD)"

python3 "$CRA_GATE" arm \
  --commit "$COMMIT_SHA" \
  --entry-source explicit-request
```

Use `--entry-source tca-required` for TCA. For autonomous entry, include the concrete rationale:

```bash
python3 "$CRA_GATE" arm \
  --commit "$COMMIT_SHA" \
  --entry-source autonomous-risk \
  --risk "security-sensitive parser boundary changed"
```

`arm` requires all of the following:

- the selected commit is the current `HEAD`
- the worktree is clean
- the commit is not a merge commit
- a trusted SessionStart heartbeat has run in this Codex session

Mutable state and review logs live under `${CODEX_HOME:-$HOME/.codex}/state/davis-agent-kit/cra`, outside the source repository.

### Stop-Gate Behavior

Once armed, prepare the normal final report and attempt to finish the turn. The Stop hook then owns completion:

1. It verifies that `HEAD` is still the armed commit boundary and the worktree is clean.
2. It launches a fresh blocking reviewer process:

   ```bash
   codex exec --ephemeral \
     -c model='"gpt-5.6-sol"' \
     -c model_reasoning_effort='"max"' \
     --output-last-message <state-output> \
     review --commit "$COMMIT_SHA"
   ```

3. A clean structured review allows the turn to end.
4. Substantive findings return `{"decision":"block","reason":"..."}`. Codex feeds the reason back to the same implementing agent.
5. The implementing agent verifies each claim, fixes valid in-scope issues, reruns affected validation, and amends the same commit.
6. The amended SHA is reviewed on the next Stop attempt.

The gate records the reviewed SHA. Repeated Stop attempts on an unchanged SHA with findings return the existing findings instead of spending another review. An amended SHA is reviewed again.

### Findings Handling

For each substantive finding:

1. Verify the factual claim against the current checkout.
2. Decide whether it is in scope for the task unit.
3. Check runtime, data, security, user-facing, and maintenance risk.
4. Reject fixes that mask symptoms, appease tests, or create a larger regression.
5. Prefer fixes that improve code, tests, docs, config, generated contracts, and naming consistency together.

For a valid finding:

```bash
# apply the smallest coherent fix
# rerun validation from the changed point
git status --short
git diff --check
git add <task-files>
git commit --amend --no-edit
```

Do not run `arm` again after a normal amend. The gate recognizes the new SHA only when it retains the original commit's parent boundary.

For findings that are all invalid or out of scope, preserve concrete evidence instead of changing code merely to satisfy the reviewer:

```bash
python3 "$CRA_GATE" rebut \
  --commit "$(git rev-parse HEAD)" \
  --reason "<specific code, test, documentation, runtime, or user-instruction evidence>"
```

A bare dismissal is not a rebuttal.

### Failure Semantics

Treat reviewer failure separately from findings.

- First failure on a SHA: block once with the exact failure and recovery checks.
- Second failure on the same SHA: fail open so a broken auth, quota, transport, model, or CLI path cannot trap the session indefinitely.
- Final report after fail-open: state that independent review did not complete and preserve the unresolved risk.

Inspect durable state with:

```bash
python3 "$CRA_GATE" status --json
```

Clear only a stale or deliberately abandoned gate, with a reason:

```bash
python3 "$CRA_GATE" clear --reason "<why CRA is being abandoned>"
```

## Why the Reviewer Is Not a Default Subagent

A reviewer subagent is not equivalent to an independent commit review unless its context policy is explicit. In the current multi-agent V2 interface, omitting `fork_turns` inherits all parent turns. A fresh reviewer therefore requires `fork_turns="none"`; older interfaces expose different controls.

Even with fresh context, a subagent remains coupled to the parent turn's multi-agent lifecycle and cannot by itself enforce the Stop condition. Use a subagent only as an optional additional perspective when all of these are true:

1. the installed Codex version is known to support the requested context policy
2. `fork_turns="none"` is explicit
3. the reviewer receives the task contract, exact commit SHA, and repository evidence it needs
4. its output does not replace the independent Stop-gate review

The primary CRA reviewer remains `codex exec review --commit`: it creates a separate review thread, consumes the exact commit boundary, produces structured output, and behaves consistently whether or not subagents are enabled.

## Blocking Fallback

Use the blocking fallback when any runtime-gate prerequisite is absent: the hook is not installed, not trusted, has no current-session heartbeat, the installed CLI lacks the required hook contract, or hook execution is otherwise uncertain.

```bash
COMMIT_SHA="$(git rev-parse HEAD)"
REVIEW_OUTPUT="$(mktemp)"

DAVIS_CRA_REVIEWER=1 codex exec --ephemeral \
  -c model='"gpt-5.6-sol"' \
  -c model_reasoning_effort='"max"' \
  --output-last-message "$REVIEW_OUTPUT" \
  review --commit "$COMMIT_SHA"
REVIEW_EXIT=$?

printf 'review_exit=%s\n' "$REVIEW_EXIT"
tail -100 "$REVIEW_OUTPUT"
rm -f "$REVIEW_OUTPUT"
```

This command remains blocking. Do not run it with `&`, repeatedly tail partial output, or infer a terminal state before process exit. Apply the same finding verification, amend, and re-review rules manually.

If the installed CLI does not support `codex exec review --commit`, use an alternative only when it is known to preserve the same provider and account, configured model and usage boundary, exact commit scope, blocking completion, and structured review output. Otherwise report that CRA is unavailable rather than treating a different path as equivalent.

## Stop Conditions

Stop CRA only when one of these is true:

1. The last completed review reports no substantive findings and marks the patch correct.
2. Every remaining finding is explicitly rebutted with current code, tests, docs, runtime evidence, or user instruction.
3. The review flow failed open after its bounded retry; report the exact failure and remaining risk.

Do not report a clean CRA result while the reviewer is running, after an invalid review payload, or after a reviewer failure.

## Final Report

Report:

1. entry source and autonomous risk rationale when applicable
2. final commit hash
3. changed files and behavioral effect
4. validation commands run
5. skipped validation with reasons
6. last CRA state
7. accepted findings and fixes
8. rejected findings with evidence
9. reviewer failure and fail-open status, if any
10. remaining risk
11. naming, docs, generated-contract, or file-movement rationale when relevant
