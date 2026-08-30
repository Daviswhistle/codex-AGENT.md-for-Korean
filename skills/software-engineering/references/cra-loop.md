# CRA Loop Reference

Use this reference when the user explicitly requests `CRA 루프`, TCA requires CRA, or the software-engineering skill selects CRA autonomously.

CRA means Commit-Review-Amend. It turns one completed task unit into a local commit, performs one complete first-pass review, records explicit review coverage as reusable units, and amends the same commit until the current commit has no unresolved substantive findings. After the first pass, CRA may reuse a prior clean conclusion only when its scope, dependencies, evidence, and applicable instructions remain unchanged. Every amendment delta is still reviewed in full for newly introduced defects.

## Entry Source

Before starting, record one reason for entering CRA:

1. `explicit-request`: the user requested CRA.
2. `tca-required`: the active TCA task requires CRA.
3. `autonomous-risk`: independent review is warranted under the software-engineering skill's risk criteria.

For `autonomous-risk`, record the concrete risk or uncertainty. A later user instruction to avoid commits or reviews overrides every entry source.

## Non-Negotiable Boundaries

1. CRA starts after one coherent task unit is implemented and locally verified as far as reasonably possible.
2. CRA requires one clean, non-merge task commit with a fixed single parent. That parent is the task boundary for every full or incremental pass.
3. A local commit is not approval to push, deploy, migrate, approve snapshots, update production data, or mutate remote state.
4. Exclude generated files, caches, logs, review logs, ledger files, secrets, credentials, and unrelated user or coworker changes from the commit.
5. Use CRA only for the requested task unit. Do not fold unrelated cleanup or follow-up work into the amend cycle.
6. Autonomous CRA may use the already-configured reviewer and the current account's existing usage. It may not purchase credits, change billing, plan, or quota settings, or switch provider or account without explicit user approval.
7. Do not use CRA as a substitute for missing local validation, and do not start when a clean task-unit commit cannot be isolated safely.
8. A review unit may be marked `clean` only when a completed reviewer output explicitly records coverage for that unit. Absence of a finding by itself is not reusable coverage.
9. Reusing a clean unit never exempts the amendment delta from review. Every change between the previous reviewed commit and the amended commit must be inspected for new defects.
10. When the impact of an amendment cannot be bounded confidently, discard the reuse decision and run another complete review of the task commit.

## Process State

Track the active review process in exactly one of these states:

1. `running`: the review process is still alive.
2. `completed-clean`: the completed pass has no substantive findings within its requested scope.
3. `completed-with-findings`: the completed pass has substantive findings.
4. `failed`: the review command, transport, auth, quota, model selection, or process execution failed.

Also record the pass kind:

1. `full`: reviews the complete task diff from the fixed task parent to the current commit.
2. `incremental`: reviews the complete amendment delta and every review unit invalidated by that delta.

Do not infer a terminal state from in-progress output. A `completed-clean` incremental pass is terminal only when the ledger also shows that every other unit remains valid through the current commit.

## Review Units

Before the first review, divide the task into the smallest useful set of independently invalidatable claims.

A review unit must contain:

1. a stable ID such as `U1`
2. a concrete claim or invariant
3. the code, tests, docs, config, data shape, or runtime path in scope
4. direct and transitive dependencies that could change the conclusion
5. current evidence, including relevant validation
6. conditions that invalidate the conclusion
7. applicable repository instructions when they materially support the claim or its review boundary

Good units describe behavior or an invariant, for example:

- an authorization decision cannot be bypassed through any changed caller
- a migration preserves existing data and has a recoverable failure path
- a public response schema remains compatible across its changed producer and consumers
- an installer never overwrites an existing target or exposes a partial target
- primary-session completion still requires independently checkable validation evidence

Do not use broad labels such as `security`, `performance`, `tests`, or `docs` without a concrete claim. Do not create one unit per file merely because files are easy to enumerate. Units may overlap when one change affects multiple invariants. A small task may use one unit.

Every changed behavior and directly connected caller, test, config, documentation, naming, or generated contract must belong to at least one unit. Cross-cutting risk that cannot be isolated safely is a reason to keep a larger unit or use full review, not a reason to omit coverage.

