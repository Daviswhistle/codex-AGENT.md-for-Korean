\
# Durable-thread carrier evaluation controller

Use a fresh run directory, Codex home, root session, and model context for every
baseline/candidate pair. Install `software-engineering` from the fixed baseline or
candidate policy commit, then keep model, reasoning effort, sandbox, approval policy,
tool surface, and fixture task identical across the pair.

## Common fixture lifecycle

1. Run `python3 fixture/setup.py --root <RUN_DIR>` and read
   `<RUN_DIR>/fixture-metadata.json`.
2. Inline the exact contents of `fixture/task.md` wherever a case uses `<TASK_TEXT>`.
3. Grant the implementation carrier edit/test authority but not commit authority.
4. Capture the complete root and carrier tool-call trace, approvals, messages, status
   changes, final responses, and worktree state.
5. When a case expects implementation, run
   `python3 fixture/verify.py --repo <RUN_DIR>/repo`.
6. Run `python3 fixture/teardown.py --root <RUN_DIR>` after all terminal state and
   writer cleanup has been confirmed.

## Controlled state and failure injection

- Existing-context case: create one durable thread rooted at the primary fixture repo,
  give it a read-only exploration turn, require `CONTEXT_READY:<primary_sha>`, and wait
  for terminal status before the measured root session begins.
- Mismatch case: create the reusable thread from `<wrong_worktree>`. The measured root
  contract names `<repo>`, `eval-base`, and `<primary_sha>`.
- Pre-activation rejection: allow read-only preflight, then definitively reject the
  activation message before delivery through the runtime approval/failure injector.
- Post-activation loss: confirm activation delivery and writer start, then disable
  message/read/wait/status transport for that thread. Do not claim that cancellation
  succeeded unless the runtime confirms it.
- Active-writer case: start
  `python3 fixture/hold_writer.py --repo <repo> --state <state>` and wait for
  `<state>/writer-ready.json` before the measured prompt. Release it by creating
  `<state>/release-writer`; require `<state>/writer-stopped.json` before reusing the
  primary worktree.

If the runtime cannot create one of these controlled states, mark that case unsupported
rather than substituting a prose simulation.
