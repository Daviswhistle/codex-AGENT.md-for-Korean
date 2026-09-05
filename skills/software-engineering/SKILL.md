---
name: software-engineering
description: Use for software implementation, modification, debugging, refactoring, or review tasks to delegate bounded implementation and local validation to an execution worker when useful, and to decide autonomously whether Commit-Review-Amend (CRA) or Task-Commit-Approve (TCA) would materially improve correctness, reviewability, recovery, or completion confidence. Explicit worker, CRA, or TCA requests also trigger this skill.
---

# Software Engineering Workflows

Choose execution ownership and, when useful, CRA or TCA. This skill does not replace root or project instructions, ordinary engineering judgment, implementation, or local validation.

## Selection Contract

For every software modification:

1. Decide whether TCA is warranted before implementation. If selected, read `references/tca-loop.md` before creating the queue or editing.
2. Define one coherent task unit, its authority, and checkable completion criteria. Prepare the known snapshot, exact scope, required evidence, and bounded tool output before delegation.
3. Before any worker, explorer, or independent reviewer invocation, read `references/worker-delegation.md` and use its resource-selection contract: role, model, reasoning effort, service tier, context window, then history propagation. Record the selection and verify that the launcher can express it; confirm actual settings from runtime evidence. Do not silently inherit an unintended model or full-history fork.
4. Preserve Luna Max + Fast as the first bounded implementation-worker candidate when available and sufficient. Escalate for a concrete quality reason, not merely because the primary session uses Astra. The detailed selection, fork, telemetry, and compatibility rules live in the worker reference rather than being repeated here.
5. For non-trivial implementation, use a bounded worker by default when subagents are available and the contract is precise. Do not delegate when coordination exceeds the expected benefit; use the direct-execution fallbacks below.
6. Under TCA, complete one task unit at a time. While a writer is active, serialize every repository-state-dependent reader in that worktree or give it a separate worktree or fixed commit snapshot.
7. Inspect the actual diff and repository state, then independently verify completion-critical validation evidence. A worker's summary is not proof.
8. After local validation, decide whether CRA is warranted. If neither TCA nor CRA is warranted, finish without a task queue, extra commits, or review ceremony.

Re-evaluate TCA before the first commit if scope materially changes. Explicit worker, CRA, or TCA requests select that path when its safety preconditions can be met; a later instruction to avoid subagents, commits, or reviews overrides it. Do not ask for permission solely because the user did not name a workflow.

## Execution Delegation

The primary session retains user intent, desired state, completion criteria, workflow and task boundaries, integration, commit boundaries, independent review, final diff inspection, validation verification, and the final response.

Give the worker a bounded goal and scope, constraints and applicable instructions, authority including whether it may commit, required validation, and an exact return contract. It owns only the assigned implementation and local validation. It must return changed files, behavioral effect, validation commands, exit status, relevant raw output or stable artifacts, skipped checks, uncertainty, and blockers or contradictions.

A worker may not broaden product intent, hide unrelated changes, change the selected workflow, push, deploy, migrate, purchase, or mutate remote state. The primary session may implement directly when the change is trivial, an active interactive decision cannot be separated, subagents are unavailable, or a failed handoff makes direct recovery safer. Detailed responsibilities and safe launcher examples remain in `references/worker-delegation.md`.

## Local Validation

Start with checks closest to the changed behavior and connected contracts. Expand for shared dependencies, broad changes, material uncertainty, or safety risk; always run checks required by applicable project instructions. Small tasks do not justify repeated whole-repository suites merely to demonstrate effort, and large models do not justify skipping necessary tests.

Prior results may be reused only when their exact target, relevant dependencies, test configuration, environment, and acceptance criteria remain applicable and their evidence is available. Recheck affected results after amendments; rerun when applicability is uncertain. Inspect current artifacts and raw results rather than accepting an old success label. This does not weaken CRA's complete initial review, full amendment-delta review, or conservative invalidation rules.

Report commands actually run, results, reused evidence when material, and missing checks. Self-inspection is not independent review, and a passing static check does not establish model behavior or deployment readiness.

## TCA Decision

Select TCA when explicitly requested or when task-by-task commit and CRA gates materially improve correctness, recovery, or reviewability.

Autonomous TCA is warranted when several of these are true:

1. There are two or more independently explainable and verifiable task units.
2. Later work needs an earlier unit committed and independently reviewed first.
3. Combining units would obscure rationale, validation ownership, or rollback.
4. Interruption or compaction makes reviewed checkpoints valuable.
5. A migration, broad refactor, or behavior change has safe intermediate boundaries.
6. Each unit's CRA result can change whether the next unit should proceed.

Usually skip autonomous TCA for one coherent outcome, an unsafe or incomplete intermediate state, a mechanical batch with one validation contract, units too small to justify separate reviews, or work that cannot be isolated from unrelated changes.

Under TCA, every task unit uses CRA after local validation; do not make a second CRA decision. An explicit TCA request with one defensible unit stays one unit rather than inventing boundaries. Report that the queue collapsed to one task.

## CRA Decision

Select CRA after local validation when independent commit-level review materially improves confidence. The user need not name it.

Run CRA when:

1. Explicitly requested or required by an active TCA task.
2. The change affects authentication, authorization, secrets, billing, money, persisted data, migrations, concurrency, recovery, deployment, runtime configuration, agent authority, or an external/public contract.
3. Multiple callers, states, or failure paths, a broad refactor, repeated regression, inadequate local coverage, or material uncertainty justify it.
4. Production readiness, unusually high confidence, or independent review is requested.

Usually skip autonomous CRA for typos, formatting, comments, or narrow mechanical changes fully established by focused validation. Do not run it against instructions to avoid commits/reviews, for review-only work, without a safely isolated task commit, or in place of missing local validation.

When selected, read `references/cra-loop.md`; do not reconstruct a partial loop from this entrypoint.

## Shared Boundaries

1. Each commit contains one coherent unit, excluding unrelated changes, secrets, logs, caches, review output, and temporary artifacts.
2. Local commits are checkpoints, not permission to push, deploy, migrate, approve snapshots, update production data, or mutate remote state.
3. Autonomous workflows may use already-configured agents, models, tiers, and existing account usage. They may not purchase credits or change billing, plan, quota, provider, or account settings without explicit approval.
4. A workflow failure does not authorize hiding it, weakening validation, or claiming the workflow passed. Report the blocked state, missing prerequisite, and remaining risk.

## Reporting

When delegating, report the task boundary, selected role/model/effort/tier/context/fork and rationale, returned evidence, primary inspection and verification, and remaining risk. For CRA/TCA also report entry source, task/commit boundaries, reviewer selection, validation, review terminal state, accepted/rejected findings, and skipped checks.

Do not narrate skipped workflows solely to announce that they were skipped. Explain a missing capability or direct-execution fallback when it materially affects confidence.

## References

- `references/worker-delegation.md`: responsibilities, resource selection, context/fork rules, worktree safety, evidence, optional-profile installation, and fallbacks.
- `references/worker-luna-max-fast.toml`: opt-in Luna Max + Fast implementation-worker example; not automatically installed or applied to other roles.
- `references/cra-loop.md`: complete CRA mechanics, coverage ledger, blocking review, amendments, and stop conditions.
- `references/tca-loop.md`: TCA selection, task queue, per-task execution and CRA, and restart rules.