## Review Ledger

Keep the ledger outside the worktree so it cannot enter the task commit:

```bash
CRA_DIR="$(git rev-parse --git-path cra)"
LEDGER_PATH="$CRA_DIR/review-ledger.md"
mkdir -p "$CRA_DIR"
```

Use one ledger for the active task commit. At minimum record:

```text
Ledger version: 1
Entry source:
Task parent:
Current task commit:
Reviewer command and profile:
Effective context window:

Review units:
- ID:
  Claim:
  Scope:
  Dependencies:
  Evidence:
  Invalidate when:
  Applicable instructions:
  Status: clean | finding | invalidated | unknown
  Source reviewed SHA:
  Valid through SHA:
  Carry-forward reason:

Findings:
- ID:
  Unit:
  Status: open | fixed | rebutted | out-of-scope
  Evidence or fix:

Passes:
- Kind: full | incremental
  Previous reviewed SHA:
  Reviewed SHA:
  Delta status: not-applicable | clean | finding | unknown
  Requested units:
  Additional invalidations:
  Process state:
```

Ledger rules:

1. Create or update entries only from the current checkout, completed reviewer output, and current validation evidence.
2. `clean` means the reviewer explicitly covered the unit and no substantive finding remains for it.
3. `finding` means at least one valid or not-yet-adjudicated finding remains attached to the unit.
4. `invalidated` means a prior conclusion no longer applies because an amendment changed its scope, dependency, evidence, instruction, or invalidation trigger.
5. `unknown` means coverage was absent, malformed, incomplete, or could not be established. Treat `unknown` as requiring review.
6. `Source reviewed SHA` identifies the commit the reviewer actually inspected. `Valid through SHA` may advance only after conservative impact analysis shows that the unit was unaffected.
7. A carried unit must preserve the concrete reason its conclusion survives the amendment. Do not write only `unchanged`.
8. A rebutted finding needs current code, tests, docs, runtime evidence, or user instruction. If that evidence changes, invalidate the associated unit.
9. Never reuse a unit across a different task parent, a different task boundary, or a ledger whose provenance is uncertain.
10. The ledger is navigation and review evidence, not a substitute for inspecting the actual diff.

## Long-Context Compatibility

The review commands below request GPT-5.6 Sol's long-context profile. Codex resolves these values against the active model catalog rather than treating them as unconditional limits.

1. Before relying on the expanded budget, run `codex debug models` and inspect `gpt-5.6-sol`.
2. A long-context-capable catalog accepts `model_context_window=1000000` but clamps it to the advertised `max_context_window`; current upstream GPT-5.6 metadata caps this override at `872000`.
3. Older clients or catalogs may advertise `272000` or `372000`. They clamp the context request to that smaller ceiling, so CRA remains bounded but does not receive the intended long-context budget.
4. Codex also clamps the effective automatic-compaction threshold to at most 90% of the resolved context window, even when raw config output still shows `900000`.
5. If `max_context_window` is below `872000`, update and restart Codex and start a new CRA session. Report the effective runtime window instead of claiming that the long-context profile is active.

## Initial Full Review

Record the fixed task boundary:

```bash
TASK_PARENT="$(git rev-parse HEAD^)"
CURRENT_SHA="$(git rev-parse HEAD)"
test "$(git rev-list --parents -n 1 "$CURRENT_SHA" | wc -w)" -eq 2
```

The first pass must review the complete diff from `TASK_PARENT` to `CURRENT_SHA`. Render a custom review prompt with the exact SHAs and every review unit:

