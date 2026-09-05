# Davis Agent Kit

한국어로 작업하는 Codex가 사용자의 목적과 판단 기준을 일관되게 적용하도록 만드는 작은 전역 지침 + skill 묶음입니다.

## 구조

```text
davis-agent-kit/
├── AGENTS.md
├── AGENTS.override.md
├── skills/
│   ├── translation-quality/
│   ├── handoff-agent-builder/
│   ├── software-engineering/
│   └── writing-quality/
├── scripts/
├── tests/
└── .github/
```

- `AGENTS.md`: 모든 작업의 기본 자세, 권한, 완료 기준과 skill routing
- `AGENTS.override.md`: 이 저장소 자체를 수정할 때의 관리 규칙
- `skills/`: 반복 workflow와 그 workflow에만 필요한 references, agents, scripts, tests
- `scripts/install_codex.py`: 전역 AGENTS와 user skills를 심링크
- `scripts/validate_kit.py`: active skill 계약과 실행 가능한 tests/helpers 검증

과거 의사결정 기록, raw model trace, 수동 평가 archive, 빈 template/inbox/user-model 디렉터리는 제품 트리에 유지하지 않습니다. 변경 이유는 Git history와 PR이 보존합니다.

## 기본 자세

목적 소유와 주인·파트너 관점은 별도 skill이 아니라 `AGENTS.md`의 상시 기본값입니다. 모델은 표면 과업보다 실제 결과를 보고, 잘못된 전제를 고치며, 근본 원인과 높은 레버리지의 개선을 찾습니다. 동시에 새로운 가치 선택, 비용, 외부 write, 비가역적 위험과 실질적인 범위 확대는 사용자 권한으로 남깁니다.

긴 작업에서 continuity가 실제 문제일 때만 작은 checkpoint를 남기고, 재개할 때 현재 저장소·산출물·검증과 다시 대조합니다. 별도 mission database나 ownership runtime은 두지 않습니다.

## Skills

- `translation-quality`: 비단순 한국어 번역, transcript·재무보고서 번역, source/numeric/format QA
- `handoff-agent-builder`: Codex가 자동 발견하는 repo-local handoff skill 설계와 멀티턴 검증
- `software-engineering`: 구현 위임, 로컬 검증, 필요할 때 CRA/TCA
- `writing-quality`: 글쓰기 자체가 품질 병목인 원고·장문 분석·게시용 문서 작성과 편집

Codex는 skill을 먼저 metadata로 발견하고 선택된 skill의 `SKILL.md`와 필요한 reference만 읽습니다. 따라서 전역 원칙은 AGENTS에, 조건부 절차는 skill 내부에만 둡니다.

## 모델 운용

- 모든 역할은 런타임 기본 컨텍스트를 사용합니다. 이 kit는 context window나 auto-compaction limit을 늘리지 않습니다.
- bounded implementation worker의 첫 후보는 `gpt-5.6-luna` + Max + Fast입니다.
- CRA reviewer의 기본은 `gpt-6-astra` + Medium + default/non-Fast service tier입니다.
- 더 비싼 자원은 오류 비용·모호성·실제 품질 실패 같은 구체적 이유가 있을 때만 사용합니다.

## 설치

현재 Codex의 전역 위치를 따릅니다.

- global instructions: `${CODEX_HOME:-$HOME/.codex}/AGENTS.md`
- user skills: `$HOME/.agents/skills/<skill-name>`

저장소 루트에서:

```bash
./scripts/install_codex.sh
```

다른 위치를 시험하거나 격리하려면:

```bash
./scripts/install_codex.sh \
  --codex-home /tmp/codex-home \
  --skills-home /tmp/agents/skills
```

설치기는 기존 파일이나 다른 skill을 덮어쓰지 않습니다. 이미 정확한 심링크면 유지하고 충돌하면 변경 전에 중단합니다.

이 kit의 과거 버전이 사용하던 `${CODEX_HOME:-$HOME/.codex}/skills`는 Codex가 호환 목적으로 아직 읽을 수 있으므로, 그 위치에 `translation-quality`, `handoff-agent-builder`, `software-engineering`, `writing-quality` 또는 retired kit skill이 남아 있으면 migration을 중단합니다. 중복 로딩을 피하기 위해 해당 과거 링크를 직접 확인해 제거한 뒤 다시 실행합니다.

설치 상태 확인:

```bash
./scripts/install_codex.sh --check
```

설치 또는 skill 변경 뒤에는 새 Codex 세션을 시작합니다.

## 검증

```bash
python3 scripts/validate_kit.py
```

CI도 같은 진입점을 사용합니다. 검증 대상은 skill frontmatter/resource 경로, installer 계약, 실제 helper와 실행 코드의 tests입니다. 특정 Markdown 문구나 모델 판단 품질을 정적 테스트로 고정하지 않습니다.

## 수정 원칙

1. 현재 행동을 바꾸는 최소 규범 원본과 직접 연결된 실행물만 수정합니다.
2. 실제 실패보다 큰 방어 시스템을 만들지 않습니다.
3. helper가 필요 없어진다면 helper를 지키기 위한 테스트도 함께 없앱니다.
4. 행동 품질 변화는 필요할 때 대표 작업으로 비교하고 결과는 PR에 요약합니다.
5. merge, 배포, 외부 상태 변경은 명시적 권한을 따릅니다.
