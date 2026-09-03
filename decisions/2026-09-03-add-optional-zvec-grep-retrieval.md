# 선택적 zvec-grep 저장소 검색 계층 추가

날짜: 2026-09-03

결정: `software-engineering` 스킬의 trigger와 실행 계약에 독립적인 저장소 탐색을 포함하고, 위치나 표현을 모르는 의미 검색·아키텍처·데이터 흐름·여러 파일 합성이 필요할 때 이미 설치되고 색인된 zvec-grep을 선택적으로 사용한다. 정확한 식별자나 경로가 알려진 작업과 이미 위치가 특정된 작업은 기존 직접 읽기와 `rg`를 유지한다. Davis Agent Kit가 관리하는 Codex 환경에는 upstream 전체 설치기 대신 `config.toml`의 MCP 항목만 관리하는 별도 도우미를 제공한다.

배경: 기존 스킬은 실행 위임과 CRA/TCA에는 구체적인 계약이 있지만, 실행 범위를 정하기 전 저장소를 어떻게 탐색할지는 명시하지 않았다. 정확한 문자열을 모르는 아키텍처·호출 흐름 질문에서 에이전트가 여러 번 `rg`, 디렉터리 순회, 광범위한 파일 읽기를 반복하면 도구 호출과 문맥 사용량이 커지고 시작 키워드에 따라 중요한 경로를 놓칠 수 있다. zvec-grep은 exact search, BM25, vector search를 한 로컬 우선 인터페이스로 결합하므로 이 병목을 줄일 후보가 된다.

동시에 upstream Codex 설치기는 `${CODEX_HOME:-$HOME/.codex}/config.toml`뿐 아니라 `AGENTS.md`에도 관리 블록을 기록한다. Davis Agent Kit 설치는 그 `AGENTS.md`를 저장소의 규범 원본에 연결하는 심링크로 사용하며, upstream 원자적 쓰기는 심링크를 따라 실제 원본을 수정한다. 그대로 사용하면 외부 설치기가 규범 원본에 도구별 지침을 삽입해 원본 소유권과 설치 계약을 깨뜨린다.

경계:

1. zvec-grep은 선택적 검색 계층이지 키트의 필수 런타임 의존성이 아니다. 설치되지 않았거나 색인이 없거나 결과가 부적합하면 직접 읽기와 native exact search로 폴백한다.
2. 이미 파일과 범위가 알려졌거나 정확한 anchor만 찾으면 되는 작업에는 의미 검색을 추가하지 않는다.
3. 의미 검색 결과는 후보 근거다. 변경 전에는 결정적인 정의, 호출부, 조건, 생성 여부와 주변 프로젝트 지침을 원문에서 확인한다.
4. 패키지 설치, daemon 시작, persistent index 생성·재생성·수동 강제 갱신·삭제, index lifecycle 정책 변경, 원격 embedding 승인과 provider credential 변경은 자동으로 수행하지 않는다. 기존 index가 이미 설정된 background freshness 정책에 따라 일반 검색 중 갱신되는 것은 허용하되, 에이전트가 그 정책을 바꾸거나 lifecycle tool을 호출하지 않는다.
5. 원격 embedding은 MCP 사용 승인과 별개이며, 같은 workspace에 대한 사용자의 명시적 승인이 없으면 query나 source content를 외부 provider로 보내지 않는다.
6. 설정 도우미는 `config.toml`의 완전하고 배타적인 관리 블록만 추가·갱신·제거한다. 다른 TOML, config 심링크, `AGENTS.md`는 보존하며, marker 안의 무관한 key·table, table·dotted key·inline table 형태를 포함한 비관리 zvec-grep 정의, marker 밖에서 관리 table을 의미상 확장하는 key·nested table, 유효하지 않은 TOML 또는 손상된 marker가 있으면 덮어쓰지 않고 중단한다.
7. MCP는 의미 검색만 제공하는 `agent` toolset으로 제한하고 정확 검색은 Codex의 native route에 남긴다.
8. 저장소 전체 색인이 필요하지 않은 국소 작업을 zvec-grep 부재 때문에 지연하거나 실패 처리하지 않는다.
9. 설정 문서는 어느 workspace에서 읽더라도 동작하도록 Codex에 설치된 `software-engineering` skill 경로에서 도우미를 실행한다. 사용자가 명시한 `~/...` 또는 `./...` executable path는 절대 경로로 정규화해 Codex 설정에 저장한다.

대안:

1. upstream `zg install --target codex`를 그대로 사용하고 생성된 `AGENTS.md` 블록을 규범 원본에 받아들인다.
2. zvec-grep 설치기 실행 뒤 매번 `AGENTS.md` 변경을 수동으로 되돌린다.
3. 키트 설치 과정에서 npm package와 모든 workspace index를 자동으로 설치·생성한다.
4. 설정 도우미 없이 문서에 수동 TOML 편집만 안내한다.
5. zvec-grep을 도입하지 않고 `rg`와 파일 읽기만 유지한다.

이유: 저장소 탐색 자체를 skill trigger에 넣고 검색 판단을 스킬에 두면 특정 외부 설치기가 전역 규범 원본을 소유하지 않으면서도 에이전트가 독립적인 분석 요청과 수정 작업 모두에서 의미 검색을 사용할 조건과 중단 조건을 일관되게 적용할 수 있다. 설정 전용 도우미는 upstream과의 핵심 충돌을 제거하고, TOML 구조 전체를 기준으로 한 관리 범위 검증·비관리 설정 거부·결과 재파싱·실행 경로 정규화·원자적 쓰기·심링크 보존·반복 실행 검증을 코드로 고정한다. 반면 패키지와 색인을 선택 사항으로 남기면 작은 저장소와 국소 변경에 불필요한 런타임·저장공간·개인정보 비용을 부과하지 않는다.

나중에 다시 볼 조건:

- zvec-grep이 Codex에서 `config.toml`만 설치하는 공식 모드를 제공하거나 `AGENTS.md` 비수정 옵션을 제공한다.
- Codex의 MCP 설정 schema나 zvec-grep의 stdio arguments가 바뀐다.
- 대표 저장소 이해 과제에서 semantic route가 도구 호출, 입력 token, 시간 또는 정답 품질을 개선하지 못한다.
- index freshness 때문에 현재 작업 내용을 반복해서 놓치거나 exact verification 비용이 오히려 커진다.
- 로컬 embedding의 품질·자원 사용 또는 remote authorization 경계가 운영 환경에 맞지 않는다.
