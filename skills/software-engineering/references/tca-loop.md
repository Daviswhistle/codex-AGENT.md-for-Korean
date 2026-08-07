# TCA Loop Reference

Use this reference only when the user explicitly requests `TCA 루프`.

TCA means Task-Commit-Approve. It is the outer loop for multi-step work: split the request into independently reviewable task units, complete one task unit, commit it, run CRA on that commit, update the task queue, and only then continue to the next task.

## Purpose

TCA prevents these failures:

1. unrelated goals mixed into one commit
2. review fixes blurring the original task boundary
3. test failures whose owning task is unclear
4. new work being built on top of an unapproved current commit
5. names, docs, tests, settings, or generated contracts drifting after review fixes
6. the agent silently starting follow-up work the user did not ask for

## Task Unit Definition

A task unit must have:

1. one clear goal
2. an explainable scope boundary
3. a local commit boundary
4. the closest practical validation plan
5. a rollback or failure story
6. explicit naming, docs, tests, settings, generated-contract, and deployment-surface consistency checks when relevant
7. clear dependencies on earlier or later task units

Split oversized work by public behavior, internal structure, naming or file movement, tests, docs, config, deployment, migrations, and separable bug-fix versus refactor concerns.

Do not split directly connected consistency work away from the functional change when doing so would leave the task unit materially inconsistent.

## Task Queue Format

Maintain the queue as an execution record, not as a fixed promise:

```text
[ ] T1. Task name
    - Goal:
    - Scope:
    - Dependency:
    - Expected validation:
    - Commit boundary:
    - CRA need:
    - CRA route:
    - CRA state:
    - Approval needed:
    - Resume point:
    - Status notes:
```

Use `approval-pending` as the task status when CRA returns `approval-required`. Update the queue when new facts, failures, review findings, approvals, or design changes alter the next safest step.

## Task Selection Order

Choose the next task by this priority:

1. work that fixes a current failure or prevents a regression
2. work that is a prerequisite for later tasks
3. the smallest independently verifiable unit
4. naming, docs, tests, config, or generated-contract consistency needed to keep the completed task understandable
5. work that reduces risk sooner than the alternatives

## Single Task Flow

For each task unit:

1. select the task
2. restate goal, scope, dependency, and completion condition
3. inspect relevant files, entry points, tests, docs, config, and source of truth
4. implement the smallest coherent change
5. run local verification from the changed contract
6. update directly connected docs, tests, names, settings, generated contracts, or examples
7. check `git status --short` and relevant diffs
8. commit only the task unit
9. run CRA on the commit when the current usage boundary authorizes it
10. if CRA returns `approval-required`, follow the pause-and-resume contract below
11. process completed CRA findings
12. update the task queue and status notes
13. decide whether the next task is still valid

Do not start implementing the next task until the current task has a commit, local verification record, CRA terminal state, and updated queue entry. `approval-required` does not satisfy the CRA terminal-state gate.

## Approval-Required Pause And Resume

When CRA returns `approval-required` during an active TCA task:

1. set the task status to `approval-pending`
2. record the current task ID, commit SHA, CRA entry source, reviewer invocation count, exact additional authority or cost boundary requested, completed validation, remaining risk, and the resume point
3. request the narrow approval required and stop the TCA loop
4. Do not mark the task complete. Do not select or implement the next task while approval is pending.
5. if approval is denied or not supplied, keep the task deferred at `approval-pending` and report the blocked continuation
6. if approval is granted, confirm that it covers the recorded command and boundary, then re-check branch, commit, worktree, task scope, and whether prior validation is still current
7. re-run validation when the checkout, commit, environment, or relevant assumption changed while paused
8. resume the same task at the CRA usage-authorization check; do not create a new task or silently restart from implementation
9. after the authorized reviewer invocation finishes, process findings and continue through the ordinary next-task gate

An approval for one command, purchase, usage ceiling, or task unit does not widen later TCA tasks. Record any newly approved ceiling in the queue before resuming.

## CRA Fix Restart Rules

If CRA produces a valid finding and the task changes:

1. implementation changed: rerun local verification from the changed point
2. test expectation changed: rerun the affected tests first
3. name or file location changed: recheck references, imports, docs, tests, logs, metrics, and settings
4. config or deployment surface changed: recheck runtime context and environment assumptions
5. task goal or scope changed: return to task selection and decide whether to continue, split, or stop
6. dependency changed: update the queue before selecting the next task

The current task is not complete until the amended commit passes CRA or only explicitly rebuttable findings remain.

## Next Task Gate

Proceed only when all are true:

1. the current task has a commit
2. the last CRA reached a terminal state; `approval-required`, `approval-pending`, and `blocked` do not satisfy this condition
3. no valid critical or high-risk issue remains in scope
4. no valid medium issue remains inside the current task boundary without an explicit reason
5. executable validation has run
6. skipped validation and reasons are recorded
7. CRA-triggered changes were revalidated from the correct point
8. the task queue reflects the current repository state
9. no approval request or resume checkpoint remains open for the current task

## Stop Conditions

Stop instead of continuing when:

1. CRA failed and the cause is unclear
2. CRA returned `approval-required`; record `approval-pending`, request the narrow approval, and preserve the same-task resume point
3. the current task boundary became unclear
4. unrelated user or coworker changes cannot be separated safely
5. a migration, deployment, production data update, snapshot approval, or other state-changing action needs explicit user approval
6. a failing test cannot be classified as implementation, expectation, environment, or stale fixture
7. the next change would make the current commit meaning unclear
8. CRA changed the task premise but the queue has not been updated
9. required revalidation after CRA fixes has not run

## Final Report

For multi-task TCA work, report:

1. completed task list
2. final commit hash for each task
3. CRA route and terminal state for each task
4. validation run for each task
5. skipped validation and reasons
6. CRA fixes that forced a restart point
7. pending or denied approvals, the exact requested boundary, and the recorded resume point
8. deferred findings or follow-up tasks
9. naming, docs, generated-contract, or file-movement rationale when relevant
