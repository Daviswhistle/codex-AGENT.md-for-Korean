# Davis Agent Kit

한국어로 작업하는 에이전트가 사용자의 판단 기준과 작업 습관을 따라 사고하고 행동하도록 만드는 철학과 원칙 중심 운영 키트입니다.

최종 목적은 반복 작업에서 드러난 사고방식, 판단 기준, 우선순위, 품질 기준, 검증 습관을 새 환경에서도 재현 가능한 형태로 남기는 것입니다.

## 지침 구조

[`AGENTS.md`](AGENTS.md)는 모든 저장소에서 적용할 전역 철학, 핵심 원칙, 기본 동작, 행동 권한, 중단 조건, 스킬 라우팅의 유일한 규범적 원본입니다.

[`AGENTS.override.md`](AGENTS.override.md)는 이 저장소를 수정할 때만 필요한 프로젝트 지침입니다. Codex가 `davis-agent-kit` 안에서 작업할 때는 전역 `AGENTS.md`와 프로젝트 override를 결합하므로, 저장소 전용 관리 규칙을 일반 프로젝트의 전역 프롬프트에 싣지 않습니다.

철학은 필요한 것을 잃지 않는 가장 단순한 형태를 찾는 사고방식입니다. 핵심 원칙은 철학을 작업에서 반복 사용할 수 있는 판단 기준으로 바꾼 것입니다. 가이드라인, 스킬, 체크리스트, 템플릿, 테스트, 폴백 규칙은 원칙을 현재 환경에 적용하는 실행물입니다.

## 기본 구조

```text
davis-agent-kit/
  AGENTS.md           # 모든 프로젝트에 적용할 전역 지침의 규범 원본
  AGENTS.override.md  # 이 저장소에만 적용할 프로젝트 지침
  kit.toml            # 키트 버전·스키마·Python·설치 대상 manifest
  scripts/            # 설치·진단·기계 검증 도구
  .github/            # 같은 검증 진입점을 실행하는 CI
  guidelines/         # 원칙에서 내려온 적용 지침
  checklists/         # 완료 전 검수 기준
  templates/          # 글, 리서치, 리뷰 등 출력 형식 템플릿
  skills/             # 독립 Codex skill 원본
  examples/           # 좋은 결과물과 나쁜 결과물 예시
  evidence/           # 대표 행동 평가의 원시 결과와 수동 판정
  user-model/         # 작업 재현성에 필요한 사용자 선호와 품질 기준
  decisions/          # 왜 이렇게 정했는지 남기는 결정 기록
  inbox/              # 아직 정리되지 않은 원칙, 피드백, 아이디어
  scratch/            # 임시 작업 공간, git 제외
  private/            # 토큰, 계정 정보, 비공개 원문 등, git 제외
```

## 운영 방식

1. `AGENTS.md`에는 모든 세션에 필요한 전역 판단 계약만 둡니다.
2. 이 저장소에만 필요한 자동 로드 규칙은 `AGENTS.override.md`에 둡니다.
3. 세부 절차와 특정 작업 표면의 해설은 `guidelines/`, `checklists/`, `skills/`, `templates/`에 둡니다.
4. 실제 Codex 스킬은 `skills/<skill-name>/SKILL.md` 형태로 독립 유지합니다.
5. 반복해서 지적된 문제는 철학, 핵심 원칙, 기본 동작, 적용 지침, 실행물 중 어디에 속하는지 먼저 분류합니다.
6. 스킬은 실제 작업에 적용하고 실패 지점을 반영한 뒤 고정합니다.
7. 좋은 결과물만 저장하지 말고 반복 실수를 막는 나쁜 예시와 검수 기준도 함께 남깁니다.
8. 새로 파악한 사용자 선호와 품질 기준은 작업 재현성에 직접 도움이 될 때만 `user-model/`에 근거와 함께 기록합니다.
9. push, 배포, 원격 저장소 rename처럼 외부 상태를 바꾸는 작업은 전역 행동 권한과 사용자의 명시 요청을 따릅니다.

프롬프트나 스킬을 GPT-5.6에 맞게 조정할 때는 [프롬프트 변경과 GPT-5.6 이행](guidelines/prompt-migration.md)을 사용합니다. 기준선을 남기고 한 번에 하나의 변경 묶음만 적용한 뒤 같은 대표 평가를 다시 실행합니다.

## 검증

자동 검증은 지침이나 스킬의 정답을 판정하지 않습니다. 다음처럼 기계적으로 확인할 수 있는 표면만 다룹니다.

- `kit.toml`, skill frontmatter, bundled resource 경로의 파싱과 존재 여부
- installer와 doctor의 링크 생성, 충돌 거부, 롤백, credential sanitization
- 번역 HTML 변환·QA·equivalence helper처럼 실제로 실행되는 코드의 동작
- bundled helper의 `--help` smoke check

