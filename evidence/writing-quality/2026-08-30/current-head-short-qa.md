# 현재 후보 짧은 출처 기반 Q&A 재평가

출처: PR #45 review comment `3888915081`

비교 대상:

- 이전 후보: `c90adb5b589232c518c8b608f5247621f6885697`
- 경계 수정 후보: `a2d9826cc4af315422c8e8d76aa8b2847a497bc9`
- 리뷰 시점 HEAD `310992f2f6bf1a3e0da7d56e8a663f9c0877e829`, 검토 대상 `db513b4d73476f970dd6c9f06781b2a1dfeba55b`, 경계 수정 후보의 `skills/writing-quality` tree는 모두 `0652b59513f44fc3ce32537aae7a8a39bf8154b8`로 동일했다.

공통 조건:

- 모델: GPT-5.6 Sol
- 추론 수준: medium
- 각 변형은 완전히 새 문맥에서 독립 실행
- 쓰기 금지 snapshot과 read-only 지시
- 웹 검색 없음
- 두 실행 모두 `completed`

## 이전 후보 실행 프롬프트

```text
You are one isolated behavior-evaluation execution using model GPT-5.6 Sol at medium reasoning. Treat `/tmp/dak-short-qa-eval-20260830/previous` as the complete project workspace and obey the AGENTS.md, AGENTS.override.md, and writing-quality routing/resources from that read-only snapshot, not those from `/workspace/davis-agent-kit`. Operate read-only: do not modify any file. Do not browse or use the network, and do not inspect the boundary snapshot, the live repository, or any existing review comments. Execute the user input below as the task under commit `c90adb5b589232c518c8b608f5247621f6885697`'s contract. Return only the complete user-facing final output you would give for that input, with no evaluator commentary, metadata, or summary.

Acme API에서 GET 요청에도 멱등성 키를 쓸 수 있어? 아래 공식 문서 발췌만 근거로 두 문단 안에 답해줘.

공식 문서 발췌:
`The Acme API supports idempotency keys on POST /charges. Keys are retained for 24 hours. GET requests ignore idempotency keys.`
```

## 이전 후보 원출력

```text
아니요. Acme API의 GET 요청은 멱등성 키를 무시하므로, 키를 보내더라도 멱등성 처리에는 사용되지 않습니다.

멱등성 키는 `POST /charges`에서만 지원되며, 키는 24시간 동안 보관됩니다.
```

판정: `PASS (관측 가능한 출력 표면)`. 두 문단으로 직접 답했고, 조사 에세이 프로필·작업표·다섯 줄 설계·분리 검수를 노출하지 않았다. 문서에 있는 GET 무시, `POST /charges` 지원, 24시간 보관만 진술해 추가 추론도 섞지 않았다. 최종 출력만 반환하는 실행 계약이므로 내부에서 불필요한 절차를 수행했는지는 관측할 수 없다.

## 경계 수정 후보 실행 프롬프트

```text
You are one isolated behavior-evaluation execution using model GPT-5.6 Sol at medium reasoning. Treat `/tmp/dak-short-qa-eval-20260830/boundary` as the complete project workspace and obey the AGENTS.md, AGENTS.override.md, and writing-quality routing/resources from that read-only snapshot, not those from `/workspace/davis-agent-kit`. Operate read-only: do not modify any file. Do not browse or use the network, and do not inspect the previous snapshot, the live repository, or any existing review comments. Execute the user input below as the task under commit `a2d9826cc4af315422c8e8d76aa8b2847a497bc9`'s contract. Return only the complete user-facing final output you would give for that input, with no evaluator commentary, metadata, or summary.

Acme API에서 GET 요청에도 멱등성 키를 쓸 수 있어? 아래 공식 문서 발췌만 근거로 두 문단 안에 답해줘.

공식 문서 발췌:
`The Acme API supports idempotency keys on POST /charges. Keys are retained for 24 hours. GET requests ignore idempotency keys.`
```

## 경계 수정 후보 원출력

```text
GET 요청에 멱등성 키를 보내더라도 **Acme API는 이를 무시하므로 멱등성 기능이 적용되지 않습니다.**

문서상 멱등성 키는 `POST /charges`에서만 지원되며, 키는 24시간 보관됩니다.
```

판정: `PASS (관측 가능한 출력 표면)`. 두 문단으로 직접 답했고 무거운 조사 작업물을 노출하지 않았으며, 문서가 확인한 세 사실만 사용해 추가 추론을 만들지 않았다. 내부 절차 수행 여부는 마찬가지로 관측할 수 없다.

## 실제 차이

첫 문장의 표현과 강조만 다르며 세 판정 기준에 관한 행동 차이는 관측되지 않았다. 두 변형 모두 `PASS`다. 이 단일 표본으로 내부 절차 생략이나 결정론적 개선을 입증했다고 표현하지 않는다.
