---
name: software-engineering
description: Use for software implementation, modification, debugging, refactoring, or review tasks to delegate bounded implementation and local validation to an execution worker when useful, and to decide autonomously whether Commit-Review-Amend (CRA) or Task-Commit-Approve (TCA) would materially improve correctness, reviewability, recovery, or completion confidence. Explicit worker, CRA, or TCA requests also trigger this skill.
---

# Software Engineering Workflows

Use this skill to choose execution ownership and, when useful, run CRA or TCA. It does not replace root or project instructions, ordinary engineering judgment, implementation, or local validation.

## Selection Contract

For every software modification:

1. Before implementation, decide whether TCA is warranted.
2. If TCA is selected, read `references/tca-loop.md` before creating the task queue or editing.
3. Define the current task unit and its execution contract before delegating or editing.
4. For non-trivial implementation, delegate the bounded change and local validation to the `worker` agent by default when subagents are available and the handoff can be made precise.
5. Under TCA, delegate and finish one task unit at a time. Do not let multiple write-capable workers edit the same worktree concurrently.
6. The primary session must inspect the actual diff, repository state, and validation evidence. A worker summary or completion claim is not sufficient.
7. After local validation of the task unit, decide whether CRA is warranted.
8. If neither TCA nor CRA is warranted, finish normally without creating a task queue, extra commits, or review ceremony.

Re-evaluate TCA before the first commit if the discovered scope materially changes. A user request for worker delegation, CRA, or TCA selects that path when its safety preconditions can be met. A later instruction to avoid subagents, commits, or reviews overrides the corresponding entry path. Do not ask for permission solely because the user did not name the workflow.

## Execution Delegation

Before the first delegated write task in a session, read `references/worker-delegation.md`.

The primary session owns:

1. user intent, desired final state, and completion criteria
2. TCA and CRA selection
3. task boundaries, dependencies, and execution contracts
4. commit boundaries and independent review
5. inspection of the final diff and validation evidence
6. the final completion decision and response

The worker owns only the bounded implementation and local validation described in its contract. Give it:

1. goal and scope
2. constraints and applicable project instructions
3. required validation and completion evidence
4. permitted authority, including whether it may commit
5. the exact return contract

The worker must return changed files, behavioral effect, validation commands and outcomes, skipped checks, remaining uncertainty, and blockers or contradictions. It may not broaden product intent, hide unrelated changes, select a different workflow, push, deploy, migrate, purchase, or mutate remote state.

The primary session may implement directly when the change is trivial, the work cannot be separated from an active interactive decision, subagents are unavailable, or a failed handoff makes direct recovery safer than another delegation. Do not delegate merely to add ceremony when coordination cost is greater than the expected benefit.

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
3. Autonomous delegation, CRA, or TCA may use already-configured agents, reviewers, models, service tiers, and the current account's existing usage. It may not purchase credits, change billing, plan, quota, provider, or account settings without explicit approval.
4. A workflow failure does not authorize masking the problem, weakening validation, or silently finishing as though the workflow passed.
5. If the workflow cannot proceed safely, report the blocked state, missing prerequisite, and remaining risk.

## Reporting

When worker delegation is used, report the delegated task boundary, returned validation evidence, the primary session's independent inspection, and any remaining risk. When CRA or TCA is used, also report the entry source and rationale, task or commit boundaries, validation, review terminal state, accepted and rejected findings, skipped checks, and remaining risk.

When delegation, CRA, or TCA is skipped, do not add process narration solely to announce that it was skipped unless the missing capability or direct-execution fallback materially affects confidence.

## References

1. `references/worker-delegation.md` - primary/worker responsibilities, execution contract, write-concurrency boundary, return evidence, and direct-execution fallbacks.
2. `references/worker-luna-max-fast.toml` - optional model-specific custom `worker` example using GPT-5.6 Luna, Max reasoning, and Fast service tier; it is not an installed or normative default.
3. `references/cra-loop.md` - Commit-Review-Amend mechanics, state model, blocking reviewer command, findings, amendments, stop conditions, and reporting.
4. `references/tca-loop.md` - Task-Commit-Approve selection record, task queue, per-task worker execution and CRA gate, restart rules, stop conditions, and reporting.
