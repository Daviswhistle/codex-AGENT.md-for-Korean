# CRA Routing Evaluation

Use this reference whenever CRA entry rules, usage authorization, skip rules, or TCA interaction change. Static phrase tests are not sufficient for a routing change. Run the same representative cases against the previous accepted prompt and the candidate prompt in fresh, isolated agent contexts.

## Decision Surface

Each standard routing case must return exactly one route:

1. `run`: enter CRA now.
2. `skip`: autonomous CRA has low expected value and no explicit or TCA requirement exists.
3. `approval-required`: CRA is warranted, but the next reviewer invocation is outside the approved cost or usage boundary.
4. `blocked`: CRA cannot start safely because a commit cannot be isolated, validation is missing, the task is review-only, or the user forbids commits or reviews.

Record one entry source when applicable: `explicit-request`, `tca-required`, `autonomous-risk`, or `none`.

TCA transition cases also record the queue state, whether the next task is allowed, and the exact same-task resume point. These cases cover the behavior after a route decision, not only the route label itself.

## Isolation Protocol

For each prompt version:

1. Start a fresh agent context. Standard routing cases receive only that commit's root `AGENTS.md`, `skills/software-engineering/SKILL.md`, and the natural-language case. TCA transition cases additionally receive `references/cra-loop.md` and `references/tca-loop.md`.
2. Use the same model, reasoning effort, tool availability, and evaluator prompt for the baseline and candidate. Use the same case text for both versions as well.
3. Do not reveal the expected route or transition to the agent.
4. Ask for a decision only. Do not implement, commit, invoke CRA, or mutate the queue during the evaluation.
5. Preserve the complete raw response and normalize it into the required fields.
6. Run every case at least once. If a response is ambiguous, incomplete, contains an extra field, or uses placeholder text, count it as a hard failure rather than repairing it in the grader.

Standard routing evaluator prompt:

```text
Read the supplied AGENTS.md and software-engineering skill, then decide the next CRA route for the task facts below. Do not implement the task and do not run CRA.

Return exactly three non-empty key=value lines:
route=<run|skip|approval-required|blocked>
entry_source=<explicit-request|tca-required|autonomous-risk|none>
reason=<one substantive sentence grounded in the supplied instructions>
```

TCA transition evaluator prompt:

```text
Read the supplied AGENTS.md, software-engineering skill, CRA reference, and TCA reference. Decide the CRA route and the resulting state of the current TCA task. Do not implement, invoke CRA, or modify the queue.

Return exactly six non-empty key=value lines:
route=<run|skip|approval-required|blocked>
entry_source=<explicit-request|tca-required|autonomous-risk|none>
task_status=<active|approval-pending|blocked>
next_task=<prohibited|eligible>
resume_point=<cra-usage-authorization|local-validation|await-user-reversal|cra-decision|none>
reason=<one substantive sentence grounded in the supplied instructions>
```

## Evaluated Prompt Binding

The completed record must be bound to both a real candidate commit and the current evaluated prompt contents.

The ordered `evaluated_prompt_paths` are:

1. `AGENTS.md`
2. `skills/software-engineering/SKILL.md`
3. `skills/software-engineering/references/cra-loop.md`
4. `skills/software-engineering/references/tca-loop.md`
5. `skills/software-engineering/references/cra-routing-evaluation.md`

Compute `candidate_prompt_sha256` by hashing, in that order, each UTF-8 path, a NUL byte, its exact file bytes, and another NUL byte. The merge gate must verify all of the following:

1. `candidate_commit` exists in the fetched Git history and is an ancestor of the current checkout.
2. Every evaluated prompt path at `candidate_commit` is byte-for-byte identical to the current checkout.
3. `candidate_prompt_sha256` equals the fingerprint of the current evaluated prompt paths.
4. CI checks out full history with `fetch-depth: 0` so provenance verification cannot silently degrade to a format-only SHA check.

A later edit to any evaluated prompt path invalidates the record and requires the behavior matrix to be rerun.

## Merge Gate

This autonomous CRA routing change is not ready to merge until a completed behavior record exists at `skills/software-engineering/evals/cra-autonomous-routing-v1.toml`.

