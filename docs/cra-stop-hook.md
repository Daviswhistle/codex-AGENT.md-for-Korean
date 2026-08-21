# CRA Stop Hook

The CRA Stop hook makes Commit-Review-Amend a runtime completion condition instead of a prompt-only convention.

## Architecture

```text
implement + validate + one local commit
                  |
          cra_gate.py arm
                  |
       agent attempts to stop
                  |
          Codex Stop hook
                  |
  independent codex exec review --commit SHA
          /                     \
       clean                  findings
         |                       |
    allow stop          block + continuation
                                 |
                      verify, fix, validate,
                      amend the same commit
                                 |
                          next Stop review
```

The reviewer is a new `codex exec review` thread. It does not receive the implementing agent's conversation history. `DAVIS_CRA_REVIEWER=1` prevents the reviewer process from recursively invoking the same gate.

## Install

From the kit checkout, or from the path installed under `CODEX_HOME`:

```bash
python3 scripts/cra_gate.py install-hook
python3 scripts/cra_gate.py doctor-hook
```

Installation performs a structural merge into `${CODEX_HOME:-$HOME/.codex}/hooks.json`:

- existing hooks and unrelated top-level fields are preserved
- exactly one managed `SessionStart` handler and one managed `Stop` handler are installed
- rerunning the command is idempotent
- malformed existing JSON is rejected without overwrite
- the previous file is copied to `hooks.json.bak` before replacement

Codex does not execute an untrusted user or project hook. Review the changed hook configuration, trust it in Codex, and start a new session. `SessionStart` writes a heartbeat outside the repository. CRA refuses to arm without a recent heartbeat, preventing a silent no-review exit when a hook is installed but inactive.

## Commands

```bash
# Arm current HEAD after local validation and commit
python3 scripts/cra_gate.py arm \
  --entry-source explicit-request \
  --commit "$(git rev-parse HEAD)"

# Inspect the durable state
python3 scripts/cra_gate.py status --json

# Record an evidence-backed rebuttal to the current review
python3 scripts/cra_gate.py rebut \
  --commit "$(git rev-parse HEAD)" \
  --reason "The reported path is unreachable because ...; covered by test_x."

# Clear a stale/abandoned state explicitly
python3 scripts/cra_gate.py clear --reason "task was cancelled by the user"

# Remove only the managed CRA handlers
python3 scripts/cra_gate.py uninstall-hook
```

`--entry-source autonomous-risk` additionally requires `--risk`.

## State and Boundary Safety

State is stored under `${CODEX_HOME:-$HOME/.codex}/state/davis-agent-kit/cra`, never in the target repository. It is keyed by canonical repository path and Codex thread/session identity, written atomically, and guarded by a file lock.

The armed task commit's parent set defines the boundary. A normal `git commit --amend --no-edit` changes the SHA while preserving that parent set. A second commit does not, so the gate blocks it. Merge commits are not accepted as CRA task units.

A dirty worktree also blocks Stop. This prevents a reviewer from assessing an obsolete commit while uncommitted fixes exist.

## Review Contract

The gate invokes:

```bash
codex exec --ephemeral \
  -c model='"gpt-5.6-sol"' \
  -c model_reasoning_effort='"max"' \
  --output-last-message <temporary-file> \
  review --commit <sha>
```

Environment overrides are available for controlled compatibility testing:

- `DAVIS_CRA_CODEX_BIN`
- `DAVIS_CRA_REVIEW_MODEL`
- `DAVIS_CRA_REVIEW_REASONING_EFFORT`
- `DAVIS_CRA_REVIEW_TIMEOUT_SECONDS`
- `DAVIS_CRA_MAX_REVIEW_FAILURES`
- `DAVIS_CRA_MAX_REASON_CHARS`

A valid terminal result must be a JSON object with a `findings` array, `overall_correctness`, and `overall_explanation`. Invalid or partial output is a reviewer failure, never a clean result.

## Failure Policy

The first reviewer failure blocks Stop and returns diagnostics. A second failure on the same SHA fails open. This bounded retry prevents a bad login, quota exhaustion, model-access problem, transport error, or incompatible CLI from creating an infinite Stop loop. `status --json` retains the failure for the final report.

## Subagents

Subagents are useful as optional additional reviewers, but not as the CRA enforcement primitive. Current multi-agent V2 defaults to full parent-turn inheritance when `fork_turns` is omitted. A reviewer subagent must explicitly use `fork_turns="none"` and receive a compact task contract plus exact commit SHA.

The independent Stop-gate review remains authoritative because it is fresh-context, commit-scoped, structured, and able to control whether the parent turn actually ends.
