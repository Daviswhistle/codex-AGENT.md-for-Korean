# Executable fixture

Every carrier-routing case uses the same bounded code change from `task.md`.
`setup.py` creates a clean primary repository, a deliberately mismatched worktree,
and state paths for the active-writer barrier. `verify.py` provides an independent
task oracle; `apply_reference.py` exists only to self-test that oracle.

Fixture self-test:

```bash
RUN_DIR="$(mktemp -d)/carrier-fixture"
python3 fixture/setup.py --root "$RUN_DIR"
test ! python3 fixture/verify.py --repo "$RUN_DIR/repo"
python3 fixture/apply_reference.py --repo "$RUN_DIR/repo"
python3 fixture/verify.py --repo "$RUN_DIR/repo"
python3 fixture/teardown.py --root "$RUN_DIR"
```

`controller.md` fixes the baseline/candidate session isolation, state setup, failure
injection, trace capture, and teardown contract. Passing this fixture self-test proves
only that the repository task and oracle are executable; it is not carrier behavior
evidence.
