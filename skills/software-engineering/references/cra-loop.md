# CRA Loop

CRA means Commit-Review-Amend. Use it after local validation when independent commit-level review is required by the user, TCA or the software-engineering risk criteria.

## Default reviewer

- model: `gpt-6-astra`
- reasoning: `medium`
- service tier: `default` (non-Fast)
- context: runtime default

Astra is a quality-per-review default, not a claim of lower token price. If the review packet does not fit safely, reduce/split the packet rather than enlarging context.

## Preconditions

1. local validation has run;
2. the task is represented by one clean non-merge commit with a fixed parent;
3. unrelated changes, secrets, generated artifacts and review bookkeeping are excluded;
4. the reviewer did not author the change.

A local commit does not authorize push, deployment, migration or remote mutation.

## Review contract

The first pass reviews the complete task diff. Every amendment delta is also reviewed in full.

Define the smallest useful claim-based units covering changed behavior and directly connected callers, tests, config, schema, docs or public contracts. Small tasks may have one unit.

Give the reviewer:

- task parent and current SHA
- complete diff target
- unit claims
- applicable instructions
- relevant local-validation evidence
- unresolved risks

Ask for ordinary findings plus compact unit coverage such as:

```text
Coverage: U1=clean; U2=finding.
```

Run with the profile explicit:

```bash
CRA_REVIEW_MODEL="${CRA_REVIEW_MODEL:-gpt-6-astra}"
CRA_REVIEW_EFFORT="${CRA_REVIEW_EFFORT:-medium}"

codex review - \
  -c "model=$CRA_REVIEW_MODEL" \
  -c "model_reasoning_effort=$CRA_REVIEW_EFFORT" \
  -c service_tier=default \
  -c features.fast_mode=false \
  < "$PROMPT_PATH" > "$REVIEW_LOG" 2>&1
```

If the installed CLI does not support `codex review -`, use the supported commit-review form with the same resource profile. A zero process exit only means the command completed; it does not mean the review is clean.

## Amendments

For every accepted finding:

1. fix the task-relevant defect;
2. rerun the closest affected validation;
3. amend the same task commit;
4. inspect the full delta from the previously reviewed SHA;
5. invalidate every unit whose scope, dependency, evidence or instruction changed;
6. add units for new behavior.

File non-intersection is not enough to preserve a clean conclusion.

Incremental review must inspect the complete amendment delta and all invalidated/unknown units. If impact cannot be bounded confidently, run a full task review again.

## Active record

If continuity is needed, keep only the current CRA state outside the worktree under `$(git rev-parse --git-path cra)`: task parent, current SHA, units, open findings and pass results. Do not preserve it as product history after the task.

## Completion

CRA is clean only when:

1. validation applicable to the current commit passes or limitations are disclosed;
2. the latest review command completed;
3. the complete initial diff was reviewed;
4. every amendment delta was reviewed;
5. no substantive finding remains open;
6. every active unit is clean through the current SHA;
7. HEAD, parent and worktree still match the reviewed state.

Auth, quota, model availability, command support or transport failure is a review failure, not a reason to silently weaken the profile.
