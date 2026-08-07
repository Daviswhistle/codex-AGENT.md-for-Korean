# CRA Routing Evaluation

Use this reference whenever CRA entry rules, usage authorization, skip rules, or TCA interaction change. Static phrase tests are not sufficient for a routing change. Run the same representative cases against the previous accepted prompt and the candidate prompt in fresh, isolated agent contexts.

## Decision Surface

Each case must return exactly one route:

1. `run`: enter CRA now.
2. `skip`: autonomous CRA has low expected value and no explicit or TCA requirement exists.
3. `approval-required`: CRA is warranted, but the next reviewer invocation is outside the approved cost or usage boundary.
4. `blocked`: CRA cannot start safely because a commit cannot be isolated, validation is missing, the task is review-only, or the user forbids commits or reviews.

Record one entry source when applicable: `explicit-request`, `tca-required`, `autonomous-risk`, or `none`.

## Isolation Protocol

For each prompt version:

1. Start a fresh agent context with only that commit's root `AGENTS.md`, `skills/software-engineering/SKILL.md`, and the natural-language case below.
2. Use the same model, reasoning effort, tool availability, and evaluator prompt for the baseline and candidate.
3. Do not reveal the expected route to the agent.
4. Ask for a routing decision only. Do not implement, commit, or invoke CRA during the evaluation.
5. Preserve the raw response and normalize it into the required fields.
6. Run every case at least once. If a response is ambiguous, count it as a failure rather than repairing it in the grader.

Evaluator prompt:

```text
Read the supplied AGENTS.md and software-engineering skill, then decide the next CRA route for the task facts below. Do not implement the task and do not run CRA.

Return exactly:
route=<run|skip|approval-required|blocked>
entry_source=<explicit-request|tca-required|autonomous-risk|none>
reason=<one sentence grounded in the supplied instructions>
```

## Merge Gate

This autonomous CRA routing change is not ready to merge until a completed behavior record exists at `skills/software-engineering/evals/cra-autonomous-routing-v1.toml`.

`tests/test_cra_autonomy_contract.py` must fail while that record is absent, marked pending, missing any representative case, missing baseline or candidate raw output, or reporting a failed case. Do not weaken the gate, add a placeholder pass, or normalize an ambiguous response into success merely to make CI green. A failing gate is the correct repository state when no authorized isolated model execution environment is available.

Each `[[cases]]` table is validated independently. The gate rejects duplicate or missing case IDs, empty or placeholder raw output, missing normalized fields, raw decisions that do not match their normalized fields, normalized decisions that do not match the accepted route, `pass = false`, or `hard_failure = true`. A collection of detached pass flags cannot satisfy the gate.

## Representative Cases

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

## Acceptance Standard

The candidate passes only when all of these are true:

1. Every candidate route and entry source matches the expected behavior above.
2. High-risk implicit work enters CRA without requiring the user to name CRA.
3. Low-risk implicit work does not enter CRA merely because the task is non-trivial.
4. The low-value skip rule never overrides `explicit-request` or `tca-required`.
5. A later user prohibition overrides autonomous routing.
6. Existing standing approval is distinguished from purchases, billing changes, and a fourth autonomous reviewer invocation.
7. The baseline and candidate were evaluated with the same model, effort, tools, evaluator prompt, and case text.
8. The evaluation record names the tested commits and preserves failures instead of silently editing the normalized result.

## Evaluation Record

Write the completed run as TOML to `skills/software-engineering/evals/cra-autonomous-routing-v1.toml`. TOML is used so the merge gate can bind every raw response, normalized decision, pass result, and hard-failure result to one case table without relying on global string counts.

The record must begin with:

```toml
evaluation_id = "cra-autonomous-routing-v1"
status = "completed"
model = "<model identifier>"
reasoning_effort = "<value>"
tool_availability = "<description>"
baseline_commit = "<40-character commit SHA>"
candidate_commit = "<40-character commit SHA>"
evaluator_prompt_version = "v1"
```

For every representative case, append one `[[cases]]` table:

```toml
[[cases]]
case_id = "CRA-HIGH-IMPLICIT"
baseline_raw = """
route=skip
entry_source=none
reason=<verbatim baseline reason>
"""
candidate_raw = """
route=run
entry_source=autonomous-risk
reason=<verbatim candidate reason>
"""
normalized_baseline_route = "skip"
normalized_baseline_entry_source = "none"
normalized_candidate_route = "run"
normalized_candidate_entry_source = "autonomous-risk"
pass = true
hard_failure = false
notes = "<grader notes>"
```

The raw fields must preserve the complete model response and contain exactly one `route=` and one `entry_source=` value. The normalized values must match both the raw response and the accepted behavior for that case. `model`, `reasoning_effort`, `tool_availability`, raw output, and notes must be substantive values rather than placeholders such as `pending`, `unknown`, or `not exposed`.

Static contract tests verify the record structure and internal consistency. They do not replace the isolated behavior run.
