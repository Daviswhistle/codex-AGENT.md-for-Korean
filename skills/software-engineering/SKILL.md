---
name: software-engineering
description: Use for software implementation, modification, debugging, refactoring, or review tasks to decide autonomously whether Commit-Review-Amend (CRA) or Task-Commit-Approve (TCA) would materially improve correctness, reviewability, recovery, or completion confidence, and to run the selected workflow. Explicit CRA or TCA requests also trigger this skill.
---

# Software Engineering Workflows

Use this skill only to select and run CRA or TCA. It does not replace root or project instructions, ordinary engineering judgment, implementation, or local validation.

## Selection Contract

For every software modification:

1. Before implementation, decide whether TCA is warranted.
2. If TCA is selected, read `references/tca-loop.md` before creating the task queue or editing.
3. If TCA is not selected, complete one coherent task unit under the applicable project instructions.
4. After local validation of that task unit, decide whether CRA is warranted.
5. If neither workflow is warranted, finish normally without creating a task queue, extra commits, or review ceremony.

Re-evaluate TCA before the first commit if the discovered scope materially changes. A user request for CRA or TCA selects that workflow when its safety preconditions can be met. A later instruction to avoid commits or reviews overrides every entry path. Do not ask for permission solely because the user did not name the workflow.

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
3. Autonomous CRA or TCA may use the already-configured reviewer and the current account's existing usage. It may not purchase credits, change billing, plan, quota, provider, or account settings without explicit approval.
4. A workflow failure does not authorize masking the problem, weakening validation, or silently finishing as though the workflow passed.
5. If the workflow cannot proceed safely, report the blocked state, missing prerequisite, and remaining risk.

## Reporting

When CRA or TCA is used, report the entry source and rationale, task or commit boundaries, validation, review terminal state, accepted and rejected findings, skipped checks, and remaining risk. When neither is used, do not add process narration solely to announce that the workflows were skipped.

## References

1. `references/cra-loop.md` - Commit-Review-Amend mechanics, state model, blocking reviewer command, findings, amendments, stop conditions, and reporting.
2. `references/tca-loop.md` - Task-Commit-Approve selection record, task queue, per-task CRA gate, restart rules, stop conditions, and reporting.
