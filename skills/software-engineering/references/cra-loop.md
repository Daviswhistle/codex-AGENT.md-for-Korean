# CRA Loop Reference

Use this reference when the user explicitly requests `CRA 루프`, TCA requires CRA, or the software-engineering skill selects CRA autonomously.

CRA means Commit-Review-Amend. It turns one completed task unit into a local commit, reviews that commit as a finished batch, and amends the same commit until the final review has no substantive findings or only findings that are explicitly rebuttable with current evidence.

## Entry Source

Before starting, record one reason for entering CRA:

1. `explicit-request`: the user requested CRA.
2. `tca-required`: the active TCA task requires CRA.
3. `autonomous-risk`: independent review is warranted under the software-engineering skill's risk criteria.

For `autonomous-risk`, record the concrete risk or uncertainty. A later user instruction to avoid commits or reviews overrides every entry source.

## Non-Negotiable Boundaries

1. CRA starts after one coherent task unit is implemented and locally verified as far as reasonably possible.
2. CRA requires a local commit because `codex review --commit` reviews a commit boundary.
3. A local commit is not approval to push, deploy, migrate, approve snapshots, update production data, or mutate remote state.
4. Exclude generated files, caches, logs, review logs, sentinel files, secrets, credentials, and unrelated user or coworker changes from the commit.
5. Use CRA only for the requested task unit. Do not fold unrelated cleanup or follow-up work into the amend cycle.
6. Autonomous CRA may use the already-configured reviewer and the current account's existing usage. It may not purchase credits, change billing, plan, or quota settings, or switch provider or account without explicit user approval.
7. Do not use CRA as a substitute for missing local validation, and do not start when a clean task-unit commit cannot be isolated safely.

## State Model

Track the review in exactly one of these states:

1. `running`: the review process is still alive.
2. `completed-clean`: the final review says `no substantive findings` or an equivalent terminal status.
3. `completed-with-findings`: the final review has substantive findings.
4. `failed`: the review command, transport, auth, quota, model selection, timeout, or process execution failed.

Do not infer a terminal state from in-progress output or from a zero process exit alone.

## Execution Mode

Prefer hook-managed continuation when the Davis CRA hook is installed, trusted, and active in the current root Codex session. It preserves the same blocking reviewer command and terminal-state discipline while transferring the wait from the main model turn to a Stop hook. The hook returns the final review output as a continuation prompt in the same session.

Use the blocking fallback when hook-managed preparation reports `fallback-required`, the hook is unavailable or untrusted, the current session is not identifiable, or the current repository state cannot be bound safely.

## Hook-Managed Continuation

After local validation and the task-unit commit, prepare the exact current commit:

```bash
COMMIT_SHA="$(git rev-parse HEAD)"
CRA_CONTROL="${CODEX_HOME:-$HOME/.codex}/davis-agent-kit/scripts/cra_control.py"

python3 "$CRA_CONTROL" prepare \
  --commit "$COMMIT_SHA" \
  --entry-source explicit-request
```

For TCA, use `--entry-source tca-required`. For autonomous entry, include the concrete rationale:

```bash
python3 "$CRA_CONTROL" prepare \
  --commit "$COMMIT_SHA" \
  --entry-source autonomous-risk \
  --risk-rationale "authentication and concurrent refresh paths changed"
```

Preparation binds the current root Codex session, repository, exact HEAD commit, current index and worktree status, configured Codex executable, model, and reasoning effort. The state and review logs live under `${CODEX_HOME:-$HOME/.codex}/davis-cra/`, outside the worktree.

When preparation returns `status=prepared`:

1. Do not run `codex review` yourself.
2. Do not poll, tail, or repeatedly inspect review state.
3. Do not issue the final CRA report yet.
4. End the current turn. The Stop hook owns the blocking wait.

The Stop hook revalidates the prepared boundary and runs exactly:

