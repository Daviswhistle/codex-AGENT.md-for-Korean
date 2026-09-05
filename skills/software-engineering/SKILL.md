---
name: software-engineering
description: Use for software implementation, modification, debugging, refactoring, or review tasks to delegate bounded implementation and local validation to an execution worker when useful, and to decide autonomously whether Commit-Review-Amend (CRA) or Task-Commit-Approve (TCA) would materially improve correctness, reviewability, recovery, or completion confidence. Explicit worker, CRA, or TCA requests also trigger this skill.
---

# Software Engineering Workflows

Choose execution ownership and, when useful, CRA or TCA. Root and project instructions remain authoritative.

## Selection Contract

For every software modification:

1. Define one coherent task unit, authority, and checkable completion criteria.
2. Decide whether TCA is warranted before implementation. If selected, read `references/tca-loop.md`.
3. Before delegating, prepare the known snapshot, exact scope, required evidence, and bounded tool output.
4. Read `references/worker-delegation.md` before the first worker, explorer, or independent reviewer. Select role, model, reasoning effort, service tier, then history propagation. The kit always uses the runtime's default context window; do not request a larger one.
5. Use Luna Max + Fast as the first bounded implementation-worker candidate when available and sufficient. Do not escalate merely because the primary session uses Astra.
6. For non-trivial implementation, use a bounded worker when subagents are available and the contract is precise; otherwise use the direct-execution fallback.
7. While a writer is active, serialize repository-state-dependent readers in that worktree or give them a fixed snapshot or separate worktree.
8. Inspect the actual diff and repository state and independently verify completion-critical validation evidence.
9. After local validation, decide whether CRA is warranted. If neither TCA nor CRA is warranted, finish without extra ceremony.

## Local Validation

Start with checks closest to the changed behavior and connected contracts. Expand for shared dependencies, broad changes, material uncertainty, safety risk, or explicit project requirements. Do not rerun whole-repository suites merely to demonstrate effort.

Reuse prior results only when the exact target, dependencies, test configuration, environment, and acceptance criteria are still applicable and the evidence remains available. Recheck affected results after amendments. Passing static checks do not establish deployment readiness or model behavior.

## TCA

Use TCA when explicitly requested or when separate task commits and CRA gates materially improve correctness, recovery, or reviewability: independently verifiable units, dependency-ordered work, safe migration/refactor boundaries, or interruption risk. Skip it for one coherent outcome, unsafe intermediate states, mechanical batches with one validation contract, or units too small to justify separate review.

Under TCA, every task unit uses CRA after local validation. Do not invent task boundaries only to satisfy the workflow.

## CRA

Use CRA after local validation when independent commit-level review materially improves confidence. Run it for explicit requests, TCA, authentication/authorization/secrets/billing/money/persisted data/migrations/concurrency/recovery/deployment/runtime configuration/agent authority/public contracts, broad multi-path changes, material uncertainty, or requested production readiness.

Usually skip CRA for typo, formatting, comments, or narrow mechanical changes fully established by focused validation. CRA requires a safely isolated task commit and does not replace local validation.

When selected, read `references/cra-loop.md`. Its default reviewer is Astra Medium on standard tier with the runtime's default context.

## Boundaries

- A worker may not broaden product intent, push, deploy, migrate, purchase, or mutate remote state.
- Local commits are checkpoints, not permission for external writes.
- Autonomous workflows may use existing account usage but may not change billing, plan, quota, provider, or account settings.
- Workflow failure must be reported; do not weaken validation to obtain a pass.

When delegation or review is used, report the task boundary, selected resources, actual validation and review evidence, skipped checks, and remaining risk. Do not narrate skipped workflows when they do not affect confidence.

## References

- `references/worker-delegation.md`: execution contract, resource defaults, history propagation, worktree safety, evidence, and fallbacks.
- `references/worker-luna-max-fast.toml`: opt-in Luna Max + Fast worker example.
- `references/cra-loop.md`: CRA mechanics and review loop.
- `references/tca-loop.md`: TCA queue and per-task CRA flow.
