# TCA Loop Reference

Use this reference when the user explicitly requests `TCA 루프` or the software-engineering skill selects TCA autonomously.

TCA means Task-Commit-Approve. It is the outer workflow for a request with multiple independently reviewable task units: complete one task unit, validate it, commit it, run CRA on that commit, update the task queue, and only then decide whether to continue to the next task.

`Approve` means that the current task passed the next-task gate with a CRA terminal state. It is not user approval and does not authorize push, deployment, migration, production mutation, purchasing, or any other external state change.

## Entry Source

Before starting, record one reason for entering TCA:

1. `explicit-request`: the user requested TCA.
2. `autonomous-structure`: separate task commits and CRA gates materially improve correctness, recovery, or reviewability under the software-engineering skill's selection criteria.

For `autonomous-structure`, record the concrete task boundaries, dependency, or recovery risk that justifies TCA. A later user instruction to avoid commits or reviews overrides both entry sources.

## Non-Negotiable Boundaries

1. TCA is not an ordinary plan or a reason to split every multi-step change.
2. Each task unit must have one clear goal, an explainable scope, a local validation contract, and a clean commit boundary.
3. Every TCA task runs CRA after local validation. Do not proceed to the next task while the current task's CRA is running or has unresolved valid findings.
4. When using a worker, delegate only the active task unit and keep at most one write-capable worker in the worktree.
5. Do not manufacture task boundaries that leave the repository broken, misleading, or materially incomplete.
6. Exclude unrelated user or coworker changes, secrets, caches, logs, review output, and temporary artifacts from every task commit.
7. A local commit and CRA result do not authorize push, deployment, migration, snapshot approval, production data changes, or other remote mutation.
8. Autonomous delegation or TCA may use already-configured workers, reviewers, models, service tiers, and the current account's existing usage. It may not purchase credits or change billing, plan, quota, provider, or account settings without explicit approval.

## Task Unit Definition

A task unit must have:

1. one clear goal
2. an explainable scope boundary
3. the closest practical validation plan
4. a local commit boundary
5. a rollback or failure story
6. clear dependencies on earlier or later task units
7. directly connected code, tests, docs, config, names, or generated-contract consistency needed to leave that unit coherent

Split by independently shippable behavior, prerequisite structure, migration phase, public contract, or separable bug-fix versus refactor concerns. Do not split directly connected consistency work away from the functional change merely to create more tasks.

## Task Queue

Maintain the queue as an execution record, not a fixed promise:

```text
Entry source: <explicit-request|autonomous-structure>
Selection rationale: <concrete reason>

[ ] T1. Task name
    - Goal:
    - Scope:
    - Dependency:
    - Expected validation:
    - Execution owner: <worker|primary>
    - Commit boundary:
    - CRA state: pending
    - Status notes:
```

Update the queue when new facts, failures, review findings, or design changes alter the safest remaining sequence. Remove or merge planned tasks when the discovered structure no longer justifies separate boundaries.

## Task Selection Order

Choose the next task by this priority:

1. work that fixes a current failure or blocks every later task
2. prerequisites whose reviewed contract makes later work safer
3. the smallest independently verifiable coherent unit
4. directly connected consistency needed to leave that unit understandable and operable
5. work that reduces risk sooner than the alternatives

## Single Task Flow

For each task unit:

1. Select the task and restate its goal, scope, dependency, validation, and completion condition.
2. Create the execution contract from `references/worker-delegation.md`. Delegate implementation and local validation to `worker` by default when the contract is precise and subagents are available; otherwise record the direct-execution fallback.
3. Wait for the active task's worker to return before starting another write task in the same worktree.
4. Inspect the actual changes, worker evidence, and repository state; do not accept a completion summary as proof.
5. Run or repeat local validation appropriate to the changed contract when the returned evidence is insufficient or the task risk warrants independent execution.
6. Check `git status --short` and the relevant diff; separate unrelated changes.
7. Commit only the current task unit.
8. Run CRA with entry source `tca-required`.
9. Verify and process CRA findings, amend the same task commit, and revalidate from the changed point.
10. Record the final commit and CRA terminal state in the queue.
11. Reassess whether the next planned task is still necessary and correctly bounded.

Do not start implementing the next task until the current task has a commit, a local validation record, a CRA terminal state, and an updated queue entry.

## CRA Restart Rules

If CRA produces a valid finding:

1. implementation changed: rerun local validation from the changed point
2. test expectation changed: rerun the affected tests first
3. name or file location changed: recheck directly connected imports, docs, tests, settings, logs, and generated contracts
4. config or deployment surface changed: recheck runtime context and environment assumptions
5. task goal or scope changed: update the queue and decide whether to continue, merge, split, or stop
6. dependency changed: update the remaining task order before selecting the next task

The current task is not complete until the amended commit reaches a CRA terminal state with no unresolved valid finding inside the task boundary.

## Next Task Gate

Proceed only when all are true:

1. the current task has one coherent commit
2. local validation appropriate to that task has run
3. skipped validation and reasons are recorded
4. the primary session inspected the actual diff and repository state
5. the last CRA reached a terminal state
6. no valid critical, high-risk, or in-scope medium finding remains unresolved
7. CRA-triggered changes were revalidated from the correct point
8. the task queue reflects the current repository state
9. the next task remains requested, necessary, and independently coherent

## Stop Conditions

Stop instead of continuing when:

1. the user cancels or reverses the workflow
2. the current task boundary becomes unclear
3. unrelated changes cannot be separated safely
4. required local validation is unavailable or its failure cannot be classified
5. the worker handoff fails and no safer direct-execution fallback exists
6. CRA fails in a way that cannot be corrected inside the current task
7. a migration, deployment, production data update, purchase, or other external state change needs explicit approval
8. review findings change the task premise and the queue has not yet been updated
9. the next planned task is no longer necessary or cannot form a coherent boundary

## Final Report

Report:

1. TCA entry source and autonomous selection rationale when applicable
2. completed, merged, removed, and deferred task units
3. execution owner and worker evidence for each completed task
4. final commit hash for each completed task
5. local validation and skipped checks for each task
6. CRA terminal state, accepted findings, and rejected findings for each task
7. review fixes that changed a task boundary or restart point
8. remaining risk and any external action still requiring approval
