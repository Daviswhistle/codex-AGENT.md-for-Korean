# Worker Delegation Reference

Use this reference when a software task will be implemented, explored, or reviewed by a subagent. Delegation moves bounded work and noisy output out of the primary context; it does not transfer final responsibility.

## Roles

The primary session owns user intent, task/workflow boundaries, integration, final diff inspection, completion-critical validation, and the final response.

A bounded worker owns only the assigned implementation and local validation. An explorer is read-only. An independent reviewer must not be the author of the change it reviews.

## Execution Contract

Send only what the delegate needs:

```text
Goal: <observable outcome>
Scope: <included files/components/behavior>
Out of scope: <nearby work to leave alone>
Constraints: <project, safety, compatibility, user choices>
Authority: <read/edit/test/commit permission>
Validation: <required checks and evidence>
Return: <changes, effect, raw results, skipped checks, uncertainty, blockers>
```

Resolve missing product decisions in the primary session. Use read-only exploration first when a precise implementation contract cannot yet be written.

## Resource Defaults

Choose in this order: role, model, reasoning effort, service tier, history propagation.

1. Bounded implementation worker: first candidate `gpt-5.6-luna`, Max effort, Fast tier when available and sufficient.
2. Independent CRA reviewer: `gpt-6-astra`, Medium effort, standard tier by default; CRA owns the exact invocation contract.
3. Explorer: choose the cheapest model that can answer the bounded discovery question reliably.
4. Escalate a role only for a concrete quality reason: task ambiguity, consequence of error, difficult reasoning, or insufficient prior result.
5. Do not infer active settings from an example file or omitted option. Verify the launcher can express the selected model/effort/tier and inspect runtime metadata when material.

### Context policy

Use the runtime's default context window for every role. Do not set a larger `model_context_window` or `model_auto_compact_token_limit` in this kit.

If a handoff does not fit comfortably:

1. remove duplicated instructions and irrelevant history
2. bound recursive or generated tool output
3. give exact paths, diffs, and evidence instead of asking the delegate to rediscover them
4. split exploration or implementation into coherent units
5. for code changes, use TCA when a large task has safe independently reviewable boundaries

Do not solve a context-budget problem by silently paying for expanded context.

Choose history propagation after the role profile is fixed. Prefer a self-contained handoff with no history or the smallest useful recent-turn subset. Use full history only when the launcher semantics and task genuinely require it; never use full history merely to avoid writing the contract.

## Execution Rules

1. For a non-trivial coherent change, use one write-capable worker when the contract is precise and delegation adds value.
2. Treat one mutable worktree as a single-writer/stable-reader boundary. While a writer is active, do not run a repository-state-dependent reader against the same changing worktree.
3. Under TCA, delegate only the active task unit and finish its validation and CRA before the next unit.
4. The worker does not run CRA on its own implementation.
5. A worker summary is navigation, not proof. Inspect the diff and independently check completion-critical evidence.
6. If the worker finds a contradiction or materially larger scope, it stops and returns evidence rather than expanding silently.

## Direct Fallback

Implement directly when the change is trivial, execution cannot be separated from a live user/product decision, subagents are unavailable, or recovery after a failed handoff is safer than another delegation.

## Return Evidence

Require changed files, behavioral effect, commands actually run, exit status and useful raw output or artifact locations, skipped checks, uncertainty, and blockers. Record model/effort/tier when it matters to reproducibility. Default-context use does not require a separate telemetry ledger unless a concrete context failure occurred.
