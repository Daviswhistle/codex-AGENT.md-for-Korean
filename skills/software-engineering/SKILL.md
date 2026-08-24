---
name: software-engineering
description: Use for software implementation, modification, debugging, refactoring, or review tasks to delegate bounded execution to a worker when useful, decide autonomously whether Commit-Review-Amend (CRA) or Task-Commit-Approve (TCA) would materially improve correctness, reviewability, recovery, or completion confidence, and run the selected structure. Explicit worker delegation, CRA, or TCA requests also trigger this skill.
---

# Software Engineering Workflows

Use this skill only to choose and run the execution structure for software changes: bounded worker delegation, CRA, and TCA. It does not replace root or project instructions, ordinary engineering judgment, implementation details, or local validation.

## Selection Contract

For every software modification:

1. Before implementation, decide whether TCA is warranted.
2. If TCA is selected, read `references/tca-loop.md` before creating the task queue or editing.
3. For each coherent task unit, decide whether delegating implementation and local validation to a `worker` would materially improve focus, context preservation, recovery, or completion confidence.
4. Delegate by default when the task can be bounded by a clear execution contract and a suitable worker is available. Otherwise complete the task unit directly under the delegation exceptions below.
5. After local validation, the primary session inspects the actual diff and evidence, then decides whether CRA is warranted.
6. If neither CRA nor TCA is warranted, finish normally without creating a task queue, extra commits, or review ceremony.

Re-evaluate TCA before the first commit if the discovered scope materially changes. A user request for worker delegation, CRA, or TCA selects that structure when its safety preconditions can be met. A later instruction to avoid subagents, commits, or reviews overrides the corresponding entry path. Do not ask for permission solely because the user did not name the structure.

## Execution Delegation

The primary session retains requirement interpretation, the intended outcome, task boundaries, workflow selection, completion criteria, verification, and the final response.

Delegate implementation and local validation to the `worker` agent by default when all of these are true:

1. The task unit has a clear goal, scope, constraints, and completion evidence.
2. The worker can operate inside the current permissions without new external authority.
3. A separate execution context would reduce noisy intermediate output, preserve the primary context, or add meaningful recovery value.
4. The handoff and verification cost is lower than the expected execution benefit.
5. The current worktree can safely have one write-capable worker.

Before spawning the worker, provide an execution contract containing:

1. goal and intended behavioral result
2. in-scope and out-of-scope boundaries
3. applicable root, project, and domain instructions
4. permissions and forbidden actions
5. required validation
6. completion evidence to return
7. known dependencies, risks, and relevant prior decisions

The worker must return the behavioral result, changed files, validation commands and outcomes, skipped validation, remaining uncertainty, blockers, and any discovery that changes the task premise.

The primary session must inspect the actual changes and validation evidence. A worker summary or completion claim is not sufficient. The primary normally owns commit creation, CRA entry, finding adjudication, and the next-task gate.

Use direct implementation instead when one of these is true:

1. The change is trivial and handoff overhead would exceed the work.
2. The task cannot be separated from an active interactive decision without losing essential context.
3. A suitable worker or subagent facility is unavailable.
4. The worker failed and direct recovery is safer than another handoff.
5. Unrelated worktree changes cannot be isolated safely for a write-capable worker.

Allow only one write-capable worker in a worktree at a time. Parallel agents in the same worktree should remain read-only. Parallel implementation requires isolated worktrees and separately verifiable task contracts.

The worker does not independently broaden scope, choose a new product direction, create or amend commits, run CRA, push, deploy, migrate, purchase, or mutate remote state unless the primary's execution contract explicitly authorizes that action.

Under TCA, delegate at most one task unit for implementation in a worktree at a time. Do not start the next task until the primary has inspected the current task, committed it, completed its CRA gate, and updated the queue.

## TCA Decision

Select TCA when the user explicitly requests it or when task-by-task commit and CRA gates would materially improve correctness, recovery, or reviewability.

Autonomous TCA is warranted when several of these are true:

1. The request contains two or more independently explainable and verifiable task units.
2. Later work depends on an earlier unit being committed and independently reviewed first.
3. Combining the work would obscure why a commit exists, which validation belongs to it, or how to roll it back.
4. The work is likely to be interrupted or compacted, so stable reviewed checkpoints materially reduce recovery risk.
5. A migration, broad refactor, or behavior change has safe intermediate boundaries that should not be crossed while unreviewed.
6. Each task unit is important enough that its own CRA result would change whether the next unit should proceed.

Usually skip autonomous TCA when:

1. The work has one coherent outcome even if it has many steps or touches many files.
2. Splitting would leave an intermediate commit broken, misleading, or materially incomplete.
3. The change is a mechanical batch edit, generated update, or rename with one validation contract.
4. The candidate task units are too small for separate commit and review overhead to improve the result.
5. A clean series of task commits cannot be isolated from unrelated work.

When TCA is selected, every task unit uses CRA after local validation. Do not make a second CRA decision inside TCA. If an explicit TCA request has only one defensible task unit, do not invent boundaries; run it as one TCA task with CRA and report that the queue collapsed to one unit.

## CRA Decision

After local validation, select CRA when independent commit-level review would materially improve confidence. The user does not need to name CRA.

Run CRA when:

1. The user explicitly requests it or an active TCA task requires it.
2. The change affects authentication, authorization, secrets, billing, money, persisted data, migrations, concurrency, recovery, deployment, runtime configuration, agent authority, or an external or public contract.
3. The change spans multiple callers, states, or failure paths; performs a broad refactor; addresses a repeated regression; cannot be exercised adequately through local validation; or retains material uncertainty.
4. The user asks for production readiness, unusually high confidence, or independent review.

Usually skip autonomous CRA for typo, formatting-only, comments-only, or narrowly mechanical changes whose contract is fully established by focused validation.

Do not run CRA when the user asks to avoid commits or reviews, the task is review-only, a clean task-unit commit cannot be isolated, or local validation is missing. CRA is not a substitute for local validation.

When CRA is selected, read `references/cra-loop.md` and follow it without duplicating or partially reconstructing the loop from this front page.

## Shared Boundaries

1. Keep each commit limited to one coherent task unit and exclude unrelated user or coworker changes, secrets, logs, caches, review output, and temporary artifacts.
2. Treat local commits as reviewable checkpoints, not permission to push, deploy, migrate, approve snapshots, update production data, or otherwise mutate remote state.
3. Autonomous delegation, CRA, or TCA may use already-configured agents, reviewers, models, service tiers, and the current account's existing usage. It may not purchase credits, change billing, plan, quota, provider, account, or persistent runtime settings without explicit approval.
4. A workflow failure does not authorize masking the problem, weakening validation, or silently finishing as though the workflow passed.
5. If delegation or a review workflow cannot proceed safely, use the smallest valid fallback and report the blocked state, missing prerequisite, and remaining risk.

## Reporting

When worker delegation is used, report the delegated task boundary, execution contract, returned evidence, primary verification, and any fallback or remaining risk.

When CRA or TCA is used, report the entry source and rationale, task or commit boundaries, validation, review terminal state, accepted and rejected findings, skipped checks, and remaining risk.

When none of these structures is used, do not add process narration solely to announce that they were skipped.

## References

1. `references/cra-loop.md` - Commit-Review-Amend mechanics, state model, blocking reviewer command, findings, amendments, stop conditions, and reporting.
2. `references/tca-loop.md` - Task-Commit-Approve selection record, task queue, per-task CRA gate, restart rules, stop conditions, and reporting.