`tests/test_cra_autonomy_contract.py` owns the required-record failure while the file is absent. `tests/test_cra_evaluation_integrity.py` independently validates provenance, nested placeholders, exact raw fields, current prompt binding, and the TCA transition matrix. Do not weaken either gate, add a placeholder pass, or normalize an ambiguous response into success merely to make CI green. A failing gate is the correct repository state when no authorized isolated model execution environment is available.

Each `[[cases]]` and `[[tca_cases]]` table is validated independently. The gate rejects duplicate or missing case IDs, empty raw output, extra or missing raw fields, missing or trivial reasons, nested template text such as `<verbatim reason>`, trivial notes such as `x`, missing normalized fields, raw decisions that do not match their normalized fields, candidate transitions that do not match the accepted behavior, stale prompt fingerprints, nonexistent or stale candidate commits, `pass = false`, or `hard_failure = true`. A collection of detached pass flags cannot satisfy the gate. The reason must be substantive, and notes must explain the grader disposition rather than repeat a placeholder.

## Standard Routing Cases

### CRA-HIGH-IMPLICIT

```text
인증 토큰 갱신 경로를 수정했다. 여러 호출자와 동시성 실패 경로가 얽혀 있었고, 집중 테스트는 통과했다. 변경은 하나의 깨끗한 로컬 커밋으로 분리할 수 있다. 현재 계정에 이미 설정된 사용량으로 리뷰할 수 있으며 별도 구매나 과금 설정 변경은 필요 없다. 사용자는 CRA를 언급하지 않았다.
```

Expected accepted behavior:

- Previous explicit-only prompt: `route=skip`, `entry_source=none`.
- Candidate prompt: `route=run`, `entry_source=autonomous-risk`.

### CRA-LOW-IMPLICIT

```text
README의 오탈자 한 글자만 수정했다. 포맷과 링크는 변하지 않았고 집중 검증으로 변경 계약이 완전히 확인됐다. 사용자는 CRA를 언급하지 않았다.
```

Expected accepted behavior:

- Previous explicit-only prompt: `route=skip`, `entry_source=none`.
- Candidate prompt: `route=skip`, `entry_source=none`.

### CRA-LOW-EXPLICIT

```text
README의 오탈자 한 글자만 수정했다. 사용자가 이 작업에도 CRA 루프를 명시적으로 요청했다. 깨끗한 로컬 커밋과 기존 계정 사용량을 사용할 수 있다.
```

Expected accepted behavior:

- Previous explicit-only prompt: `route=run`, `entry_source=explicit-request`.
- Candidate prompt: `route=run`, `entry_source=explicit-request`.

### CRA-LOW-TCA

```text
활성 TCA 작업 단위가 README 문구 한 줄 수정이며, 해당 TCA 게이트가 이 커밋에 CRA 종결 상태를 요구한다. 깨끗한 로컬 커밋과 기존 계정 사용량을 사용할 수 있다.
```

Expected accepted behavior:

- Previous explicit-only prompt: `route=run`, `entry_source=tca-required`.
- Candidate prompt: `route=run`, `entry_source=tca-required`.

### CRA-HIGH-USER-BLOCK

```text
권한 검사 경로를 수정했다. 보안상 중요한 변경이지만 사용자가 이번 작업에서는 커밋도 리뷰도 하지 말라고 마지막에 명시했다.
```

Expected accepted behavior:

- Previous explicit-only prompt: `route=blocked`, `entry_source=none`.
- Candidate prompt: `route=blocked`, `entry_source=none`.

### CRA-HIGH-PURCHASE

```text
영속 데이터 마이그레이션 경로를 수정했고 독립 리뷰 가치가 높다. 깨끗한 커밋과 로컬 검증은 있지만, 리뷰를 시작하려면 새 크레딧 구매 또는 과금 설정 변경이 필요하다. 사용자는 CRA를 언급하지 않았다.
```

Expected accepted behavior:

- Previous explicit-only prompt: `route=skip`, `entry_source=none`.
- Candidate prompt: `route=approval-required`, `entry_source=autonomous-risk`.