```bash
python3 scripts/validate_kit.py
```

이 명령은 실행 가능한 테스트 디렉터리와 helper를 자동 발견합니다. `.github/workflows/validate.yml`도 pull request와 `main` push에서 같은 명령을 실행하므로 로컬 코드 검증과 CI 검증이 갈라지지 않습니다.

Markdown의 특정 문구, 제목, 섹션 배치, 라우팅 선언, 예시는 자동 테스트로 고정하지 않습니다. 지침과 스킬의 판단 품질은 같은 대표 과제를 실제로 다시 실행하고 결과를 비교하며 검토합니다. 정적 검증 통과는 행동 품질의 증거가 아닙니다.

보존 가치가 있는 대표 행동 평가의 원시 trace, 최종 응답, 자동 판정과 수동 판정은 [`evidence/`](evidence/)에 둡니다. 일회성 평가 러너는 제품 실행물과 분리하고, 결과를 재현하는 데 필요한 고정 commit이나 별도 브랜치를 증거 기록에 명시합니다.

설치 링크를 요구하지 않고 저장소와 manifest 상태만 진단하려면 다음을 실행합니다.

```bash
python3 scripts/doctor.py --repo-only
```

## 버전 manifest

[`kit.toml`](kit.toml)은 키트 버전, manifest 스키마 버전, 최소 Python 버전, 전역 지침 원본, Codex 설치 경로 이름, 활성 스킬과 제거해야 할 legacy 스킬 목록을 관리합니다.

- 스킬을 추가하거나 이름을 바꾸면 `kit.toml`을 같은 변경에서 갱신합니다.
- `scripts/validate_kit.py`는 manifest와 실제 `skills/*/SKILL.md` 목록, `name`·`description` frontmatter, bundled resource 참조가 일치하는지 검사합니다.
- `scripts/doctor.py`는 같은 manifest를 사용해 현재 checkout과 Codex가 읽는 심링크 대상이 일치하는지 검사합니다.

## 수정 전 safe sync

에이전트가 이 저장소를 수정하기 전에는 원격 변경을 먼저 확인합니다. 목표는 로컬 변경과 원격 변경을 모두 보존한 상태로 수정 가능한 기준점을 만드는 것입니다.

```bash
CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"
cd "$CODEX_DIR/davis-agent-kit"

if [ -n "$(git status --porcelain)" ]; then
  git status --short
  printf '%s\n' "local changes exist; inspect and commit intended changes first"
else
  git fetch origin main
  git pull --ff-only origin main
fi
```

로컬 변경이 있으면 `git diff`와 `git diff --cached`로 내용을 확인합니다. 의도된 변경은 관련 파일만 stage해서 커밋 가능한 단위로 보호한 뒤 원격 변경을 가져옵니다.

```bash
git add <intended-files>
git commit -m "<message>"
git fetch origin main
git rebase origin/main
```

원격과 로컬이 갈라져 fast-forward가 불가능하면 rebase로 로컬 커밋을 원격 최신 커밋 위에 다시 적용합니다. 충돌이 나면 양쪽 변경 의도를 확인해 해소하고 검증한 뒤 `git rebase --continue`로 진행합니다. push는 명시 요청이 있을 때 수행합니다.

## 설치

권장 설치 방식은 저장소 루트에서 Codex 전용 설치 스크립트를 한 번 실행하는 것입니다.

```sh
./scripts/install_codex.sh
```

`CODEX_HOME`을 별도로 사용하는 환경에서도 같은 명령을 사용할 수 있습니다.

```sh
CODEX_HOME=/path/to/codex-home ./scripts/install_codex.sh
```

설치 스크립트는 `kit.toml`에 등록된 모든 스킬과 전역 `AGENTS.md`를 심링크로 연결하고 doctor를 실행합니다. 저장소가 이미 `${CODEX_HOME:-$HOME/.codex}/davis-agent-kit`에 직접 checkout되어 있으면 그 디렉터리를 그대로 기준 원본으로 사용합니다. 이미 올바른 checkout과 링크는 유지하므로 반복 실행해도 안전합니다.

installer는 기존 파일, 다른 링크, retired 스킬 또는 이 kit를 가리키는 unlisted 스킬을 자동으로 이동하거나 삭제하지 않습니다. 하나라도 발견하면 어떤 설치 경로도 바꾸기 전에 중단하므로, 사용자가 해당 경로를 직접 확인하고 정리한 뒤 다시 실행합니다. 새 링크를 만드는 도중 또는 최종 doctor에서 실패하면 이번 실행이 만든 경로만 제거합니다.

