# CRA Loop Reference

CRA means Commit-Review-Amend. Use it after one coherent task unit is locally validated when independent commit-level review is required by the user, TCA, or the software-engineering risk criteria.

## Defaults

Use these defaults unless the user explicitly chooses another profile or Astra is unavailable:

- reviewer: `gpt-6-astra`
- reasoning effort: `medium`
- service tier: standard
- context: runtime default; this kit does not request an expanded context window or raised auto-compaction limit

Astra is more expensive per token than Sol, so this is a quality-per-review default, not a claim of lower token price. If the task cannot be reviewed safely within the default context, reduce the evidence packet or split the task before review; do not silently enlarge context.

## Boundaries

1. Start only after local validation and a clean, non-merge task commit with one fixed parent.
2. Exclude unrelated changes, secrets, generated files, caches, logs, and review bookkeeping from the commit.
3. A local commit is not permission to push, deploy, migrate, or mutate remote state.
4. The first pass reviews the complete task diff. Every amendment delta is reviewed in full.
5. Reuse an earlier clean conclusion only when its claim, dependencies, evidence, and applicable instructions remain unchanged. Uncertainty means re-review.
6. CRA never substitutes for missing local validation.

## Compact Review Record

Store the active record outside the worktree under `$(git rev-parse --git-path cra)` so it cannot enter the commit. Keep only information needed to continue the current loop:

```text
Task parent:
Current commit:
Reviewer: gpt-6-astra / medium / standard / default-context

Units:
- U1: <claim>; scope=<paths/contracts>; status=<clean|finding|invalidated|unknown>; valid-through=<sha>

Findings:
- F1: <unit>; status=<open|fixed|rebutted|out-of-scope>; evidence=<short note>

Passes:
- <full|incremental>; from=<sha>; to=<sha>; result=<clean|finding|unknown>
```

Do not retain this record as repository history after the task. It is active-loop state, not product documentation.

## Initial Review

Fix the boundary:

```bash
TASK_PARENT="$(git rev-parse HEAD^)"
CURRENT_SHA="$(git rev-parse HEAD)"
test "$(git rev-list --parents -n 1 "$CURRENT_SHA" | wc -w)" -eq 2
```

Define the smallest useful claim-based units covering every changed behavior and directly connected caller, test, config, document, schema, or public contract. A small task may use one unit. Do not create one unit per file merely because files are easy to enumerate.

Render a prompt containing the exact parent/current SHAs, complete diff target, units, applicable instructions, relevant validation evidence, and unresolved risks. Ask the reviewer to inspect the complete task diff and return ordinary findings plus one compact coverage line such as:

```text
Coverage: U1=clean; U2=finding.
```

Run the blocking review with the cost profile fixed explicitly:

```bash
CRA_DIR="$(git rev-parse --git-path cra)"
PROMPT_PATH="$CRA_DIR/review-prompt.md"
REVIEW_LOG="$CRA_DIR/review.log"
mkdir -p "$CRA_DIR"

CRA_REVIEW_MODEL="${CRA_REVIEW_MODEL:-gpt-6-astra}"
CRA_REVIEW_EFFORT="${CRA_REVIEW_EFFORT:-medium}"

CRA_REVIEW_ARGS=(
  -c "model=$CRA_REVIEW_MODEL"
  -c "model_reasoning_effort=$CRA_REVIEW_EFFORT"
  -c service_tier=default
  -c features.fast_mode=false
)

if codex review - "${CRA_REVIEW_ARGS[@]}" \
  < "$PROMPT_PATH" >| "$REVIEW_LOG" 2>&1
then
  REVIEW_EXIT=0
else
  REVIEW_EXIT=$?
fi

echo "review_exit=$REVIEW_EXIT"
tail -100 "$REVIEW_LOG"
```

No context-window or auto-compaction override belongs in `CRA_REVIEW_ARGS`.

A zero exit code means the command completed, not that the review is clean. Parse the completed findings and coverage. Missing or ambiguous unit coverage becomes `unknown`.

If the installed CLI does not support `codex review -`, use the same profile with `codex review --commit "$CURRENT_SHA"`. Without explicit unit coverage, a later amendment must receive another full review rather than reusing clean units.

## Amendments

For every accepted finding:

1. fix only the task-relevant defect
2. rerun the closest affected validation
3. amend the same task commit
4. inspect `git diff <previous-reviewed-sha> <current-sha>` in full
5. invalidate any unit whose scope, dependency, evidence, or applicable instruction changed
6. add a new `unknown` unit for newly introduced behavior

File non-intersection is not proof that a unit remains valid. Changed producers, config, tests, or shared dependencies may invalidate unchanged files.

## Incremental Review

An incremental pass must inspect:

1. the complete amendment delta for newly introduced defects
2. every invalidated or unknown unit against the current task state

Pass the fixed task parent, previous reviewed SHA, current SHA, amendment delta target, invalidated units, relevant findings, and any carry-forward units with a concrete reason they remain valid. Ask for a compact line such as:

```text
Coverage: delta=clean; U1=clean; additional-invalidations=none.
```

`delta=unknown` cannot close the loop. Any additional invalidation must be reviewed before completion. If impact cannot be bounded confidently, run a full task-commit review instead.

## Stop Conditions

`completed-clean` requires all of the following:

1. local validation applicable to the current commit passes or limitations are disclosed
2. the latest review command completed successfully
3. the complete initial task diff was reviewed
4. every amendment delta was reviewed
5. no substantive open finding remains
6. every active unit is clean through the current SHA
7. `HEAD`, task parent, and worktree still match the reviewed state

If review fails because of auth, quota, model availability, command support, or transport, report the failure and remaining risk. Do not weaken the profile or claim a clean review silently.
