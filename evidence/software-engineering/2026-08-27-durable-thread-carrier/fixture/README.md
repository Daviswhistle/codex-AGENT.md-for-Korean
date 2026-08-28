# Executable v6 fixture

Every case uses the bounded change in `task.md`. `setup.py` creates:

- a clean mutable primary worktree on `eval-base`;
- dormant implementation-capable matching and mismatch roles whose setup turns are
  read-only, with the mismatch on a different revision/branch and deliberately dirty;
- a detached fixed snapshot used with an actual `read-only` app-server sandbox;
- controller state paths for barriers and the external writer;
- an executable, byte-identical run-local copy at `<fixture-root>/thread_barrier.py`,
  recorded as the absolute `barrier_script` in fixture metadata.

`inspect_binding.py` emits machine-readable Git path/worktree/Git-dir identity,
branch or detached state, HEAD, status and digest, staged/unstaged/untracked paths,
refs, reflog, and worktree-list digests. It can compare a final observation with a
starting artifact to enforce exact edit paths, empty staging, and unchanged
HEAD/branch/refs/reflog/worktree-list.

`verify.py` is the independent task oracle. `hold_writer.py` and the run-local
`metadata.barrier_script` copy establish real live-writer conditions. The source
`fixture/thread_barrier.py` is never the per-run execution path. `integrate_worktree.py`
remains available for a separately allocated mutable boundary, though the ten v6
primary cases use the designated primary worktree.

Run the fixture v6 self-test from the repository root:

```bash
EVIDENCE="evidence/software-engineering/2026-08-27-durable-thread-carrier"
RUN_PARENT="$(mktemp -d)"
python3 "$EVIDENCE/fixture/self_test.py" \
  --root "$RUN_PARENT/carrier-fixture" \
  --source-repo "$(git rev-parse --show-toplevel)" \
  --runner "$(git rev-parse --show-toplevel)/$EVIDENCE/fixture/run_evaluation.py" \
  --baseline-commit aa2ae97856d7968e50511864c03f1babcd608d0d \
  --candidate-commit a7056f2469b1b8c6ae8cb996f4624e9c333205cd
rmdir "$RUN_PARENT"
```

The self-test proves fixture mechanics only:

- clean, dirty-mismatch, and detached binding observations;
- stable status sampling;
- exact policy-install identities for baseline and candidate;
- definitive versus ambiguous dispatch classification;
- `commandActions` normalization for wrapped, simple, compound exact-test, and
  forbidden-Git examples, plus classification of only actual Python barrier
  execution while `find`/`sed` reads remain read-only;
- v0.150.1 `gitInfo=null` acceptance only when all required cwd/workspace/idle/actual
  binding evidence matches, plus rejection of surfaced mismatched Git identity;
- terminal-turn plus idle-thread reconciliation truth table;
- allowed uncommitted edits pass while worktree-list or commit/ref/reflog drift fails;
- active-writer integration is rejected until the writer stops;
- the run-local barrier matches the source hash and executable mode, remains live
  until controller release, records ready/released, and does not time out;
- addressability permits the two observed compound `sed` control-plane reads and
  exact release marker while rejecting repository paths, mutation-capable commands,
  redirection, and pipelines during the live writer interval;
- the tracked execution-harness identity has a complete portable file inventory,
  equal start/end values, a reproducible canonical aggregate, and tamper detection;
- final-primary integration/oracle and teardown work.

It does not run a model or prove carrier behavior. The runtime evaluation is a
controller-hosted app-server compatibility surface, not stock TUI approval E2E.
`controller.md` defines lifecycle validity, failure injection, reconciliation,
grading, and the publication allowlist.

## Tracked execution and grading SSOT

Run behavioral evaluations only with `fixture/run_evaluation.py` and grade them
only with `fixture/grade_runs.py`. The old work-directory scripts are exploratory
compatibility wrappers, not evidence inputs. `self_test.py` defaults to the tracked
runner; if `--runner` is supplied, it must resolve to that exact file.

The execution-harness aggregate contains exactly these evidence-root-relative files:

- `cases.json`;
- `fixture/run_evaluation.py`;
- `fixture/task.md`;
- `fixture/install_policy.py`;
- `fixture/setup.py`;
- `fixture/inspect_binding.py`;
- `fixture/hold_writer.py`;
- `fixture/thread_barrier.py`;
- `fixture/verify.py`;
- `fixture/teardown.py`.

Each entry records its portable relative path, exact byte size, and SHA-256. A
canonical JSON encoding of the sorted entries produces `execution_harness_sha256`.
The runner records complete start and end identities plus source-repository identity
in `result.json`; any change makes the run harness-invalid. `fixture/self_test.py`,
`fixture/README.md`, `fixture/controller.md`, and `fixture/grade_runs.py` do not
affect model execution and are intentionally outside the aggregate. The grader has
its own separately reported self SHA-256, so later grading-only fixes do not rewrite
the historical behavioral identity.

A fully explicit single-run invocation is:

```bash
python3 "$EVIDENCE/fixture/run_evaluation.py" \
  --case SE-BOUNDED-CHILD-CONTROL \
  --side candidate \
  --source-repo "$(git rev-parse --show-toplevel)" \
  --run-root /absolute/path/to/final-primary-20 \
  --codex "$(command -v codex)" \
  --auth-source "${CODEX_HOME:-$HOME/.codex}/auth.json" \
  --model gpt-5.6-luna \
  --effort high
```

`--run-root` is always required. Without overrides, the source repository and
evidence root derive from the tracked script location, the Codex executable comes
from `PATH`, and auth is read from current `CODEX_HOME/auth.json` then
`~/.codex/auth.json`. Auth is copied only into the raw per-run `CODEX_HOME`; it is
never publication-allowlisted. Grade a frozen manifest with:

```bash
python3 "$EVIDENCE/fixture/grade_runs.py" \
  --manifest /absolute/path/to/behavior-run-manifest.json
```

The manifest must contain top-level `execution_harness_sha256`. Every included
primary or replicate result must carry the same complete and stable identity, and
the grader also recomputes the tracked checkout when it is available.

## Final-run replacement boundary

The eight runs already present in the pre-identity `primary-20` directory are
exploratory and excluded from the final manifest. The final twenty runs are fresh
ten-case baseline/candidate pairs sharing one `execution_harness_sha256`. An
infrastructure or harness-invalid execution may be rerun once from fresh state;
preserve both executions and record the excluded run and exact reason. A valid
behavioral failure is not rerun or replaced. Model noncompliance that prevents a
required injection remains the primary `invalid-or-unsupported` result; another
run may not be cherry-picked in its place.
