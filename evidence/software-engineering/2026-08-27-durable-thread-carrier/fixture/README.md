# Executable fixture

Every carrier-routing case uses the same bounded code change from `task.md`.
`setup.py` creates a clean primary repository, a deliberately mismatched worktree,
and state paths for the active-writer barrier. `verify.py` provides an independent
task oracle; `apply_reference.py` exists only to self-test that oracle.

Run the following from the parent evidence directory
`evidence/software-engineering/2026-08-27-durable-thread-carrier/`:

```bash
RUN_PARENT="$(mktemp -d)"
RUN_DIR="$RUN_PARENT/carrier-fixture"
python3 fixture/setup.py --root "$RUN_DIR"
! python3 fixture/verify.py --repo "$RUN_DIR/repo"
python3 fixture/apply_reference.py --repo "$RUN_DIR/repo"
python3 fixture/verify.py --repo "$RUN_DIR/repo"
python3 fixture/teardown.py --root "$RUN_DIR"
rm -rf "$RUN_PARENT"
```

`controller.md` fixes the baseline/candidate session isolation, state setup, failure
injection, trace capture, and teardown contract. Passing this fixture self-test proves
only that the repository task and oracle are executable; it is not carrier behavior
evidence.
