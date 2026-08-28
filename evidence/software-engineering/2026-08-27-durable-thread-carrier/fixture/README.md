# Executable fixture

Every carrier-routing case uses the same bounded code change from `task.md`.
`setup.py` creates a clean primary repository, a deliberately mismatched worktree,
and state paths for controlled writer conditions. `verify.py` provides an
independent task oracle; `apply_reference.py` exists only to self-test that oracle.
`thread_barrier.py` provides a controller-released synchronization point that keeps
an activated durable writer non-terminal during cross-session handoff and
post-activation transport-loss injection.

Run the following from the parent evidence directory
`evidence/software-engineering/2026-08-27-durable-thread-carrier/`:

```bash
RUN_PARENT="$(mktemp -d)"
RUN_DIR="$RUN_PARENT/carrier-fixture"
python3 fixture/setup.py --root "$RUN_DIR"
! python3 fixture/verify.py --repo "$RUN_DIR/repo"
python3 fixture/apply_reference.py --repo "$RUN_DIR/repo"
python3 fixture/verify.py --repo "$RUN_DIR/repo"

python3 fixture/thread_barrier.py \
  --state "$RUN_DIR/state" --name selftest --timeout-seconds 30 &
BARRIER_PID=$!
until test -f "$RUN_DIR/state/selftest-ready.json"; do sleep 0.05; done
touch "$RUN_DIR/state/selftest-release"
wait "$BARRIER_PID"
test -f "$RUN_DIR/state/selftest-released.json"

python3 fixture/teardown.py --root "$RUN_DIR"
rmdir "$RUN_PARENT"
```

`controller.md` fixes per-execution baseline/candidate isolation, state setup,
failure injection, exact cross-session handoff, trace capture, and teardown.
Passing this fixture self-test proves only that the repository task, oracle, and
barrier are executable; it is not carrier behavior evidence.
