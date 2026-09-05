# Davis Agent Kit

한국어로 작업하는 에이전트가 사용자의 판단 기준과 작업 습관을 일관되게 적용하도록 만드는 철학·지침·스킬 키트입니다.

## 구조

```text
davis-agent-kit/
  AGENTS.md           # 전역 철학·원칙·행동 계약
  AGENTS.override.md  # 이 저장소를 수정할 때만 적용되는 규칙
  kit.toml            # 버전·설치 manifest
  guidelines/         # 공통 원칙의 적용 지침
  checklists/         # 실제 완료 전에 필요한 짧은 검수 기준
  templates/          # 재사용 출력 형식
  skills/             # 독립 설치 가능한 Codex skills
  examples/           # 실제 품질 기준에 필요한 예시
  user-model/         # 아직 다른 규범 원본으로 흡수되지 않은 사용자 기준의 관리 원칙
  scripts/            # 설치·doctor·기계 검증
  .github/            # CI
```

현재 동작을 설명하지 않는 과거 의사결정 기록, 일회성 행동 평가 raw trace, grader 출력, 실행 로그는 저장소에 장기 보존하지 않습니다. Git history와 PR이 변경 이유를 남기며, 필요한 평가 결과는 해당 PR/CI/artifact에 요약합니다.

## 지침 구조

`AGENTS.md`는 모든 저장소에서 적용할 전역 철학, 핵심 원칙, 기본 동작, 행동 권한, 중단 조건, 스킬 라우팅의 규범 원본입니다. `AGENTS.override.md`는 이 저장소를 수정할 때만 적용됩니다. 세부 절차는 해당 `guidelines/`, `checklists/`, `skills/`, `templates/`에 둡니다.

한 계약을 여러 파일에 반복하지 않습니다. 스킬은 독립 설치 가능해야 하므로 실행에 꼭 필요한 계약은 스킬 내부에 남기되, 상세 절차의 원본은 하나만 둡니다.

## 현재 스킬

- [`translation-quality`](skills/translation-quality/) — 긴 비즈니스 문서·실적발표 번역과 원문/수치/HTML QA
- [`handoff-agent-builder`](skills/handoff-agent-builder/) — 프로젝트별 인수인계 에이전트 설계와 멀티턴 검증
- [`outcome-owner`](skills/outcome-owner/) — 직원이 아니라 주인·파트너처럼 전체 결과를 보고 문제를 재정의하며 높은 레버리지의 발전에 주도적으로 기여
- [`software-engineering`](skills/software-engineering/) — 구현 위임, 로컬 검증, CRA/TCA
- [`writing-quality`](skills/writing-quality/) — 장문 분석·원고 작성·편집과 필요 시 분리 검수

## 모델 운용

프론티어 모델 전환은 [`guidelines/prompt-migration.md`](guidelines/prompt-migration.md)를 따릅니다. 키트는 비용 효율을 위해 런타임 기본 컨텍스트를 사용하며 확장 컨텍스트 override를 만들지 않습니다.

소프트웨어 작업의 기본 역할 배치는 다음과 같습니다.

- bounded implementation worker: Luna Max + Fast 우선 후보
- CRA reviewer: Astra Medium + standard tier

역할 기본값은 전역 모델 강제가 아닙니다. 실제 launcher와 가용성을 확인하고, 품질이 부족할 때만 구체적 근거로 변경합니다.

## 검증

기계적으로 검증 가능한 계약만 자동화합니다.

```bash
python3 scripts/validate_kit.py
```

CI도 같은 진입점을 사용합니다. 자동 검증 대상은 manifest/frontmatter/resource 경로, installer·doctor의 충돌·롤백·credential 경계, 실제 helper 코드와 그 공개 동작입니다.

Markdown의 특정 문구·제목·섹션·예시나 모델의 판단 품질을 자동 테스트로 고정하지 않습니다. 실행 코드의 테스트도 공개 계약, 안전 경계, 재발 가능한 회귀를 보호할 때만 유지합니다. 모델 행동 평가는 중요한 변경에서만 대표 과제로 수행하고 결과를 PR에 남깁니다.

저장소와 manifest만 확인하려면:

```bash
python3 scripts/doctor.py --repo-only
```

## 설치

저장소 루트에서:

```bash
./scripts/install_codex.sh
```

다른 `CODEX_HOME`을 쓰면:

```bash
CODEX_HOME=/path/to/codex-home ./scripts/install_codex.sh
```

설치 스크립트는 `kit.toml`의 전역 `AGENTS.md`와 스킬을 Codex 경로에 심링크하고 doctor를 실행합니다. 기존 파일·다른 링크·retired/unlisted skill을 임의로 덮거나 삭제하지 않으며 충돌 시 변경 전에 중단합니다.

`${CODEX_HOME:-$HOME/.codex}/davis-agent-kit` 자체를 checkout으로 사용하거나 checkout을 `CODEX_HOME` 밖에 둡니다. 설치 뒤 새 Codex 세션을 시작해 지침과 스킬 목록을 다시 로드합니다.

연결 상태는 다음으로 확인합니다.

```bash
python3 scripts/doctor.py
```

`--strict`를 붙이면 경고도 실패로 처리합니다.

## 수정 원칙

1. 원격과 현재 작업 상태를 확인하고 다른 변경을 덮지 않습니다.
2. 현재 행동을 바꾸는 최소한의 규범 원본과 직접 연결된 실행물만 수정합니다.
3. 실제 코드가 있는 helper는 필요한 테스트를 함께 유지합니다. 문서 문구를 테스트하지 않습니다.
4. 실패 원인이나 사용자 기준이 현재 지침에 흡수되면 별도 역사 기록을 또 남기지 않습니다.
5. push, merge, 배포, 마이그레이션, 외부 상태 변경은 명시적 권한을 따릅니다.
