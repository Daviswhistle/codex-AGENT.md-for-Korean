# CRA Loop Reference

Use this reference when the user explicitly requests `CRA 루프`, TCA requires CRA, or `software-engineering/SKILL.md` autonomously selects CRA because independent commit-level review is warranted.

CRA means Commit-Review-Amend. It turns one completed task unit into a local commit, reviews that commit as a finished batch, and amends the same commit until the final review has no substantive findings or only findings that are explicitly rebuttable with current evidence.

## Entry Sources

Record one primary entry source:

1. `explicit-request`: the user explicitly requests CRA.
2. `tca-required`: the active TCA task gate requires CRA.
3. `autonomous-risk`: the software-engineering skill determines that independent commit-level review is likely to materially reduce risk or uncertainty.

The low-value autonomous skip rule never cancels `explicit-request` or `tca-required`. A later user instruction to avoid commits or reviews overrides every entry source.

Record the entry source and, for `autonomous-risk`, the concrete risk or uncertainty that justified the review.

## Usage Authorization

Check authorization before every reviewer command invocation and record the source and invocation count.

1. `explicit-request` and `tca-required` supply task-specific approval for the required CRA entry and its ordinary configured inference usage. They do not authorize purchasing credits, changing a plan or billing setting, increasing quota, or enabling another paid service.
2. `autonomous-risk` uses the bounded standing approval in `software-engineering/SKILL.md`. It covers the configured reviewer command using the current account's existing included quota or metered inference usage for at most three reviewer command invocations per task unit.
3. Count an invocation when the reviewer command is launched, regardless of whether it later completes, returns findings, or fails.
4. If the next autonomous invocation would be the fourth, or any entry source would require a purchase or billing-setting change, do not run the command. Return to the CRA decision with route `approval-required` and request explicit approval.
5. Do not infer authorization from the fact that the commit and logs are local. Local mutation authority and inference-usage authority are separate.

## Non-Negotiable Boundaries

1. CRA starts after one coherent task unit is implemented and locally verified as far as reasonably possible.
2. CRA requires a local commit because `codex review --commit` reviews a commit boundary.
3. A local commit is not approval to push, deploy, migrate, approve snapshots, update production data, or mutate remote state.
4. Exclude generated files, caches, logs, review logs, sentinel files, secrets, credentials, and unrelated user or coworker changes from the commit.
5. Use CRA only for the requested task unit. Do not fold unrelated cleanup or follow-up work into the amend cycle.
6. Do not use CRA as a substitute for missing local validation or an unclear source of truth.
7. Do not start CRA when a clean task-unit commit cannot be isolated safely.

## State Model

Track an invoked review in exactly one of these states:

1. `running`: the review process is still alive.
2. `completed-clean`: the final review says `no substantive findings` or an equivalent terminal status.
3. `completed-with-findings`: the final review has substantive findings.
4. `failed`: the review command, transport, auth, quota, model selection, or process execution failed.

`approval-required` and `blocked` are pre-invocation CRA decision routes, not review process states. Do not infer a terminal state from in-progress output.

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
5. Re-check the usage boundary, then run CRA again on the amended commit when authorized.

If a finding is invalid or out of scope, preserve a concise reason in the final report or the closest durable artifact when that will prevent the same finding from recurring.

## Stop Conditions

Stop the CRA loop only when one of these is true:

1. The last completed review reports no substantive findings or an equivalent terminal clean state.
2. All remaining findings are explicitly rebuttable with current code, tests, docs, runtime evidence, or user instruction.
3. The review flow failed in a way that cannot be corrected inside the current task; report the failure, exact command, exit signal, and remaining risk.
4. The next reviewer invocation requires approval under the usage boundary; report route `approval-required`, the invocation count, and the additional authorization needed.

Do not finish CRA while the review process is still running.

## Final Report

Report:

1. entry source and autonomous risk rationale when applicable
2. usage-authorization source and reviewer invocation count
3. final commit hash
4. changed files and behavioral effect
5. validation commands run
6. skipped validation with reasons
7. last review state or pre-invocation route
8. accepted findings and fixes
9. rejected findings with reasons
10. remaining risk
11. naming, docs, generated-contract, or file-movement rationale when relevant