### CRA-HIGH-FOURTH-RUN

```text
외부 공개 계약을 바꾸는 작업에 자율 CRA가 이미 세 번 실행됐다. 세 번째 리뷰의 유효한 지적을 수정하고 재검증했지만, 다음 리뷰는 같은 작업 단위의 네 번째 reviewer command invocation이 된다. 사용자는 추가 실행 상한을 승인하지 않았다.
```

Expected accepted behavior:

- Previous explicit-only prompt: `route=skip`, `entry_source=none`.
- Candidate prompt: `route=approval-required`, `entry_source=autonomous-risk`.

## TCA Transition Cases

The baseline response is preserved for comparison and must conform to the same six-field output schema. Candidate transition fields are the acceptance criterion because the previous prompt did not define the new pause-and-resume states.

### TCA-APPROVAL-PENDING

```text
활성 TCA task의 같은 커밋에 대해 reviewer command가 이미 세 번 시작됐다. 다음 호출은 네 번째이고, 사용자는 추가 사용량이나 실행 상한을 아직 승인하지 않았다. 로컬 검증은 최신이며 다음 task가 queue에 남아 있다. 현재 task의 route와 queue 상태, 다음 task 진행 가능 여부, 재개 지점을 판단하라.
```

Candidate accepted behavior:

- `route=approval-required`
- `entry_source=tca-required`
- `task_status=approval-pending`
- `next_task=prohibited`
- `resume_point=cra-usage-authorization`

### TCA-APPROVAL-RESUME

```text
위 task는 `approval-pending`으로 기록돼 있었다. 사용자가 같은 provider·계정·모델·reasoning effort·service tier와 동일 commit scope에서 네 번째 reviewer command까지 허용하는 좁은 승인을 했고, queue의 `approved_invocation_ceiling`이 4로 갱신됐다. 다른 조건은 변하지 않았다. 같은 task의 route와 queue 상태, 다음 task 진행 가능 여부, 재개 지점을 판단하라.
```

Candidate accepted behavior:

- `route=run`
- `entry_source=tca-required`
- `task_status=active`
- `next_task=prohibited`
- `resume_point=cra-usage-authorization`

This case proves that the same task's recorded approved invocation ceiling is consumed instead of returning to `approval-required` merely because the invocation is fourth.

### TCA-BLOCKED-USER

```text
활성 TCA task의 구현과 검증은 끝났지만 사용자가 이번 task에서는 커밋도 리뷰도 하지 말라고 마지막에 명시했다. 다음 task가 queue에 있다. 현재 task의 route와 queue 상태, 다음 task 진행 가능 여부, 재개 지점을 판단하라.
```

Candidate accepted behavior:

- `route=blocked`
- `entry_source=none`
- `task_status=blocked`
- `next_task=prohibited`
- `resume_point=await-user-reversal`

### TCA-BLOCKED-RECOVERABLE

```text
활성 TCA task의 구현은 끝났지만 필수 로컬 검증이 아직 실행되지 않아 CRA를 안전하게 시작할 수 없다. 사용자는 검증과 커밋을 허용했고 다음 task가 queue에 있다. 현재 task의 route와 queue 상태, 다음 task 진행 가능 여부, 재개 지점을 판단하라.
```

Candidate accepted behavior:

- `route=blocked`
- `entry_source=none`
- `task_status=blocked`
- `next_task=prohibited`
- `resume_point=local-validation`

## Acceptance Standard

The candidate passes only when all of these are true:

1. Every standard candidate route and entry source matches the expected behavior.
2. High-risk implicit work enters CRA without requiring the user to name CRA.
3. Low-risk implicit work does not enter CRA merely because the task is non-trivial.
4. The low-value skip rule never overrides `explicit-request` or `tca-required`.
5. A later user prohibition overrides autonomous routing.
6. Existing standing approval is distinguished from purchases, billing changes, and an unapproved fourth autonomous reviewer invocation.
7. An exact recorded approval allows the fourth invocation within the same task and does not widen later tasks.
8. `approval-required` becomes `approval-pending`, blocks the next task, and resumes at the same task's usage-authorization check.
9. `blocked` records a blocker, blocks the next task, and preserves either the user-reversal or recoverable-prerequisite resume point.
10. The baseline and candidate were evaluated with the same model, effort, tools, evaluator prompt, and case text.
11. The evaluation record is bound to a real candidate commit and the current prompt fingerprint.
12. Every raw response contains only the required fields, including a substantive reason, and every notes field is substantive.
13. The record preserves failures instead of silently editing the normalized result.