```text
Review the complete task change between parent <TASK_PARENT> and commit <CURRENT_SHA>.
Inspect `git diff <TASK_PARENT> <CURRENT_SHA>` in full and enough surrounding code, callers,
tests, config, docs, and runtime paths to identify every qualifying defect introduced by this task.

The numbered review units below are coverage claims, not limits on defect discovery.
Review every unit and continue through the complete diff after finding an issue.

<REVIEW UNITS FROM THE LEDGER>

Return ordinary findings using the review command's standard output contract.
In `overall_explanation`, append exactly one final sentence in this form:

Coverage: delta=not-applicable; U1=<clean|finding|unknown>; U2=<clean|finding|unknown>.

Use `clean` only after inspecting the unit's claim, scope, dependencies, and evidence and finding
no substantive issue. Use `finding` when one or more returned findings apply to the unit. Use
`unknown` when coverage could not be established. Do not suppress a defect because it crosses
units, and do not use a clean marker as a substitute for reporting a finding.
```

Run the custom review as a blocking batch:

```bash
CRA_DIR="$(git rev-parse --git-path cra)"
PROMPT_PATH="$CRA_DIR/review-prompt.md"
REVIEW_LOG="$CRA_DIR/review.log"
mkdir -p "$CRA_DIR"

if codex review - \
  -c model="gpt-5.6-sol" \
  -c model_reasoning_effort="max" \
  -c model_context_window=1000000 \
  -c model_auto_compact_token_limit=900000 \
  < "$PROMPT_PATH" >| "$REVIEW_LOG" 2>&1
then
  REVIEW_EXIT=0
else
  REVIEW_EXIT=$?
fi

echo "review_exit=$REVIEW_EXIT"
if [ "$REVIEW_EXIT" -eq 0 ]; then
  echo "review_command=completed"
else
  echo "review_command=failed"
fi
tail -100 "$REVIEW_LOG"
```

The `>|` output redirection intentionally truncates the fixed log before each run even when shell `noclobber` is enabled, and `codex review` blocks until the command exits. Use `REVIEW_EXIT` as the command completion signal rather than creating, deleting, or retaining a sentinel. A zero exit code establishes only that the review command completed; determine `completed-clean` or `completed-with-findings` from the completed output.

After completion:

1. verify the reviewed SHA and task parent still match the checkout
2. inspect all returned findings
3. parse the final `Coverage:` sentence into the ledger
4. mark a missing, duplicated, malformed, or incomplete unit status as `unknown`
5. require every initial unit to become `clean` or `finding` before incremental reuse is allowed
6. record the pass, reviewer profile, effective context, output location, and current validation evidence

If the installed CLI does not support a custom review prompt through `codex review -`, preserve the same blocking discipline and reviewer profile while switching only the review target:

```bash
if codex review --commit "$CURRENT_SHA" \
  -c model="gpt-5.6-sol" \
  -c model_reasoning_effort="max" \
  -c model_context_window=1000000 \
  -c model_auto_compact_token_limit=900000 \
  >| "$REVIEW_LOG" 2>&1
then
  REVIEW_EXIT=0
else
  REVIEW_EXIT=$?
fi

echo "review_exit=$REVIEW_EXIT"
if [ "$REVIEW_EXIT" -eq 0 ]; then
  echo "review_command=completed"
else
  echo "review_command=failed"
fi
tail -100 "$REVIEW_LOG"
```

That fallback may establish the process verdict and findings, but it does not create reusable clean units unless the completed output explicitly reports equivalent unit coverage. Without reusable coverage, run another full commit review after every amendment.

Do not replace review mode with an ordinary implementation session merely to obtain a different output shape. Use an alternative only when it is known to preserve the same provider and account, configured reviewer role and model, usage boundary, fixed commit scope, blocking completion, and review output.

## Amendment Impact Analysis

Before changing a reviewed commit, preserve its reviewed SHA in the ledger. After applying a valid fix, re-running local validation from the changed point, and amending the commit, compare the old and new commit objects:

```bash
PREVIOUS_REVIEWED_SHA="<sha from the last completed pass>"
CURRENT_SHA="$(git rev-parse HEAD)"

git diff --name-status "$PREVIOUS_REVIEWED_SHA" "$CURRENT_SHA"
git diff --stat "$PREVIOUS_REVIEWED_SHA" "$CURRENT_SHA"
git diff "$PREVIOUS_REVIEWED_SHA" "$CURRENT_SHA"
```

Classify every existing unit conservatively:

