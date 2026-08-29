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
- independent raw-wrapper auditing of every `commandExecution`, including rejection
  of an unpermitted `touch`, arbitrary Python or heredoc writes, shell redirection,
  remote `curl` mutation, combined `sort -T/path`, lookalike executables,
  noncanonical shell wrappers, attacker-controlled `git -C`, parenthesized
  state-capable commands from the wrong/fixed worktree, wrong cwd, and incomplete,
  out-of-order, status-invalid, or mismatched start/completion pairs even if
  `commandActions` claims a harmless read;
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
- complete-JSON nonzero grader exits for malformed nested manifest/result data,
  duplicate/non-finite JSON, missing/stale grading identity, and over-limit JSONL
  physical records, plus identity binding and deterministic gzip evidence that are
  regraded through subprocesses, with substitutions of the one frozen-invalid
  run ID/result hash/raw-trace hash rejected;
- publication roundtrip plus absolute/parent/symlink/missing/hash/duplicate/inode
  alias, concurrent-mutation, existing-output, incomplete-inventory, embedded
  camel/flat/snake/kebab JSON/JSONL credential, escaped credential syntax inside
  decoded JSON strings, password/passphrase and Authorization/API-key secrets
  across Markdown/text/log/patch formats, quoted chunk-boundary values, late
  staged-gzip mutation, duplicate-key, non-finite JSON, decompression-size,
  long-record, 100,001-record, and global-size counterexamples, with raw
  `CODEX_HOME` authentication material excluded;
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
`fixture/README.md`, `fixture/controller.md`, `fixture/evidence_contract.py`,
`fixture/grade_runs.py`, and `fixture/publish_evidence.py` do not affect model
execution and are intentionally
outside the aggregate. A separate deterministic grading-harness identity covers
exactly `fixture/evidence_contract.py`, `fixture/grade_runs.py`, and
`fixture/publish_evidence.py`, recording each exact byte size and SHA-256 plus a
canonical aggregate. A gradeable behavior manifest binds
`grading_harness_sha256` to that aggregate, and the grader compares it with the
current three-file identity before reading any run. Grader and publisher reports
also include the complete identity, so grading/publication semantics are verified
without changing the historical execution-harness identity.

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
never publication-allowlisted. Historical raw manifests contain only the frozen
execution identity. Create a new, identity-bound manifest copy, then grade it:

```bash
BOUND_PARENT="$(mktemp -d)"
BOUND_MANIFEST="$BOUND_PARENT/behavior-run-manifest.json"
python3 "$EVIDENCE/fixture/publish_evidence.py" \
  --manifest /absolute/path/to/raw/behavior-run-manifest.json \
  --bind-output "$BOUND_MANIFEST"
python3 "$EVIDENCE/fixture/grade_runs.py" \
  --manifest "$BOUND_MANIFEST"
```

The binder exclusively creates one new file, resolves raw relative run directories
against the source manifest, and never rewrites the historical source. A gradeable
manifest must contain both top-level `execution_harness_sha256` and
`grading_harness_sha256`. Every included primary or replicate result must carry the
same complete and stable execution identity, and the grader also recomputes the
tracked checkout when it is available. A missing or stale grading identity fails
before run grading. The grader always writes one complete JSON report. It exits
nonzero for manifest/artifact invalidity outside the frozen expected baseline
outcome, or for any candidate fail or invalid outcome; the frozen set exits zero
even though its recorded baseline addressability run remains intentionally
`invalid-or-unsupported`. That exception is bound to primary run
`b-2df65-35161c0` and its exact manifest result/raw-trace hashes as well as its
case, side, replicate, and invalid reasons; an identity substitution exits nonzero.

