# 현재 후보 영어 편집기 라우팅 재평가

출처: PR #45 review comment `3888888454`

비교 대상:

- pre-fix: `032b5b1cd9ae11ac6bc826807bf62eade30196dd`
- candidate: `a2d9826cc4af315422c8e8d76aa8b2847a497bc9`
- 현재 검토 대상의 `writing-quality` tree는 candidate와 동일함을 실행자가 확인했다.

공통 조건:

- 모델: GPT-5.6 Sol
- 추론 수준: medium
- 각 변형은 완전히 새 문맥에서 독립 실행
- 별도 snapshot과 read-only 지시
- 웹 검색 없음
- 두 실행 모두 `completed`

## pre-fix 실행 프롬프트

```text
You are one isolated behavior-evaluation execution using model GPT-5.6 Sol at medium reasoning. Treat `/tmp/dak-editor-eval-20260830/pre-fix` as the complete project workspace and obey the AGENTS.md and skill resources from that snapshot, not those from `/workspace/davis-agent-kit`. Operate read-only: do not modify any file. Do not browse or use the network, and do not inspect the candidate snapshot or any existing review comments. Execute the user input below as the task under commit `032b5b1cd9ae11ac6bc826807bf62eade30196dd`'s `writing-quality` contract. Return only the complete user-facing output you would give for that input, with no evaluator commentary or summary.

The factual review is complete. Edit the following evidence-backed research paragraph for an English-language audience. First state which editorial reviewer you selected, then provide the edited paragraph. Do not add facts.

Factual review result:
`PASS. The draft may state that the supplied study found an association, but it may not claim causation. No dates, numbers, or comparison bases may be added or changed.`

Draft:
`The study, association was found between queue visibility and cancellation. But this is not meaning causation. The operational implication deriving is that managers should observe the queue before changing staffing. Source note: https://example.invalid/search-result [Image] TOOL_RESULT_17.`
```

## pre-fix 원출력

```text
Editorial reviewer selected: Korean Research Essay Editor.

The study found an association between queue visibility and cancellation, but it did not establish causation. The operational implication is that managers should observe the queue before changing staffing.
```

판정: `FAIL`. 영어 문장과 표면 잔재는 고쳤고 사실 범위도 지켰지만 영어 출력에 한국어 편집기를 선택했다.

## candidate 실행 프롬프트

```text
You are one isolated behavior-evaluation execution using model GPT-5.6 Sol at medium reasoning. Treat `/tmp/dak-editor-eval-20260830/candidate` as the complete project workspace and obey the AGENTS.md and skill resources from that snapshot, not those from `/workspace/davis-agent-kit`. Operate read-only: do not modify any file. Do not browse or use the network, and do not inspect the pre-fix snapshot or any existing review comments. Execute the user input below as the task under commit `a2d9826cc4af315422c8e8d76aa8b2847a497bc9`'s `writing-quality` contract. Return only the complete user-facing output you would give for that input, with no evaluator commentary or summary.

The factual review is complete. Edit the following evidence-backed research paragraph for an English-language audience. First state which editorial reviewer you selected, then provide the edited paragraph. Do not add facts.

Factual review result:
`PASS. The draft may state that the supplied study found an association, but it may not claim causation. No dates, numbers, or comparison bases may be added or changed.`

Draft:
`The study, association was found between queue visibility and cancellation. But this is not meaning causation. The operational implication deriving is that managers should observe the queue before changing staffing. Source note: https://example.invalid/search-result [Image] TOOL_RESULT_17.`
```

## candidate 원출력

```text
Selected reviewer: English Research Essay Editor

The study found an association between queue visibility and cancellation, but it did not establish causation. The operational implication is that managers should observe the queue before changing staffing.
```

판정: `PASS`. 영어 편집기를 선택했고 문장·용어·표면 잔재를 고치면서 상관관계를 인과로 강화하거나 새 사실을 추가하지 않았다.

## 실제 차이

편집된 문단은 두 실행에서 동일했다. 관측된 행동 차이는 편집기 선택이다. pre-fix는 한국어 편집기를 선택해 실패했고 candidate는 영어 편집기를 선택해 통과했다. 이 한 번의 대표 표본을 결정론적 보장으로 확대하지 않는다.
