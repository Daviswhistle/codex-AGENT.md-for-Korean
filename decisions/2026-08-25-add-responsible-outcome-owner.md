# 책임 있는 Outcome Owner 추가

날짜: 2026-08-25

## 결정

사용자가 비사소한 목표를 모델에게 맡기고 책임 있게 끝까지 수행하기를 원하거나, 여러 턴·중단·위임 사이에서 목적과 완료 근거가 유실될 위험이 있을 때 `outcome-owner` 스킬을 사용한다.

구조는 하나의 사용자 대면 owner, Codex의 기존 실행·위임 기능, 로컬 control-state ledger로 제한한다. 별도 planning 모델, 상주 daemon, scheduler, worker pool, 웹 UI, shell/Git 실행기, 네트워크 서비스는 만들지 않는다. 모델이 주체적으로 판단하는 데 필요한 것은 두 번째 오케스트레이션 런타임이 아니라 목적과 권한, 현재 소유자, 실제 근거, 완료 조건을 잃지 않는 통제 계층이기 때문이다.

짧고 원자적인 답변이나 작업에는 ledger를 만들지 않는다. 영구 상태의 비용보다 목적 유실 위험이 클 때만 사용한다.

## 책임과 권한

모델은 확인된 근거와 현재 권한 안에서 최선의 실행 경로를 선택하고, 직접 필요한 조사·구현·검증·통합·완료 판정을 소유한다. 선택지를 사용자에게 되돌리는 것으로 책임을 피하지 않는다.

사용자는 가치 선택과 권한 경계를 소유한다. push, 배포, 마이그레이션, 외부 메시지, 구매·유료 행동, 운영 데이터 변경, 파괴적 작업, 실질적 범위 확대는 기존 승인 경계를 그대로 유지한다. 주체성은 권한 확대가 아니다.

## Ledger 계약

`skills/outcome-owner/scripts/outcome_ledger.py`는 Python 표준 라이브러리만 사용하는 로컬 SQLite CLI이며 다음 control state만 관리한다.

- 목표, 목적, 원하는 상태, 관측 가능한 성공 기준, 제약, 저장소, 권한
- mission 상태와 버전
- 한 번에 한 owner만 mutation할 수 있는 lease와 fencing generation
- checkpoint, 결정, 근거, 위험, blocker, 기회, 복구 event
- 검증 단계 뒤 현재 lease에서 새로 기록한 완료 근거

helper는 Codex, shell, Git, worktree, 네트워크 또는 프로젝트 파일을 실행·수정하지 않는다. `local-write` mission은 device·inode·stable creation identity, canonical path, filesystem-aware case key와 ancestor·descendant 범위로 배타화하고 `read-only` mission끼리만 공존시킨다. creation identity는 시작 시 선택한 종류까지 고정해 같은 종류로 재검증한다. 안전한 creation identity를 읽을 수 없는 filesystem에서는 mission 생성을 거부하며, claim은 관측한 mission version과 lease generation을 함께 요구해 기다리는 사이 상태가 바뀐 stale owner도 차단한다. wall clock이 뒤로 이동해도 mutation은 영속 시각보다 작아지지 않는 logical time을 사용하고, lease 유효성은 writer lock 뒤의 실제 wall clock으로 판단한다.

완료는 `active -> verifying -> complete`로 분리한다. 최신 `verifying` 전이 이후, 현재 lease generation 아래 기록된 새 `evidence`가 없으면 완료할 수 없다. 중단 뒤에는 저장소·산출물·테스트·허용된 외부 근거를 먼저 대조하고 새 owner ID와 generation으로 인수한다.

DB는 로컬 평문이므로 비밀값과 비공개 원문을 기록하지 않는다. 기존 DB는 read-write open 전에 관리 저장소와 분리된 고정 private control temp root에 main, rollback journal, WAL의 안정된 copy를 만들고 그 복사본만 복구·식별하며, process 임시 경로를 사용하지 않는다. 새 mission의 저장소가 이 root를 포함하면 생성 전에 거부한다. POSIX root는 사용자별 `0700`, clone은 `0600`이며 정상 종료 때 지운다. 강제 종료 residue는 private root에는 남을 수 있지만 프로젝트에는 남지 않는다. 다른 애플리케이션·미지원 schema·손상·동시 변경은 원본을 고치지 않고 fail closed한다. POSIX의 식별된 main·WAL·SHM·rollback journal은 각각 mode `0600`이어야 하며, 더 열린 기존 mode는 원본을 고치지 않고 거부한다. released state의 lease는 그 state 진입 generation보다 새로워야 하며, case 판정은 case-variant alias보다 정확한 directory entry 구분을 우선한다.

## 행동 계약 보강

전역 계약에는 다음을 명시했다.

- 근거와 권한이 충분한 구현 판단을 모델이 소유한다.
- 저장소의 지도·색인·계약이 현재 목적과 연결된 검증 근거를 가리키면 최소 범위로 확인한다.
- 사용자 입력·출력 계약을 바꾸면 구현, 공개 schema, 예시, 문서, 테스트의 실제 의미를 함께 맞춘다.
- 중요한 선택 기회는 무단 구현하지 않되, 산문형 완료 보고에서 근거·효과·비용·위험·최소 가역 실험을 구체값으로 구분해 보존한다.
- 엄격한 출력 계약은 선택 설명으로 오염시키지 않는다.

## 행동 평가

2026-08-13 결정이 요구한 9개 사례, 기준선·후보 18개 독립 실행을 완료했다. 최종 후보는 자동 판정 9/9, 수동 판정 9/9, hard failure 0이었다. 기준선은 자동 8/9, 수동 7/9였으며, 후보는 직접 정합성과 중요한 기회 보고를 개선하고 나머지 사례에서 회귀가 없었다.

원시 trace, 최종 응답, 자동 grade, 실행 metadata, 사례별 수동 판정은 `evidence/outcome-ownership/2026-08-25/`에 보존했다. 평가 러너는 제품 코드가 아니므로 로컬 브랜치 `evaluation/outcome-owner-2026-08-25`에 고정했다.

## 한계와 다시 볼 조건

- 행동 평가는 고정 profile에서 사례별 한 번의 대표 표본이며 미래 행동을 결정론적으로 보장하지 않는다.
- ledger는 현재 전체 event history를 한 번에 읽으므로 control state를 작게 유지한다. 실제 사용에서 크기가 커지면 bounded pagination을 검토한다.
- capture 직후 외부 process가 DB를 바꾸는 일반적인 filesystem TOCTOU를 완전히 제거하지는 못한다. capture 중 변화는 재시도 후 fail closed하며, ledger는 한 사용자·한 머신의 작은 control DB라는 경계 안에서 사용한다.
- stable creation identity를 제공하지 않는 filesystem에서는 mission을 시작할 수 없다. 현재 Linux 로컬 filesystem에서는 opaque file handle을 우선하며, 지원되지 않으면 filesystem generation이나 native birth/creation time을 사용한다.
- wall clock rollback은 기존 lease를 보수적으로 더 오래 유지할 수 있다. 이는 조기 takeover보다 안전을 택한 결과이며, timestamp 순서와 fencing은 유지한다.
- 실제 사용에서 ledger가 목적 보존보다 의식적 절차를 더 늘리거나, 중요 기회 보고가 과도해지거나, 재개 실패가 발견되면 스킬 적용 범위와 schema를 다시 검토한다.
