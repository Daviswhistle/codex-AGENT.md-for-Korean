# Worker Delegation Reference

Use this reference when a software task will be implemented or locally validated by a subagent.

The purpose of delegation is to keep requirement interpretation, workflow decisions, and final verification in the primary session while moving bounded execution and noisy tool output into an isolated worker context. Delegation does not transfer final responsibility.

## Role Boundary

The primary session owns:

1. the user's purpose, constraints, and desired final state
2. TCA and CRA selection
3. task and commit boundaries
4. the execution contract sent to the worker
5. inspection of actual changes and validation evidence
6. final completion judgment and reporting

The worker owns:

1. investigation needed to execute the bounded task
2. implementation inside the stated scope
3. local validation appropriate to the changed contract
4. inspection of its own working-tree changes
5. a precise return report

The worker does not independently redefine product intent, widen scope, select TCA or CRA, accept its own work as complete, push, deploy, migrate, purchase, or mutate remote state.

## Execution Contract

Send a contract with this shape:

```text
Goal: <one observable outcome>
Scope: <files, components, behavior, or task unit included>
Out of scope: <nearby work that must remain untouched>
Constraints: <project instructions, compatibility, safety, user choices>
Authority: <edit/test permissions; whether local commit is allowed>
Validation: <commands or evidence required>
Completion evidence: <diff, tests, reproduction, generated output, or docs>
Return: <changed files, behavioral effect, validation, skipped checks, uncertainty, blockers>
```

Do not delegate an ambiguous outcome and expect the worker to infer the missing product decision. Resolve the decision in the primary session or assign a read-only exploration task first.

## Execution Rules

1. For a non-trivial coherent software change, use one write-capable `worker` by default when the execution contract is precise and subagents are available.
2. Read applicable root and project instructions before editing. Include any task-specific constraint that may not be obvious from those files.
3. Keep one write-capable worker per worktree. Parallel agents in the same worktree should be read-only unless the edits are isolated by separate worktrees.
4. Under TCA, delegate only the active task unit. Wait for its implementation, local validation, commit boundary, and CRA gate before starting the next task.
5. Do not ask the worker to run CRA on its own implementation. Independent review remains a separate primary-session workflow.
6. A worker summary is navigation, not proof. Inspect `git status`, the relevant diff, changed files, and validation output before accepting the task.
7. If the worker discovers a contradiction, hidden dependency, or materially larger scope, it should stop and return the evidence instead of silently expanding the task.

## Direct-Execution Fallbacks

The primary session may implement directly when:

1. the change is trivial and delegation overhead would exceed its value
2. execution cannot be separated from a live user or product decision
3. no usable subagent is available
4. unrelated working-tree changes prevent a safe handoff
5. a failed delegation leaves a smaller and safer direct recovery path

A direct fallback does not weaken the validation or CRA/TCA criteria.

## Return Evidence

Require the worker to return:

1. behavioral result
2. changed files and why each changed
3. validation commands and exact outcomes
4. skipped validation and reasons
5. repository-state or diff concerns
6. remaining uncertainty
7. blockers, contradictions, or valuable out-of-scope opportunities

The primary session should independently verify the evidence proportionate to risk. At minimum, inspect the final diff and repository state. Re-run critical validation when the worker's environment, output, or confidence is insufficient.

## Optional Luna Max + Fast Example

`references/worker-luna-max-fast.toml` is an opt-in custom-agent example, not a normative model assignment and not an installer-managed file. It overrides the built-in `worker` with GPT-5.6 Luna, Max reasoning, workspace-write sandboxing, and the Fast service tier.

After installing the skill, a user may copy it into the personal custom-agent directory:

```bash
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_DIR/agents"
cp "$CODEX_DIR/skills/software-engineering/references/worker-luna-max-fast.toml" \
  "$CODEX_DIR/agents/worker.toml"
```

Restart Codex or start a new session after changing custom-agent configuration.

Before relying on the profile, inspect the active model catalog and confirm that `gpt-5.6-luna` advertises the requested reasoning effort and Fast tier. If the current catalog or account does not support either setting, choose an advertised effort or tier rather than claiming the example is active.

Fast is a service tier, not a different model. It increases supported-model speed and consumes usage at a higher rate. The example enables it with both `service_tier = "fast"` and `[features].fast_mode = true`.
