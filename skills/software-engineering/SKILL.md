---
name: software-engineering
description: Use for software implementation, modification, debugging, refactoring, or code review. Define a coherent task contract, delegate bounded implementation when useful, verify the actual result, and use CRA or TCA only when independent review or task commits materially improve confidence.
---

# Software Engineering

The primary session owns user intent, task boundaries, integration, verification and the final response.

## Selection

For software changes:

1. define one coherent task unit, authority and checkable completion criteria;
2. inspect the actual execution path before editing;
3. decide whether delegation adds enough value to justify coordination;
4. if delegating, read `references/worker-delegation.md` and send a bounded contract;
5. inspect the returned diff/state and independently verify completion-critical evidence;
6. decide whether CRA is warranted after local validation;
7. use TCA only when multiple independently reviewable task commits materially improve correctness, recovery or reviewability.

Do not create workflow ceremony merely because a workflow exists.

## Resource defaults

- bounded implementation worker: first candidate `gpt-5.6-luna`, Max reasoning, Fast tier
- independent CRA reviewer: `gpt-6-astra`, Medium reasoning, default/non-Fast service tier
- every role: runtime default context; this kit does not raise context-window or auto-compaction limits

Escalate resources only for a concrete quality reason such as ambiguity, consequence of error, difficult reasoning or an insufficient result.

## Local validation

Start with checks closest to the changed behavior and connected contracts. Expand for shared dependencies, broad changes, material uncertainty, safety risk or explicit project requirements.

Reuse a prior result only when the target, dependencies, configuration, environment and acceptance criteria are still applicable and the evidence remains available. Recheck affected results after amendments.

Passing static checks does not establish deployment readiness or model behavior.

## Delegation

Use a bounded worker for non-trivial implementation when the contract is precise and separation materially improves execution or primary-context quality. Implement directly when the task is trivial, cannot be separated from a live product decision, subagents are unavailable or another handoff would cost more than it saves.

Treat one mutable worktree as a single-writer/stable-reader boundary. A writer summary is navigation, not proof.

## CRA

Use CRA when the user explicitly requests it or independent commit-level review materially improves confidence: authentication/authorization, secrets, billing/money, persisted data, migrations, concurrency/recovery, deployment/runtime configuration, agent authority, public contracts, broad multi-path changes or material uncertainty.

Usually skip CRA for narrow mechanical changes already established by focused validation.

When selected, read `references/cra-loop.md`.

## TCA

Use TCA when the user explicitly requests it or a large change has safe, dependency-ordered, independently verifiable commit boundaries whose per-task CRA materially improves recovery/reviewability. Do not manufacture task boundaries.

When selected, read `references/tca-loop.md`.

## Boundaries

- Workers may not broaden product intent or perform push, deployment, migration, purchases or remote mutation.
- Local commits are checkpoints, not permission for external writes.
- Existing account usage may be used; billing, plan, quota, provider or account settings may not be changed without explicit approval.
- Do not weaken validation to obtain a pass.

Report material delegation/review evidence, skipped checks and remaining risk. Do not narrate skipped workflows when they do not affect confidence.
