# Skills

반복 작업을 Codex가 재현할 수 있도록 절차화한 문서를 모읍니다.

스킬은 다음 조건을 만족할 때 고정합니다.

1. 실제 작업에 적용했다.
2. 실패 지점을 확인했다.
3. 실패를 막는 절차를 추가했다.
4. 다시 검증했다.
5. 설치/사용 방법을 README에 적었다.

## 현재 스킬

- `translation-quality`: 긴 비즈니스 문서와 실적발표 transcript를 자연스러운 한국어로 번역하고 개념 검수와 HTML QA까지 수행하기 위한 스킬
- `handoff-agent-builder`: 프로젝트별 인수인계 에이전트를 설계하고 멀티턴 검증까지 수행하기 위한 스킬
- `outcome-owner`: 비사소하거나 장기적인 목표의 목적·제약·성공 기준·근거·소유권을 보존하고, 권한 안에서 주도적으로 실행해 검증된 완료까지 책임지기 위한 스킬
- `software-engineering`: 비사소한 구현과 로컬 검증을 작업 에이전트에 위임하고, CRA 또는 TCA의 필요성을 자율적으로 판단해 선택한 workflow를 실행하기 위한 스킬
- `writing-quality`: 모든 사용자 답변에 적용되는 전역 최소 글쓰기 기준 위에서, 글쓰기 자체가 주요 품질 병목일 때 구조 설계·퇴고·검수를 제공하는 범용 스킬. 원고·장문·근거 기반·반복 발행·판단 비용이 큰 답변이나 명시적 완성도 요청에 사용하며, 문장 형식이라는 이유만으로 호출하거나 일반 질의 응답이라는 이유만으로 배제하지 않는다.

`software-engineering`의 위임 계약은 모델 중립적입니다. `software-engineering/references/worker-luna-max-fast.toml`은 GPT-5.6 Luna, Max reasoning, Fast service tier를 사용하는 선택적 custom `worker` 예시이며 설치 시 자동 적용되지 않습니다.

## 설치 단위

각 하위 폴더는 독립 Codex skill 원본입니다. Codex가 자동 발견하려면 설치 위치에 아래 형태로 배치되어야 합니다.

```text
~/.codex/skills/<skill-name>/SKILL.md
```

이 레포의 root는 전역 지침과 스킬 원본을 함께 관리하는 source of truth입니다. 각 스킬의 동작 지침은 해당 하위 폴더에서 관리합니다.