1. invalidate the unit that contained each fixed finding
2. invalidate a unit when its scoped code, test, doc, config, schema, data shape, runtime assumption, or evidence changed
3. invalidate a unit when any direct or transitive dependency that supported its conclusion changed
4. invalidate a unit when applicable repository instructions or the reviewer contract changed
5. create a new `unknown` unit for newly introduced behavior or a newly exposed invariant
6. carry a clean unit forward only when its scope, dependencies, evidence, and invalidation triggers remain unchanged in meaning
7. record a concrete carry-forward reason and advance `Valid through SHA` to `CURRENT_SHA`
8. when unsure whether a unit is affected, invalidate it
9. when the amendment's effects cannot be bounded without effectively rereading the whole task, run a full pass instead

File non-intersection is not sufficient proof. A changed producer can invalidate an unchanged consumer; a changed config can invalidate unchanged runtime code; a changed test can invalidate the evidence for unchanged implementation.

## Incremental Review

An incremental pass has two mandatory scopes:

1. the complete amendment delta from `PREVIOUS_REVIEWED_SHA` to `CURRENT_SHA`, inspected for any newly introduced defect
2. the current form of every `invalidated` or `unknown` unit, inspected against the complete task state from `TASK_PARENT` to `CURRENT_SHA`

Render a custom prompt. Before rendering it, include every field needed to challenge each carry-forward decision. A prior clean unit is not eligible for the carry-forward section when its claim, scope, dependencies, evidence, invalidation triggers, applicable instruction evidence, source reviewed SHA, valid-through SHA, or concrete carry-forward reason is missing or cannot be related confidently to the amendment; mark it `invalidated` or `unknown` instead.

```text
This is an incremental CRA review.

Fixed task parent: <TASK_PARENT>
Previous reviewed commit: <PREVIOUS_REVIEWED_SHA>
Current amended commit: <CURRENT_SHA>

First inspect `git diff <PREVIOUS_REVIEWED_SHA> <CURRENT_SHA>` in full for every defect introduced
by the amendment, including defects unrelated to the original findings. Then revalidate each
invalidated or unknown unit below against the current code and the complete task diff
`git diff <TASK_PARENT> <CURRENT_SHA>`.

Invalidated or unknown units:
<UNITS>

Open, fixed, or rebutted findings to verify:
<FINDINGS>

Carry-forward units:
<CLEAN UNITS WITH CLAIM, SCOPE, DEPENDENCIES, EVIDENCE, INVALIDATE WHEN,
APPLICABLE INSTRUCTIONS, SOURCE REVIEWED SHA, VALID THROUGH SHA, AND CARRY-FORWARD REASON>

Do not re-review a carry-forward unit merely for ceremony. Inspect enough context to determine
whether the amendment changed its claim, scope, dependencies, evidence, invalidation triggers,
or applicable instruction evidence. If it did, list that unit under `additional-invalidations`.

Return ordinary findings using the review command's standard output contract.
In `overall_explanation`, append exactly one final sentence in this form:

Coverage: delta=<clean|finding|unknown>; U1=<clean|finding|unknown>;
additional-invalidations=<none|U2,U3>.

`delta=clean` requires inspection of the complete amendment delta. A unit may be `clean` only
after its current claim, scope, dependencies, and evidence were revalidated. Use `unknown` when
coverage could not be established. Report every qualifying finding even when it belongs to a
previously clean or unlisted unit.
```

Run the same blocking command and reviewer profile as the initial pass.

After completion:

1. verify `HEAD`, `TASK_PARENT`, and the worktree did not change while the reviewer ran
2. require `delta=clean` or `delta=finding`; `delta=unknown` cannot close the loop
3. update each requested unit from explicit coverage
4. mark every `additional-invalidations` unit as `invalidated`
5. map new findings to an existing unit or create a new unit
6. carry all other prior clean units only when their recorded impact analysis remains valid
7. run another incremental pass for newly invalidated units, or reset to a full pass when the scope is no longer bounded

The reviewer may read surrounding unchanged code to understand the delta. Incremental review limits repeated adjudication, not access to necessary context.

## Full-Review Reset Conditions

