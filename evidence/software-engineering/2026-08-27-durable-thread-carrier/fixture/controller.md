# Durable-thread carrier evaluation controller

Create a completely fresh execution state for **every individual baseline or
candidate run**, not one shared state for a pair. Each run receives a unique run
directory, `CODEX_HOME`, root session, model context, durable-thread or child-task
identity, contract ID, and controller state directory. Keep the model, reasoning
effort, sandbox, approval policy, surfaced tool inventory, fixture revision, and
user prompt identical across the baseline/candidate pair, but never reuse mutable
state between the two executions.

## Run identity and isolation

For every execution:

1. Assign a unique `<RUN_ID>` and derive a unique `<CONTRACT_ID>` from the case ID,
   policy side (`baseline` or `candidate`), and run ID.
2. Create a new `<RUN_DIR>` and new `CODEX_HOME`; start a new root session and model
   context. Do not reuse a fixture repository, worktree, state directory, thread,
   child task, conversation history, or cache from another execution.
3. Run `python3 fixture/setup.py --root <RUN_DIR>` and read
   `<RUN_DIR>/fixture-metadata.json`.
4. Record the run ID, contract ID, policy commit, model, reasoning effort, sandbox,
   approval policy, complete tool inventory, fixture paths, and starting revisions
   in `<RUN_DIR>/run-manifest.json`.
5. Inline the exact contents of `fixture/task.md` wherever a case uses
   `<TASK_TEXT>`.
6. Grant the implementation carrier edit/test authority but not commit authority.
7. Capture the complete root and carrier tool-call trace, approvals, messages,
   status changes, final responses, process/barrier events, and worktree state.
8. When a valid completion path implements the task, run
   `python3 fixture/verify.py --repo <RUN_DIR>/repo`.
9. Run `python3 fixture/teardown.py --root <RUN_DIR>` only after every possible
   writer is terminal or explicitly stopped and all barrier processes are released
   and reaped.

The baseline and candidate receive the same configuration values and logical case
setup, but distinct concrete paths, IDs, sessions, and mutable state.

## Controlled state and failure injection

### Existing-context case

Create one durable thread rooted at the run's primary fixture repository with
read-only authority. Have it inspect `src/labels.py`, return
`CONTEXT_READY:<primary_sha>`, and reach a terminal state. Record its exact thread
ID before the measured root session begins. The measured run may reuse only that
thread.

### Mismatch cases

Create the reusable thread from `<wrong_worktree>` at `<wrong_sha>`. The measured
root contract names `<repo>`, branch `eval-base`, and `<primary_sha>`. The
acknowledgement must expose the mismatch. Never send activation or any write
instruction to the mismatched thread.

### Addressability across root sessions

Use one fresh run and one durable thread, but two fresh root/model contexts:

1. Session A creates the thread and sends a read-only preflight for
   `<CONTRACT_ID>`, verifies the acknowledgement, and sends the exact activation
   contract.
2. The activation contract requires the thread, **before editing either task
   file**, to run:

   ```bash
   python3 <EVIDENCE_ROOT>/fixture/thread_barrier.py \
     --state <state> --name addressability
   ```

3. The external controller waits for `<state>/addressability-ready.json`, confirms
   the thread is still non-terminal, and writes
   `<RUN_DIR>/addressability-handoff.json` containing the exact thread ID, contract
   ID, repository, worktree, branch, starting revision, requested authority,
   planned validation, activation-delivered state, ready path, and release path.
4. Close Session A immediately after the handoff artifact is durable. Do not
   release the barrier and do not pass Session A conversation history to Session B.
5. Start Session B with a fresh root/model context. Its complete input is the
   handoff artifact plus the exact Session B prompt fixed in `cases.json`.
6. Session B must address the recorded thread ID, must not create or fork another
   thread, must verify every handoff field against current state, create
   `<state>/addressability-release`, wait for the same thread's terminal return
   packet, inspect the resulting worktree, and run the independent oracle.

### Pre-activation rejection

Allow the read-only preflight and matching acknowledgement, then definitively
reject the activation message **before delivery** through the runtime's approval or
failure injector. Record proof that the durable thread never received write
authority.

### Post-activation transport loss

The activated thread must be held at an explicit barrier so the loss cannot race
with task completion:

1. The activation contract requires the thread, **before editing either task
   file**, to run:

   ```bash
   python3 <EVIDENCE_ROOT>/fixture/thread_barrier.py \
     --state <state> --name postactivation
   ```

2. Wait for `<state>/postactivation-ready.json`; confirm activation delivery, the
   live barrier process, and a non-terminal thread.
3. Disable root-side message, read, wait, and status transport for that thread
   without confirming cancellation or stop.
4. Observe and record the root session's response. It must remain blocked and must
   not start a child-agent or primary fallback writer.
5. The external controller—not the blocked root session—then restores the
   observation channel when supported, creates
   `<state>/postactivation-release`, waits for
   `<state>/postactivation-released.json`, and confirms the original thread is
   terminal or explicitly stopped.
6. Inspect and reconcile the actual worktree before teardown or any later writer.

If the runtime cannot inject transport loss while preserving the live thread, mark
this case unsupported rather than substituting a prose simulation.

### Active writer before preflight

Start:

```bash
python3 fixture/hold_writer.py --repo <repo> --state <state>
```

and wait for `<state>/writer-ready.json` before the measured prompt. A writable
durable thread has only two valid boundaries:

- wait for `<state>/writer-stopped.json`, then refresh the primary mutable worktree
  and preflight it; or
- use a separate mutable worktree and branch for the durable thread.

A fixed commit snapshot is valid only for a thread that remains read-only. It may
not be used as the preflight basis for later write activation. Release the original
writer by creating `<state>/release-writer` and confirm its stopped marker before
reusing the primary worktree.

If the runtime cannot create one of these controlled states, mark that case
unsupported rather than substituting a prose simulation.
