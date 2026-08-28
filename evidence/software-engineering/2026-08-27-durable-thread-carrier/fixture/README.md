# Executable fixture

Every carrier-routing case uses the same bounded code change from `task.md`.
`setup.py` creates a clean primary repository, a deliberately mismatched worktree,
and state paths for controlled writer conditions. `verify.py` provides an
independent task oracle; `apply_reference.py` exists only to self-test that oracle.

`install_policy.py` creates an exact detached baseline or candidate checkout,
installs that checkout into a fresh `CODEX_HOME`, and records verifiable root and
`software-engineering` skill identities. `integrate_worktree.py` transfers the
allowed uncommitted task diff from an isolated writable worktree into a stopped,
reconciled primary worktree without creating a commit. `thread_barrier.py` provides
a controller-released synchronization point that keeps an activated durable writer
non-terminal during cross-session handoff and post-activation transport-loss
injection.

Run the full fixture v5 self-test from the repository root:

```bash
EVIDENCE="evidence/software-engineering/2026-08-27-durable-thread-carrier"
RUN_PARENT="$(mktemp -d)"
python3 "$EVIDENCE/fixture/self_test.py" \
  --root "$RUN_PARENT/carrier-fixture" \
  --source-repo "$(git rev-parse --show-toplevel)" \
  --baseline-commit aa2ae97856d7968e50511864c03f1babcd608d0d \
  --candidate-commit 4a87005223d235dc29873fbe602445617a52decb
rmdir "$RUN_PARENT"
```

The self-test proves the following executable harness properties:

- the unimplemented fixture repository fails the independent oracle
- the baseline and candidate policy commits are installed into different fresh
  homes and produce attestable, different `software-engineering` identities
- an isolated reference implementation passes its local oracle
- integration is rejected while the primary writer is active
- after writer termination, the isolated diff is applied to the designated primary
  worktree without a commit and the primary oracle passes
- the controller barrier reaches ready and released terminal states
- teardown removes the isolated run state

`controller.md` fixes per-execution policy loading, baseline/candidate isolation,
state setup, failure injection, exact cross-session handoff, trace capture, final
primary-worktree integration, and teardown. Passing this fixture self-test proves
only that the harness and its oracles are executable; it is not carrier behavior
evidence.