`${CODEX_HOME:-$HOME/.codex}/skills` 자체가 whole-directory 심링크이거나 실제 경로가 checkout 내부이면 installer는 아무 설치 경로도 변경하지 않고 중단합니다. 이 경우 whole-directory 링크를 checkout 밖의 실제 `skills` 디렉터리로 교체한 뒤 다시 실행합니다.

installer는 checkout이 `CODEX_HOME` 아래에 있으면서 managed `davis-agent-kit` 경로 자체를 차지하지 않거나, 반대로 `CODEX_HOME`이 checkout 내부인 배치도 변경 전에 거부합니다. 저장소를 `CODEX_HOME` 밖에 두거나 `${CODEX_HOME:-$HOME/.codex}/davis-agent-kit` 자체를 checkout으로 사용합니다.

설치 후에는 Codex를 재시작하거나 새 세션을 시작해 전역 지침과 스킬 목록이 다시 로드되도록 합니다.

`AGENTS.md`만 복사해도 전역 철학, 원칙, 행동 계약은 적용됩니다. 이 저장소의 프로젝트 override와 스킬, 세부 실행물까지 사용하려면 위 연결 설치를 사용합니다.

### 연결 상태 확인

설치 후에는 저장소 루트에서 doctor를 실행합니다.

```bash
python3 scripts/doctor.py
```

Doctor는 다음을 함께 확인합니다.

- 현재 `kit.toml`과 실제 스킬 목록
- 최소 Python 버전과 git checkout/commit/working-tree 상태
- `${CODEX_HOME:-$HOME/.codex}/davis-agent-kit`이 현재 저장소를 가리키는지
- 전역 `AGENTS.md` 링크가 이 저장소의 규범 원본을 가리키는지
- manifest에 등록된 모든 스킬 링크와 `SKILL.md` load entrypoint가 존재하는지
- 제거 대상으로 선언된 legacy 스킬이나 manifest에 없는 이 키트 내부 스킬 링크가 남아 있지 않은지

경고까지 실패로 처리하려면 `python3 scripts/doctor.py --strict`를 사용합니다. 파일 시스템 연결이 맞아도 이미 열린 Codex 세션의 목록은 자동 갱신되지 않으므로 설치나 스킬 변경 뒤에는 새 세션을 시작합니다.

## 현재 스킬

- [`translation-quality`](skills/translation-quality/) - 실적발표 컨퍼런스콜과 긴 비즈니스 문서를 자연스러운 한국어로 번역하고 개념 검수와 HTML QA까지 수행하기 위한 스킬
- [`handoff-agent-builder`](skills/handoff-agent-builder/) - 프로젝트별 인수인계 에이전트를 설계하고 멀티턴 검증까지 수행하기 위한 스킬
- [`outcome-owner`](skills/outcome-owner/) - 비사소하거나 장기적인 목표의 목적·제약·성공 기준·진행 근거·소유권 lease를 보존하고, 권한 안에서 주도적으로 실행한 뒤 검증된 완료까지 책임지기 위한 스킬
- [`software-engineering`](skills/software-engineering/) - 비사소한 구현과 로컬 검증을 작업 에이전트에 위임하고, CRA 또는 TCA의 필요성을 자율적으로 판단해 선택한 workflow를 실행하기 위한 스킬
- [`writing-quality`](skills/writing-quality/) - 독자가 그대로 읽거나 보내거나 게시할 원고를 과제에 맞는 구조와 확인된 글쓰기 원칙으로 작성·편집하기 위한 범용 스킬

`software-engineering`의 위임 계약은 모델 중립적입니다. 선택적 custom `worker` 예시는 [`worker-luna-max-fast.toml`](skills/software-engineering/references/worker-luna-max-fast.toml)에 있으며 GPT-5.6 Luna, Max reasoning, Fast service tier를 사용합니다. 이 예시는 설치 시 자동 적용되지 않습니다.

## 첫 번째 기준점

첫 기준점은 번역 작업입니다. `translation-quality` 스킬은 긴 실적발표 transcript 번역에서 요구되는 자연스러운 한국어, 화자·문단 형식, 주석, 링크, 이태릭체, 숫자 QA, 최종 검수를 절차화한 사례입니다.

이 사례에서 끌어낸 재현 가능한 품질 지침은 [재현 가능한 품질](guidelines/reproducible-quality.md)에 정리해 두었습니다.

## 공개/비공개 경계

이 저장소는 공개 가능한 작업 철학과 품질 기준을 관리합니다. 투자 판단 방식, 개인 선호, 작업 철학, 검수 기준도 공개해도 되는 내용만 남깁니다.

계정 정보, 토큰, 키, 비밀번호, 비공개 원문 전문, 저작권 문제가 있는 긴 발췌, 제3자 민감정보, 계약상 비공개 자료는 공개 대상에서 제외합니다.
