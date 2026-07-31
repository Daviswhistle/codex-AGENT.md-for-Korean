# CRA Loop Reference

Use this reference only when the user explicitly requests `CRA 루프`.

CRA means Commit-Review-Amend. It turns one completed task unit into a local commit, reviews that commit as a finished batch, and amends the same commit until the final review has no substantive findings or only findings that are explicitly rebuttable with current evidence.

## Non-Negotiable Boundaries

1. CRA starts after one coherent task unit is implemented and locally verified as far as reasonably possible.
2. CRA requires a local commit because `codex review --commit` reviews a commit boundary.
3. A local commit is not approval to push, deploy, migrate, approve snapshots, update production data, or mutate remote state.
4. Exclude generated files, caches, logs, review logs, sentinel files, secrets, credentials, and unrelated user or coworker changes from the commit.
5. Use CRA only for the requested task unit. Do not fold unrelated cleanup or follow-up work into the amend cycle.

## State Model

Track the review in exactly one of these states:

1. `running`: the review process is still alive.
2. `completed-clean`: the final review says `no substantive findings` or an equivalent terminal status.
3. `completed-with-findings`: the final review has substantive findings.
4. `failed`: the review command, transport, auth, quota, model selection, or process execution failed.

Do not infer a terminal state from in-progress output.

## Blocking Review Command

Use a blocking command so the process exit is the first completion signal:

```bash
COMMIT_SHA="$(git rev-parse HEAD)"
rm -f review.done review.log

codex review --commit "$COMMIT_SHA" \
  -c model="gpt-5.6-luna" \
  -c model_reasoning_effort="max" \
  -c service_tier="fast" \
  > review.log 2>&1 && touch review.done
```

After the process exits, inspect completion once:

```bash
REVIEW_EXIT=$?
echo "review_exit=$REVIEW_EXIT"
test -f review.done && echo "review_done=yes" || echo "review_done=no"
tail -100 review.log
```

If the installed CLI does not support `codex review --commit`, use the closest supported review flow, record the exact command or interactive path used, and preserve the completed review output. Do not treat an unavailable review command as a passed review.

## Log Discipline

1. Do not run the reviewer in the background with `&`.
2. Do not repeatedly tail the same log while the review is running.
3. Do not interpret partial output as a finding, pass, or failure.
4. If the process is still alive, keep the state as `running`.
5. After process exit, inspect only the exit code, optional sentinel, and the last 50-100 log lines unless debugging a failed review command requires more.

Review is a batch job, not a streaming conversation.

## Findings Handling

For each substantive finding after the review completes:

1. Verify the factual claim against the current checkout.
2. Decide whether it is in scope for the task unit.
3. Check runtime, data, security, user-facing, and maintenance risk.
4. Reject fixes that mask symptoms, appease tests, or create a larger regression.
5. Prefer fixes that improve code, tests, docs, config, generated contracts, and naming consistency together.

If a finding is valid:

1. Apply the smallest coherent fix.
2. Re-run local verification from the changed point.
3. Check `git status --short` and the relevant diff.
4. Amend the existing commit with `git commit --amend --no-edit`.
5. Run CRA again on the amended commit.

If a finding is invalid or out of scope, preserve a concise reason in the final report or the closest durable artifact when that will prevent the same finding from recurring.

## Stop Conditions

Stop the CRA loop only when one of these is true:

1. The last completed review reports no substantive findings or an equivalent terminal clean state.
2. All remaining findings are explicitly rebuttable with current code, tests, docs, runtime evidence, or user instruction.
3. The review flow failed in a way that cannot be corrected inside the current task; report the failure, exact command, exit signal, and remaining risk.

Do not finish CRA while the review process is still running.

## Final Report

Report:

1. final commit hash
2. changed files and behavioral effect
3. validation commands run
4. skipped validation with reasons
5. last review state
6. accepted findings and fixes
7. rejected findings with reasons
8. remaining risk
9. naming, docs, generated-contract, or file-movement rationale when relevant
