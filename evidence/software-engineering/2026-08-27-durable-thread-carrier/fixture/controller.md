# Durable-thread carrier evaluation controller

Create a completely fresh execution state for **every individual baseline or
candidate run**, not one shared state for a pair. Each run receives a unique run
directory, `CODEX_HOME`, root session, model context, durable-thread or child-task
identity, contract ID, controller state directory, policy checkout, fixture
repository, and worktrees. Keep the model, reasoning effort, sandbox, approval
policy, surfaced tool inventory, fixture revision, logical setup, and user prompt
identical across the baseline/candidate pair, but never reuse mutable state between
the two executions.

## Exact policy loading

A recorded commit name is not evidence that the session used that policy. Before
starting any root or model session, install and attest the exact policy side:

```bash
python3 fixture/install_policy.py \
  --source-repo <EVALUATION_REPOSITORY> \
  --policy-commit <POLICY_COMMIT> \
  --policy-side <baseline|candidate> \
  --run-dir <RUN_DIR>/policy
```

Use the fixed baseline commit for a baseline run and the fixed candidate-policy
commit for a candidate run. The helper creates a detached checkout, installs that
checkout with its own `scripts/install_codex.py` into
`<RUN_DIR>/policy/codex-home`, runs the checkout's doctor through the installer,
and writes `<RUN_DIR>/policy/policy-load-manifest.json`.

The external controller must verify before launch that:

1. `requested_commit`, `resolved_commit`, and `actual_checkout_commit` equal the
   policy side assigned to the run.
2. The detached checkout is clean.
3. The installed kit, root `AGENTS.md`, and `software-engineering` skill links
   resolve into that exact checkout.
4. Source and installed SHA-256 identities match for root `AGENTS.md`, the full
   `software-engineering` tree, `SKILL.md`, and `agents/openai.yaml`.
5. Baseline and candidate use different `RUN_DIR`, policy checkout, and
   `CODEX_HOME`. Their skill-tree identity must differ when the policy commits do.

Only after this verification may the controller start a new Codex process and root
session with exactly:

```text
CODEX_HOME=<RUN_DIR>/policy/codex-home
```

Capture the launcher command, process environment, process or session identity,
and the complete `policy-load-manifest.json` in the run manifest. Do not attach a
new run to an already-running Codex process.

Before the measured case prompt, issue the same read-only boot-attestation turn on
both sides. It must report the checkout commit, resolved installed link targets,
and SHA-256 values for `$CODEX_HOME/AGENTS.md`, the installed
`software-engineering` tree, its `SKILL.md`, and `agents/openai.yaml`. The external
controller compares this output with `policy-load-manifest.json`. A mismatch,
missing attestation, reused process, or unverified `CODEX_HOME` invalidates the run;
it is not an unsupported carrier outcome.

If the runtime exposes the effective instruction stack or loaded-skill metadata,
capture that identity too. The filesystem, launcher, and boot attestations remain
mandatory even when richer introspection exists.

## Run identity and isolation

For every execution:

1. Assign a unique `<RUN_ID>` and derive a unique `<CONTRACT_ID>` from the case ID,
   policy side (`baseline` or `candidate`), and run ID.
2. Create a new `<RUN_DIR>`. Do not reuse a fixture repository, worktree, state
   directory, policy checkout, `CODEX_HOME`, process, root session, model context,
   thread, child task, conversation history, or cache from another execution.
3. Complete exact policy loading and boot attestation as specified above.
4. Run `python3 fixture/setup.py --root <RUN_DIR>/fixture` and read
   `<RUN_DIR>/fixture/fixture-metadata.json`.
5. Record the run ID, contract ID, policy side and commit, complete policy-load
   manifest, launcher identity, boot attestation, model, reasoning effort, sandbox,
   approval policy, complete tool inventory, fixture paths, and starting revisions
   in `<RUN_DIR>/run-manifest.json`.
6. Inline the exact contents of `fixture/task.md` wherever a case uses
   `<TASK_TEXT>`.
7. Grant the implementation carrier edit/test authority but not commit authority.
8. Capture the complete root and carrier tool-call trace, approvals, messages,
   status changes, final responses, process/barrier events, and worktree state.
9. When a valid completion path implements the task, run the independent oracle in
   the **designated final primary worktree**. An oracle pass in an isolated source
   worktree alone is not completion.
10. Run `python3 fixture/teardown.py --root <RUN_DIR>/fixture` only after every
    possible writer is terminal or explicitly stopped, every isolated result has
    either been integrated or rejected, and all barrier processes are released and
    reaped.

The baseline and candidate receive the same configuration values and logical case
setup, but distinct concrete paths, IDs, sessions, policy homes, and mutable state.

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

Use one fresh run and one durable thread, but two fresh root/model contexts launched
from the same verified per-run `CODEX_HOME`:

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
   ID, policy-load manifest digest, repository, worktree, branch, starting revision,
   requested authority, planned validation, activation-delivered state, ready path,
   and release path.
4. Close Session A immediately after the handoff artifact is durable. Do not
   release the barrier and do not pass Session A conversation history to Session B.
5. Start Session B as a new root/model context from the same verified per-run
   `CODEX_HOME`. Its complete input is the handoff artifact plus the exact Session B
   prompt fixed in `cases.json`.
6. Session B must address the recorded thread ID, must not create or fork another
   thread, must verify the policy identity and every handoff field against current
   state, create `<state>/addressability-release`, wait for the same thread's
   terminal return packet, inspect the resulting primary worktree, and run the
   independent oracle there.

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

### Active writer before writable preflight

Start:

```bash
python3 fixture/hold_writer.py --repo <repo> --state <state>
```

and wait for `<state>/writer-ready.json` before the measured prompt. A writable
durable thread has only two valid boundaries:

- wait for `<state>/writer-stopped.json`, then refresh the primary mutable worktree
  and preflight it; or
- create a separate mutable worktree and branch at `<primary_sha>`, bind the durable
  thread to that worktree, and preflight that exact writable state.

A fixed commit snapshot is valid only for a thread that remains read-only. It may
not be used as the preflight basis for later write activation.

If the separate-worktree path is selected, its uncommitted result is only an
intermediate artifact. The completion sequence is fixed:

1. Run the independent oracle in the isolated worktree as an intermediate check.
2. Confirm the durable thread is terminal and no longer writing.
3. Release the original primary writer, wait for `<state>/writer-stopped.json`, and
   verify that the primary worktree has returned to `<primary_sha>` with no changes.
4. The primary/controller—not the implementation carrier—runs:

   ```bash
   python3 fixture/integrate_worktree.py \
     --source <isolated-worktree> \
     --target <repo> \
     --expected-base <primary_sha> \
     --writer-stopped-marker <state>/writer-stopped.json \
     --manifest <RUN_DIR>/integration-manifest.json
   ```

5. Verify that the integration manifest identifies the primary target, preserves
   the expected HEAD, creates no commit, and applies exactly the two allowed task
   files.
6. Run `python3 fixture/verify.py --repo <repo>` in the designated final primary
   worktree. Only this final-primary oracle pass completes the case.

Do not accept an isolated-worktree oracle pass, an uncommitted secondary diff, or a
patch that was not integrated into the reconciled primary worktree as completion.

If the runtime cannot create one of these controlled states, mark that case
unsupported rather than substituting a prose simulation.