The grader independently parses the raw `/bin/*sh -c` payload for every
paired `commandExecution`; missing or mismatched starts/completions fail, and
`commandActions` is not an authority oracle. Only the exact test,
fixture-owned binding/verification/attestation/barrier commands, case-bound state
markers, narrowly proven inert failed probes, and a closed read-only shell/Git grammar
with exact bare executable tokens and command-specific frozen fixture/worktree cwd
allowlists are accepted. Start/completion identity, lifecycle status, exit code,
event order, raw command, and cwd must agree. Command tokens determine state-capable
cwd requirements even inside parentheses, and `git -C` is evaluated at its effective
target with wrong/fixed worktrees allowed only for their matching cases. Lookalike
executable paths, unclassified Python, network clients, Git mutation, write-capable
redirection, and unrecognized commands fail the runtime-boundary assertion.

To make the frozen run set clone-regradable without copying its raw directories,
publish only the per-run `publish-manifest.json` allowlists:

```bash
PUBLISH_PARENT="$(mktemp -d)"
PUBLISHED="$PUBLISH_PARENT/evidence"
python3 "$EVIDENCE/fixture/publish_evidence.py" \
  --manifest "$BOUND_MANIFEST" \
  --output "$PUBLISHED"
python3 "$EVIDENCE/fixture/grade_runs.py" \
  --manifest "$PUBLISHED/behavior-run-manifest.json"
```

The publisher requires an exact schema-v6 behavior manifest with one unique primary
run for every ten-case baseline/candidate pair. It accepts an otherwise exact legacy
source manifest only to add the current grading identity to its new output; an
already-bound mismatch fails. It verifies full manifest identity, unique
run-directory filesystem identities, and exact `result.json`/raw-trace hash linkage
before publication. The output path must not exist: files are built under a private
sibling staging directory with exclusive, no-follow descriptors. Each file's exact
stored and uncompressed size/SHA-256 is recorded after creation. After the final
inventory walk, every staged file is reopened through the staging descriptor, its
stored bytes are rechecked, and every gzip is decompressed again and matched to the
recorded original identity before one atomic no-replace rename. Failure removes
staging and never replaces or leaves a partial destination.

Only exact relative entries from each `publish-manifest.json` are considered.
Absolute, parent-traversing, noncanonical, duplicated, symlinked, missing,
non-allowlisted, or hash/size-mismatched entries fail closed. Every JSON artifact is
strictly bounded-parsed and structurally scanned for folded snake-, kebab-, camel-,
or flat-form credential keys; duplicate object keys and non-finite JSON numbers are
rejected. Every decoded JSON string value receives the same credential-pattern scan,
so JSON escaping cannot hide password/passphrase, Basic, bearer, or API-key syntax.
Every JSONL record is strictly parsed and scanned, and remaining text uses an
overlap-preserving credential pattern scan. Text scanning recognizes assigned
password/passphrase keys including embedded snake/kebab forms, plus Basic, bearer,
and API-key authorization forms; it triggers at the first nonempty value byte rather
than waiting for a closing quote. Value-free documentation remains allowed, while
credential detection aborts publication.
Decompressed input is limited to 512 MiB per artifact, 1.25 GiB for the complete
20-run publication, 8 MiB per JSONL physical record, 100,000 physical JSONL records
including blank records, and 64 MiB for structured JSON. The grader applies the same
bounds when reading plain or `<path>.gz` artifacts and verifies the declared
uncompressed size and SHA-256.
The publisher never walks or copies the raw directory wholesale, so `auth.json` and
the rest of per-run `CODEX_HOME` remain outside published evidence.

## Final-run replacement boundary

The eight runs already present in the pre-identity `primary-20` directory are
exploratory and excluded from the final manifest. The final twenty runs are fresh
ten-case baseline/candidate pairs sharing one `execution_harness_sha256`. An
infrastructure or harness-invalid execution may be rerun once from fresh state;
preserve both executions and record the excluded run and exact reason. A valid
behavioral failure is not rerun or replaced. Model noncompliance that prevents a
required injection remains the primary `invalid-or-unsupported` result; another
run may not be cherry-picked in its place.