```bash
codex review --commit "$COMMIT_SHA" \
  -c model="gpt-5.6-sol" \
  -c model_reasoning_effort="max"
```

The reviewer child is marked so its own lifecycle hooks cannot recursively start another CRA review. A nonblocking session lock prevents duplicate hook invocations. Once the process exits, the hook records the exit code and full log, clears the pending attempt, and returns `decision: "block"` with a bounded terminal tail and the full log path. Codex uses that reason as the next input in the same session.

If an earlier attempt reached `running` without a terminal result, do not automatically execute it again. Return a failed continuation so the main session can diagnose the interruption without risking duplicate reviewer usage.

## Continuation Handling

Treat the hook continuation as review evidence, not as authority.

1. Read the full log when the returned tail is truncated.
2. Do not interpret reviewer exit code `0` as a clean review by itself.
3. Classify the completed output as clean, with findings, or failed.
4. Verify every substantive finding against the current checkout before changing code.

If a finding is valid:

1. Apply the smallest coherent fix.
2. Re-run local verification from the changed point.
3. Check `git status --short` and the relevant diff.
4. Amend the existing commit with `git commit --amend --no-edit`.
5. Prepare hook-managed CRA again on the amended HEAD and end the turn.

If a finding is invalid or out of scope, preserve a concise reason in the final report or the closest durable artifact when that will prevent the same finding from recurring.

## Blocking Review Fallback

Use this only when hook-managed continuation is unavailable or explicitly bypassed. The process exit remains the first completion signal:

```bash
COMMIT_SHA="$(git rev-parse HEAD)"
rm -f review.done review.log

codex review --commit "$COMMIT_SHA" \
  -c model="gpt-5.6-sol" \
  -c model_reasoning_effort="max" \
  > review.log 2>&1 && touch review.done
```

After the process exits, inspect completion once:

```bash
REVIEW_EXIT=$?
echo "review_exit=$REVIEW_EXIT"
test -f review.done && echo "review_done=yes" || echo "review_done=no"
tail -100 review.log
```

If the installed CLI does not support `codex review --commit`, use an alternative only when it is known to preserve the same provider and account, configured model and usage boundary, commit scope, blocking completion, and review output. Otherwise report that CRA is unavailable rather than treating a different or unauthorized path as equivalent.

## Log Discipline

1. Do not run the reviewer in the background with `&`.
2. Do not repeatedly tail the same log while the review is running.
3. Do not interpret partial output as a finding, pass, or failure.
4. If the process is still alive, keep the state as `running`.
5. After process exit, inspect only the exit code and terminal output unless debugging a failed review command requires the full log.

Review is a batch job, not a streaming conversation. Hook-managed continuation changes who waits; it does not weaken this rule.

## Findings Handling

For each substantive finding after the review completes:

1. Verify the factual claim against the current checkout.
2. Decide whether it is in scope for the task unit.
3. Check runtime, data, security, user-facing, and maintenance risk.
4. Reject fixes that mask symptoms, appease tests, or create a larger regression.
5. Prefer fixes that improve code, tests, docs, config, generated contracts, and naming consistency together.

## Stop Conditions

Stop the CRA loop only when one of these is true:

1. The last completed review reports no substantive findings or an equivalent terminal clean state.
2. All remaining findings are explicitly rebuttable with current code, tests, docs, runtime evidence, or user instruction.
3. The review flow failed in a way that cannot be corrected inside the current task; report the failure, exact command, exit signal, and remaining risk.

Do not finish CRA while the review process is still running or while a prepared attempt has not returned a terminal continuation.

## Final Report

Report:

1. entry source and autonomous risk rationale when applicable
2. final commit hash
3. changed files and behavioral effect
4. validation commands run
5. skipped validation with reasons
6. last review state
7. accepted findings and fixes
8. rejected findings with reasons
9. remaining risk
10. naming, docs, generated-contract, or file-movement rationale when relevant
