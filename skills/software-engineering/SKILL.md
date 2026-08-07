---
name: software-engineering
description: Davis software-engineering discipline for software changes, debugging, review handling, validation boundaries, commit boundaries, autonomous CRA selection and CRA/TCA loops, runtime/cache/generated-artifact checks, vendor contract review, and interrupted workstream recovery. Use when a task needs Davis-style engineering judgment across code, tests, docs, config, deployment-adjacent validation, or source-of-truth analysis. Complements specialized GitHub, Vercel, frontend, framework, API, or docs skills; use those for domain details.
---

# Software Engineering

Use this skill to finish software work as a coherent engineering change, not as a loose patch.

This is an engineering judgment skill, not a framework skill. If another skill covers the domain, such as GitHub PR handling, frontend implementation, Next.js, Vercel, OpenAI docs, or skill creation, use that domain skill for the technical details and use this skill for scope, validation, review, commit, and finish criteria.

Keep this front page compact. When a task needs detailed loop mechanics, restart gates, or consistency passes, use the bundled reference playbooks.

## Core Contract

1. Work from the current checkout, not memory or intention.
2. Keep the scope tight, but include directly connected code, tests, docs, config, generated contract, and deployment-surface consistency.
3. Protect user and coworker changes. Do not revert, overwrite, or hide unfamiliar changes.
4. Prefer root-cause fixes over fallback, masking, or test-only appeasement.
5. Make names match current responsibility. Function, file, module, test, setting, log, metric, and doc names are maintenance interfaces.
6. Distinguish verification from approval or external state change.

## Commit Boundary

Record a commit only when all of these are true:

1. The change is one clear task unit.
2. The included files were checked with `git status --short` and, when needed, `git diff`.
3. Generated files, logs, review logs, sentinel files, caches, secrets, and unrelated user changes are excluded.
4. Reasonable local verification has run, or skipped verification is recorded with a concrete reason.
5. The user did not ask to avoid commits.

Do not record a commit when the scope is unclear, unrelated changes cannot be separated, the task is review-only, or the change needs user approval before being recorded.

Treat a local commit as a reviewable checkpoint, not approval to publish or change external state. Never push, deploy, migrate, approve snapshots, update production data, or otherwise change external state unless the user explicitly asks.

## Reference Material

Use these deeper references only when the task crosses that surface:

1. `references/cra-loop.md` - detailed Codex Review Agent loop mechanics, state model, log discipline, findings, and reporting.
2. `references/tca-loop.md` - detailed Task-Commit-Approve queue, task boundary, restart, and stop rules.
3. `references/naming-docs-consistency.md` - deeper checks for names, docs, tests, settings, logs, metrics, and public contracts.
4. `references/cra-routing-evaluation.md` - representative high-risk, low-risk, user-override, explicit-request, TCA, and cost-boundary routing evaluation.

Reference files refine this skill. They do not override the Core Contract, root `AGENTS.md`, or a more specific domain skill.

## Start The Work

1. State the goal and completion condition in one sentence for non-trivial work.
2. Check branch and worktree state before editing.
3. Read the relevant entry points, call flow, data flow, failure paths, docs, config, and tests before choosing the fix.
4. For a bug, find all callers or producers with `rg` before patching one visible path.
5. Identify deployment, database, permissions, environment variables, caches, generated artifacts, and runtime state that may affect the answer.
6. If external behavior or a library contract is uncertain, verify it from official or primary sources first.

## Find The Source Of Truth

Do not answer current-state questions from docs alone. For questions like "is this active?", "can I deploy now?", "is this the default?", "what does this log mean?", or "does this script refresh it?", identify the current source of truth:

1. loader or runtime branch actually used
2. generated artifact contents and coverage
3. deploy script behavior and current environment boundary
4. persisted state, cache, database, or object-store role
5. log line origin and the condition that emits it
6. tests or validators that prove the contract

Separate axes before answering. Runtime dependency, layer rebuild, env rewrite, code deploy, data backfill, cache refresh, and report generation may be different operations even when they share files.

For vendor or official API comparison, read vendor-provided navigation first when present: `llms.txt`, agent guidance, docs index, examples index, or API reference table. Use broad grep after narrowing the reference subtree.

## Implement

1. Follow local style, framework conventions, package boundaries, and existing helper APIs.
2. Add an abstraction only when it reduces real duplication or clarifies a real responsibility boundary.
3. Add fallback only when the failure mode, selection condition, observable signal, and maintenance owner are clear.
4. Preserve defensive or risk-reduction operations when later optional data loading can fail.
5. Keep compatibility paths when existing persisted records or old payloads still need to be read.
6. When public behavior changes, update the closest docs, examples, generated-contract descriptions, or reproduction commands.
7. Do not expose secrets through source, logs, command lines, exceptions, or final output.
8. When responsibility or public behavior shifts, use `references/naming-docs-consistency.md` to decide which names, docs, tests, settings, logs, metrics, or generated contracts must move with it.

## Validate