Discard incremental reuse and run a new full pass when any of these is true:

1. the task parent changed through rebase, reset, merge, or commit restructuring
2. the task boundary expanded or unrelated work entered the commit
3. the ledger is missing, corrupt, internally inconsistent, or has uncertain provenance
4. the initial pass did not explicitly cover every unit
5. the reviewer prompt, applicable repository instructions, or review contract changed materially
6. a broad rename, move, refactor, dependency update, schema change, public contract change, migration, auth boundary, persisted-data path, concurrency model, recovery path, or runtime configuration change defeats reliable local invalidation
7. amendment impact cannot be bounded confidently
8. most useful units would need revalidation and a full pass is simpler or safer
9. the reviewer reports additional invalidations whose dependency chain cannot be isolated
10. the user requests a complete re-review

A full reset creates a new complete pass for the same fixed task parent and current commit. Rebuild or reconcile the units, but do not silently carry old clean statuses into the new pass.

## Log Discipline

1. Do not run the reviewer in the background with `&`.
2. Do not repeatedly tail the same log while the review is running.
3. Do not interpret partial output as a finding, coverage marker, pass, or failure.
4. If the process is still alive, keep the process state as `running`.
5. After process exit, inspect only the exit code, structured result, and the last 50-100 log lines unless debugging a failed review command requires more.
6. Keep prompts, logs, and the ledger under the Git path returned by `git rev-parse --git-path cra`; do not put them in the worktree.
7. Reuse the fixed prompt and log paths, and use `>|` for the log so shell `noclobber` cannot block intentional truncation. Do not create per-pass temporary directories or retain run artifacts unless the user or a specific debugging task explicitly requires history.

Review is a batch job, not a streaming conversation.

## Findings Handling

For each substantive finding after a completed pass:

1. verify the factual claim against the current checkout
2. decide whether it is in scope for the task unit
3. map it to a review unit or create a new unit
4. check runtime, data, security, user-facing, and maintenance risk
5. reject fixes that mask symptoms, appease tests, or create a larger regression
6. prefer fixes that improve code, tests, docs, config, generated contracts, and naming consistency together

If a finding is valid:

1. apply the smallest coherent fix
2. re-run local verification from the changed point
3. check `git status --short` and the relevant diff
4. preserve the current reviewed SHA in the ledger
5. amend the existing commit with `git commit --amend --no-edit`
6. perform amendment impact analysis
7. run an incremental or reset full pass as required

If a finding is invalid or out of scope, preserve a concise reason and current evidence in the ledger and final report. A rebutted finding may leave its unit clean only when the review coverage was explicit and no other unresolved finding remains for that unit. If the rebuttal evidence later changes, invalidate the unit.

## Stop Conditions

Stop the CRA loop only when one of these is true:

1. `HEAD` equals the ledger's current task commit, the latest amendment delta is explicitly clean or no amendment followed the latest full pass, every unit is `clean` and valid through `HEAD`, and no valid finding remains open.
2. Every remaining finding is explicitly rebutted with current code, tests, docs, runtime evidence, or user instruction; all associated units remain valid through `HEAD`.
3. Incremental reuse was unavailable, and the last completed full commit review of the current `HEAD` reports no substantive findings or only explicitly rebuttable findings.
4. The review flow failed in a way that cannot be corrected inside the current task; report the failure, exact command, exit signal, stale or unknown units, and remaining risk.

Do not finish CRA while a review process is running, while `delta=unknown`, or while any unit is `invalidated`, `unknown`, stale, or attached to an unresolved valid finding.

## Final Report

Report:

1. entry source and autonomous risk rationale when applicable
2. fixed task parent and final commit hash
3. changed files and behavioral effect
4. validation commands run
5. skipped validation with reasons
6. reviewer command, profile, and effective context
7. full and incremental pass count
8. last review process state and delta status
9. review units newly reviewed, revalidated, carried forward, invalidated, or reset
10. accepted findings and fixes
11. rejected or rebutted findings with reasons and evidence
12. full-review reset reasons, when applicable
13. remaining risk
14. naming, docs, generated-contract, or file-movement rationale when relevant
