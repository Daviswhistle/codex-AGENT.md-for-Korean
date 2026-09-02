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
6. independent verification of completion-critical validation
7. final completion judgment and reporting

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
Validation: <commands and independently checkable evidence required>
Completion evidence: <diff, tests, reproduction, generated output, or docs>
Return: <changed files, behavioral effect, raw validation evidence, skipped checks, uncertainty, blockers>
```

Do not delegate an ambiguous outcome and expect the worker to infer the missing product decision. Resolve the decision in the primary session or assign a read-only exploration task first.

Before choosing agent resources, the primary session should perform deterministic preparation that does not require the delegate's independent judgment: resolve the exact snapshot and diff, identify known files and required callers, collect validation and runtime metadata, and constrain commands that could emit large recursive, binary, generated, cache, or session-log output. Give an expensive reviewer a bounded evidence packet and unresolved claims to challenge. The reviewer must still verify completion-critical claims and may widen inspection when it finds a concrete reason; independence does not require paying it to rediscover every path mechanically.

## Pre-Dispatch Resource Selection

Before starting a worker, explorer, or reviewer, make the choice in this order:

1. **Role:** decide whether the needed output is bounded implementation, read-only exploration, or independent review. Do not use a generic `worker` label for work whose authority or independence is materially different.
2. **Model:** choose for the role, consequence of error, task difficulty, and required independence. A stronger reviewer may be justified for agent authority, money, security, recovery, deployment, or a broad public contract; that does not make the same model the default implementation worker.
3. **Reasoning effort:** choose after the model from the complexity and ambiguity of the assigned task. Do not inherit the parent's effort merely because the conversation is convenient to copy.
4. **Service tier:** choose from latency value, current usage cost, and runtime support. Fast is permitted for a Luna Max implementation worker when faster execution is worth its extra usage, but it is optional and does not become the reviewer default.
5. **Context window:** estimate the peak live context from the prompt, instructions, diff, evidence packet, likely reasoning, and expected tool output—not from diff size alone. Prefer peak-input and compaction telemetry from the closest analogous run when available. Use the smallest window with material headroom after first reducing avoidable output; request an expanded window when the estimate is uncertain or approaches the ordinary effective limit. Before launch, record the request plus its catalog-clamped nominal limit and leave the runtime-effective limit pending until launch metadata reports it.
6. **Context propagation or fork:** only after the first five choices, decide how much prior conversation to pass. Model allocation and history propagation are independent axes.

Record the decision before invocation:

```text
Role: <worker|explorer|independent reviewer>
Model: <selected model>
Reasoning effort: <selected effort>
Service tier: <standard|Fast/priority|deliberately inherited supported tier>
Context window: <requested value; catalog-clamped nominal limit; runtime-effective limit>
Context propagation: explicit <none|recent N turns|full history|independent prompt>
Launcher/profile: <invocation path that expresses the selected resources>
Evidence budget: <packet scope; expected dynamic output; analogous peak/compaction evidence or none; remaining headroom>
Rationale: <role, risk, scope, evidence volume, latency, and cost that changed the choice>
```

In runtimes whose full-history fork inherits the parent model and reasoning effort and does not accept overrides, omitting `fork_turns` is the same as selecting `fork_turns=all`. Always pass the field explicitly. Use `all` only when that exact inheritance is intentional. A custom `worker.toml` does not retroactively change the model of such an invocation. When the selected model or effort differs from the parent, use `fork_turns=none` or the smallest sufficient positive turn count and provide a self-contained execution contract. Never select full history merely to avoid writing the handoff.

After making the record, inspect the chosen launcher's actual fields, inherited user/project configuration, and active named-agent configuration. A selection is not active merely because the user allowed it or a repository example contains it. If the launcher cannot express the selected service tier or context override, either use a compatible launcher or revise the record to the deliberately inherited profile before starting. In particular, a full-history fork does not by itself prove that an expanded context window was requested, and an explicit model override does not prove that Fast was enabled.

Treat the current catalog's `fast` request and `priority` runtime ID as the same accelerated Fast tier and apply the same cost and authorization decision to both. To select the standard tier despite inherited configuration, use a launcher that can explicitly set `service_tier=default` and disable `features.fast_mode`; omission means inheritance, not standard. Likewise, distinguish the requested context, the catalog-clamped nominal limit, and the smaller runtime-effective limit reported by `task_started.model_context_window`. Do not call a nominal catalog limit effective. Record the final model, effort, normalized tier, and runtime-effective context from launch metadata or other direct evidence.

If the runtime exposes different fork or custom-agent semantics, inspect that active contract before invoking and preserve the same decision order. The same model may still receive different context choices for different tasks; a small bounded high-risk review can deliberately use a strong model with its ordinary context, while a broad lower-risk repository analysis may need more context.

After completion, record the runtime-effective window, peak per-request input, whether compaction occurred, and any unexpected high-volume command. Use this telemetry for the next analogous selection; cumulative cached input across requests is cost evidence, not the peak live-context measure.

## Execution Rules

1. For a non-trivial coherent software change, use one write-capable `worker` by default when the execution contract is precise and subagents are available.
2. Read applicable root and project instructions before editing. Include any task-specific constraint that may not be obvious from those files.
3. Treat one mutable worktree as a single-writer, stable-reader boundary. While a worker is writing, do not run any repository-state-dependent explorer, reviewer, validator, or other agent against that worktree. Wait for the writer to finish or give the reader a separate worktree or fixed commit snapshot. Read-only access prevents writes, not mixed-state observations.
4. Under TCA, delegate only the active task unit. Wait for its implementation, local validation, commit boundary, and CRA gate before starting the next task.
5. Do not ask the worker to run CRA on its own implementation. Independent review remains a separate primary-session workflow.
6. A worker summary is navigation, not proof. Inspect `git status`, the relevant diff, changed files, and independently checkable validation evidence before accepting the task.
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
3. validation commands, exit status, and relevant raw output or stable artifact location
4. skipped validation and reasons
5. repository-state or diff concerns
6. remaining uncertainty
7. blockers, contradictions, or valuable out-of-scope opportunities

The primary session must independently verify every validation result needed for completion. Re-run the command or inspect independently accessible raw output, exit status, and artifacts. If only the worker's prose summary is available, re-run the validation. Lower-value checks may be sampled proportionate to risk, but required checks cannot be accepted solely on the worker's claim.

## Optional Luna Max + Fast Example

`references/worker-luna-max-fast.toml` is an opt-in custom-agent example, not a normative model assignment and not an installer-managed file. It overrides the built-in `worker` with GPT-5.6 Luna, Max reasoning, workspace-write sandboxing, and the Fast service tier.

Use the example only after the pre-dispatch record selects that worker profile. Its presence affects named-worker discovery; it does not override a full-history invocation whose runtime contract explicitly inherits the parent model and effort.

If the active spawn API does not expose service-tier controls, a bare explicit Luna model override is not evidence of Fast. Use this named profile only when it is actually installed and selected, or use another authorized launcher that exposes and reports the tier. Otherwise inspect the inherited user, project, named-agent, and parent settings before launch, record the tier as deliberately inherited, and confirm it from launch metadata; never infer either Fast or standard merely from the missing control.

Current Codex releases discover standalone custom-agent files under `~/.codex/agents/` for personal agents and `.codex/agents/` for project agents. No `[agents.worker]` or `config_file` registration is required. The `name = "worker"` field is the source of truth and makes the custom agent take precedence over the built-in role.

After installing the skill, a user may copy the example into the personal custom-agent directory. The example stages and fsyncs a complete file in the target directory, then publishes it atomically without replacing an existing `worker.toml`. If the target already exists or the filesystem cannot provide no-clobber hard-link publication, it stops without changing the target:

```bash
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
SOURCE="$CODEX_DIR/skills/software-engineering/references/worker-luna-max-fast.toml"
TARGET="$CODEX_DIR/agents/worker.toml"

mkdir -p "$CODEX_DIR/agents"

python3 - "$SOURCE" "$TARGET" <<'PY'
from pathlib import Path
import os
import shutil
import sys
import tempfile

source = Path(sys.argv[1])
target = Path(sys.argv[2])

with source.open("rb") as src:
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())

        try:
            os.link(temp, target)
        except FileExistsError:
            raise SystemExit(
                f"refusing to overwrite existing custom agent: {target}\n"
                "inspect, merge, rename, or back it up explicitly"
            )
        except OSError as exc:
            raise SystemExit(
                f"cannot atomically publish custom agent: {exc}\n"
                f"target left unchanged: {target}"
            ) from exc
    finally:
        temp.unlink(missing_ok=True)
PY
```

Restart Codex or start a new session after changing custom-agent configuration.

Before relying on the profile, inspect the active model catalog and confirm that `gpt-5.6-luna` advertises the requested reasoning effort and Fast tier. If the current catalog or account does not support either setting, choose an advertised effort or tier rather than claiming the example is active.

Fast is a service tier, not a different model. It increases supported-model speed and consumes usage at a higher rate. The example enables it with both `service_tier = "fast"` and `[features].fast_mode = true`.