1. Start with the smallest verification that proves the changed contract.
2. Expand to lint, typecheck, build, integration, or end-to-end checks only when risk or public surface requires it.
3. For non-trivial logic, leave the smallest durable regression test that would fail if the bug returns.
4. Test public behavior and operational contracts, not incidental object shape.
5. If a test fails, classify it before changing code or expectations: implementation issue, test expectation issue, environment issue, or stale fixture.
6. Wait for long-running silent validators to finish before interpreting success or failure.
7. Record commands run, checks skipped, skip reasons, and remaining risk.

## Review Findings

Treat review output as evidence to evaluate, not as authority.

For each finding, check:

1. Is the fact true in the current checkout?
2. Is it in scope for this task?
3. Is there real runtime, data, security, user-facing, or maintenance risk?
4. Would the proposed fix create a larger regression?
5. Does it improve code, docs, tests, config, and naming consistency?

If a reviewer finding conflicts with runtime evidence or an explicit user clarification, re-check the control flow or run evidence, then follow the stronger current contract. Leave a concise comment, doc note, test, or final explanation when that prevents the same invalid finding from recurring.

## CRA Decision

After local validation, choose and record exactly one route for every non-trivial completed task unit:

1. `run`: enter CRA now.
2. `skip`: independent commit-level review has low expected value for this task unit.
3. `approval-required`: CRA is warranted, but the next review execution is outside the approved cost or usage boundary.
4. `blocked`: CRA cannot start safely because there is no isolatable commit boundary, local validation is missing, the task is review-only, or a later user instruction forbids commits or reviews.

Apply this precedence:

1. A later user instruction to avoid commits or reviews wins and produces `blocked`.
2. An `explicit-request` or `tca-required` entry produces `run` even for a typo, formatting-only edit, or other low-risk task, unless a hard blocker or an unapproved purchase or billing change applies.
3. Otherwise, choose `run` with entry source `autonomous-risk` when independent commit-level review is likely to materially reduce risk enough to justify its usage.
4. Choose `skip` only when no explicit or TCA requirement exists and autonomous review has low expected value.

Presume `autonomous-risk` is warranted when one or more of these apply:

1. The change affects authentication, authorization, secrets, billing, money, persisted data, migrations, concurrency, recovery, deployment, runtime configuration, agent authority or approval boundaries, or an external or public contract.
2. The bug or behavior spans multiple producers, callers, states, or failure paths, or the fix relies on non-obvious control-flow reasoning.
3. The task moves responsibilities across files or modules, performs a broad refactor, or changes names, generated contracts, compatibility paths, or operational behavior across several surfaces.
4. Important behavior cannot be fully exercised locally, the regression has repeated, or remaining uncertainty is material despite local validation.
5. The user asks for production readiness, unusually high confidence, or an independent review without requiring the named CRA procedure.

The low-value skip rule applies only to `autonomous-risk`. Typical autonomous skips include a typo, formatting-only edit, comments-only change, deterministic generated refresh with a proving validator, or another narrowly mechanical change whose contract is fully established by focused validation.

### Autonomous CRA Standing Approval

The user's decision to enable autonomous CRA is a bounded standing approval under root `AGENTS.md`. For an `autonomous-risk` entry, it authorizes the configured `codex review` command to consume the current account's existing included quota or metered inference usage for at most three reviewer command invocations per task unit.

This standing approval does not authorize purchasing credits, changing a plan or billing setting, increasing a quota, enabling a new paid service, or starting a fourth reviewer invocation for the same task unit. Before any such action, choose `approval-required` and ask for explicit approval. Track the invocation count in the CRA record. An explicit CRA request or active TCA request supplies task-specific approval for its required CRA entry, but still does not authorize a purchase or billing-setting change.

Do not use CRA as a substitute for missing local validation.

## CRA Loop

When the CRA decision says `run`, read `references/cra-loop.md` before starting and follow its entry-source record, usage-boundary check, state model, blocking review command, failure classification, finding handling, amendment loop, and final reporting contract. Do not ask again solely because the user did not name CRA, and do not duplicate or partially reconstruct the procedure from this front page.

## TCA Loop

Use only when the user explicitly requests `TCA 루프`. Autonomous CRA selection does not authorize starting TCA. Read `references/tca-loop.md` before creating the task queue and follow its task boundaries, restart gates, CRA dependency, stop conditions, and final reporting contract.

## Interrupted Workstream Recovery

After context compaction, interruption, parallel reviews, or user correction that the thread drifted, stop and restate:

1. active branch and commit
2. intended task
3. already completed validation
4. still-open work
5. running or stale processes
6. files with unrelated user changes

Do not continue editing until the active workstream is clear.

## Finish

Before final response or commit, check:

1. no critical or high-risk issue remains in scope
2. validation appropriate to the change has run
3. skipped validation and remaining risk are known
4. names, docs, tests, settings, and generated artifacts are not materially inconsistent with current behavior
5. `git status --short` shows only intended changes, or a commit has cleanly recorded them

Final response should name the changed files, summarize the behavioral effect, list validation, mention skipped checks and risk, and include commit hash when committed.