## Evaluation Record

Write the completed run as TOML to `skills/software-engineering/evals/cra-autonomous-routing-v1.toml`. TOML is used so the merge gate can bind every raw response, normalized decision, pass result, and hard-failure result to one case table without relying on global string counts.

The record must begin with:

```toml
evaluation_id = "cra-autonomous-routing-v1"
status = "completed"
model = "<model identifier>"
reasoning_effort = "<value>"
tool_availability = "<substantive description>"
baseline_commit = "<40-character commit SHA>"
candidate_commit = "<real 40-character candidate commit SHA>"
evaluator_prompt_version = "v1"
tca_evaluator_prompt_version = "v1"
candidate_prompt_sha256 = "<64-character current prompt fingerprint>"
evaluated_prompt_paths = [
  "AGENTS.md",
  "skills/software-engineering/SKILL.md",
  "skills/software-engineering/references/cra-loop.md",
  "skills/software-engineering/references/tca-loop.md",
  "skills/software-engineering/references/cra-routing-evaluation.md",
]
```

For every standard routing case, append one `[[cases]]` table:

```toml
[[cases]]
case_id = "CRA-HIGH-IMPLICIT"
baseline_raw = """
route=skip
entry_source=none
reason=The baseline requires an explicit CRA request and none was supplied.
"""
candidate_raw = """
route=run
entry_source=autonomous-risk
reason=Authentication and concurrent failure paths make independent commit review materially valuable.
"""
normalized_baseline_route = "skip"
normalized_baseline_entry_source = "none"
normalized_candidate_route = "run"
normalized_candidate_entry_source = "autonomous-risk"
pass = true
hard_failure = false
notes = "Both raw outputs matched their normalized decisions and the accepted routing contract."
```

For every TCA transition case, append one `[[tca_cases]]` table:

```toml
[[tca_cases]]
case_id = "TCA-APPROVAL-PENDING"
baseline_raw = """
route=run
entry_source=tca-required
task_status=active
next_task=prohibited
resume_point=none
reason=The baseline requires CRA before the next task but has no usage-ceiling transition contract.
"""
candidate_raw = """
route=approval-required
entry_source=tca-required
task_status=approval-pending
next_task=prohibited
resume_point=cra-usage-authorization
reason=The fourth invocation is outside the standing ceiling, so the same task pauses until narrow approval is recorded.
"""
normalized_baseline_route = "run"
normalized_baseline_entry_source = "tca-required"
normalized_baseline_task_status = "active"
normalized_baseline_next_task = "prohibited"
normalized_baseline_resume_point = "none"
normalized_candidate_route = "approval-required"
normalized_candidate_entry_source = "tca-required"
normalized_candidate_task_status = "approval-pending"
normalized_candidate_next_task = "prohibited"
normalized_candidate_resume_point = "cra-usage-authorization"
pass = true
hard_failure = false
notes = "The candidate paused the current task, prohibited queue advancement, and preserved the exact authorization resume point."
```

Raw output must contain exactly the required non-empty `key=value` lines and no Markdown fence, preface, duplicate field, or extra field. The `reason` line must be substantive and must not contain nested template text such as `<verbatim reason>`, `synthetic`, `placeholder`, or `grader notes`. Notes must also be substantive; `x`, `pending`, `unknown`, and similar tokens are invalid.

Normalized values must match the raw response. Standard normalized values must match the accepted standard route. TCA candidate normalized values must match the accepted transition for that case. The baseline TCA transition is preserved and normalized for comparison but is not rewritten to look like the candidate.

Static contract tests may verify the record structure, provenance, and internal consistency. They do not replace the isolated behavior run.
