# Worker Delegation

Use when a software task is delegated to a worker, explorer or independent reviewer. Delegation moves bounded work and noisy output; it does not transfer final responsibility.

## Roles

- primary: user intent, scope, integration, final diff inspection, completion-critical validation and final response
- implementation worker: assigned implementation and local validation only
- explorer: read-only bounded discovery
- independent reviewer: must not be the author of the change it reviews

## Handoff contract

Send only what the delegate needs:

```text
Goal: <observable outcome>
Scope: <included files/components/behavior>
Out of scope: <nearby work to leave alone>
Constraints: <project, safety, compatibility, user choices>
Authority: <read/edit/test/commit permission>
Validation: <required checks/evidence>
Return: <changes, effect, raw results, skipped checks, uncertainty, blockers>
```

Resolve missing product decisions in the primary session.

## Resource defaults

Choose role first, then model, reasoning effort, service tier and history propagation.

1. bounded implementation worker: `gpt-5.6-luna` + Max + Fast when available and sufficient;
2. CRA reviewer: `gpt-6-astra` + Medium + default/non-Fast tier; `references/cra-loop.md` owns the exact invocation;
3. explorer: cheapest available model that can answer the bounded discovery question reliably.

Verify the launcher can express the selected settings when this matters. An example config is not runtime evidence.

## Context

Use the runtime default context for every role. Do not increase `model_context_window` or `model_auto_compact_token_limit`.

If a handoff does not fit:

1. remove duplicated instructions and irrelevant history;
2. bound recursive/generated tool output;
3. provide exact paths, diffs and evidence rather than making the delegate rediscover them;
4. split the work into coherent units;
5. use TCA only when those units are independently reviewable.

Prefer a self-contained handoff with no history or the smallest useful history subset.

## Execution rules

1. Use one write-capable worker for one coherent change.
2. One mutable worktree is a single-writer/stable-reader boundary. Serialize state-dependent readers or give them a fixed commit/separate worktree.
3. Under TCA, delegate only the active task unit.
4. A worker does not CRA-review its own implementation.
5. Inspect actual changes and completion-critical evidence after the worker returns.
6. If the worker finds a contradiction or materially larger scope, it stops and returns evidence instead of expanding silently.

## Return evidence

Require changed files, behavioral effect, commands actually run, exit status and useful raw output/artifact locations, skipped checks, uncertainty and blockers. Record model/effort/tier only when it matters to reproducibility.
