# Outcome Owner Skill

사용자의 장기 목표를 한 턴의 작업으로 소모하지 않고, 목표·목적·제약·진행 근거·소유권 lease·완료 상태를 로컬 SQLite에 보존하는 Codex 스킬입니다.

이 스킬은 모델이 더 주체적으로 판단하도록 돕되 행동 권한을 넓히지는 않습니다. 사용자는 한 명의 메인 owner와 대화하고, owner는 목적과 성공 기준을 유지하면서 필요한 조사·구현·검증을 주도합니다. 외부 쓰기와 비가역 작업은 여전히 별도 승인이 필요합니다.

## 구성

- `SKILL.md`: 목표 소유, 복구, 위임, 검증, 완료 계약
- `scripts/outcome_ledger.py`: Python 3.11 표준 라이브러리만 사용하는 로컬 상태 CLI
- `tests/test_outcome_ledger.py`: idempotency, lease, 상태 전이, 완료 증거, 권한 경계 검증
- `agents/openai.yaml`: Codex 스킬 인터페이스

helper는 Codex·Git·shell을 실행하거나 네트워크를 호출하거나 프로젝트 파일을 수정하지 않습니다. 오직 control state만 관리합니다.

## 로컬 개인정보 경계

기본 DB는 `${CODEX_HOME:-~/.codex}/outcome-owner/objectives.sqlite3`입니다. DB는 관리 대상인 모든 저장소 바깥의 전용 경로에 있어야 합니다. 새 `start`의 `--db`와 `--repo-root`가 중첩되면 디렉터리나 DB를 만들기 전에 거부하고, 기존 ledger의 중첩은 안정된 read-only 복사본에서 확인해 원본을 read-write로 열기 전에 거부합니다. POSIX에서는 새 기본 디렉터리를 `0700`으로 만들고 DB main·WAL·SHM·rollback journal을 각각 `0600`으로 유지합니다. 식별된 기존 ledger의 main 또는 sidecar가 다른 mode이면 원본을 read-write로 열거나 mode를 바꾸기 전에 `unsafe_database_permissions`로 거부합니다. 내용 자체는 암호화되지 않은 로컬 평문입니다.

DB에는 고정 SQLite application ID와 schema version이 기록됩니다. 기존 파일은 원본을 read-write로 열기 전에 관리 대상 저장소와 분리된 전용 control temp root에 main, rollback journal, WAL의 안정된 복사본을 만들고 그 복사본만 복구해 유효 식별자, 전체 v1 table·constraint·index 정의, 저장된 JSON·hash·transition 이력·행 불변식을 하나의 read snapshot에서 확인합니다. POSIX의 root는 `/tmp/.outcome-owner-preflight-<uid>`이고 mode는 `0700`이며, 다른 플랫폼은 `~/.codex/outcome-owner/preflight`를 사용합니다. 새 mission의 저장소가 이 root를 포함하면 state를 만들기 전에 거부합니다. clone은 `0600`이고 정상 종료 때 제거됩니다. 강제 종료가 일어나면 이 private root 아래에는 clone이 남을 수 있지만 프로젝트 안에는 남지 않습니다. ledger process가 실행 중이지 않음을 확인한 뒤에만 stale clone을 정리합니다. `TMPDIR` 같은 process 설정을 따르지 않습니다. 복사 전후 원본 file-set과 inode, 크기, 수정 시각, content digest가 달라지면 한 번만 다시 시도한 뒤 `database_busy`로 닫힙니다. 따라서 지원하지 않거나 다른 애플리케이션의 상태, 부분 schema, 불가능한 mission 상태, 손상된 행은 원본 DB·sidecar·권한을 바꾸지 않고 거부하면서, 식별된 ledger의 정상 rollback journal과 WAL은 이후 원본에서 복구할 수 있습니다. 초기 식별자는 rollback-journal transaction으로 main header에 먼저 확정한 뒤 WAL로 전환합니다. `--db`에는 다른 용도의 SQLite 파일을 재사용하지 마세요.

목표·이벤트·완료 요약에 토큰, 키, 비밀번호, 인증 정보, 비공개 원문, 고객 데이터 또는 불필요한 민감정보를 넣지 마세요. 민감한 증거는 안전한 원본 위치와 비민감 식별자만 기록합니다.

## 사용 예시

아래 값은 모두 비밀이 아닌 예시 placeholder입니다. 스킬 폴더에서 실행합니다.

```bash
python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 start \
  --objective "<사용자가 원하는 결과>" \
  --purpose "<이 결과가 중요한 이유 또는 유지할 판단 원칙>" \
  --desired-state "<완료 뒤 관측 가능한 상태>" \
  --success-criterion "<검증 가능한 기준 1>" \
  --success-criterion "<검증 가능한 기준 2>" \
  --constraint "<지켜야 할 제약 1>" \
  --constraint "<지켜야 할 제약 2>" \
  --repo-root /path/to/existing/repository \
  --authority local-write \
  --idempotency-key example-start-001
```

성공 응답의 `mission.id`를 이후 `<mission-id>`에 사용합니다.

같은 filesystem identity(device, inode, stable creation identity), 같은 canonical 경로, 해당 filesystem의 대소문자 규칙으로 같은 경로, 또는 ancestor·descendant 관계인 저장소 범위에서는 `local-write` claim 하나만 허용됩니다. 따라서 path alias, case-insensitive 경로 표기, inode가 즉시 재사용된 디렉터리 교체, 부모 repo와 그 하위 디렉터리의 중복 writer를 모두 보호합니다. 반대로 case-sensitive filesystem의 서로 다른 case-only 디렉터리와 독립 sibling/worktree는 충돌하지 않습니다. `read-only` claim끼리는 중첩 경로에서도 공존할 수 있지만 active `local-write` claim과는 충돌합니다.

claim은 writer transaction 안에서 대상 mission과 권한상 충돌할 수 있는 모든 active mission의 저장소 경로를 다시 resolve·stat합니다. stable creation identity는 Linux의 opaque file handle을 우선하고 지원되지 않으면 native birth/creation identity를 사용합니다. 시작 때 선택한 identity 종류를 계약에 고정해 이후에도 같은 종류로 대조하므로, 더 우선하는 OS 기능이 일시적으로 복구되어도 저장소 교체로 오판하지 않습니다. 반대로 기록된 종류를 더는 읽을 수 없으면 다른 종류로 갈아타지 않고 fail closed합니다. case 판정은 case-variant alias를 따라가기 전에 정확히 구분되는 directory entry인지 확인하므로, 나중에 사라지는 symlink가 case 계약을 오염시키지 않습니다. 프로젝트에 sentinel을 쓰지 않으며 Git metadata는 복사·재생성될 수 있어 filesystem identity의 대체물로 사용하지 않습니다. 안전한 creation identity를 얻을 수 없는 filesystem에서는 `start`를 `repo_identity_unavailable`로 거부합니다. `heartbeat`와 새 event·state mutation도 대상 binding을 확인한 뒤에만 기록합니다. canonical 경로, directory 여부, filesystem identity, case semantics 또는 path key가 시작 계약과 달라졌으면 `repo_binding_mismatch`로 lease 부여·연장·새 기록을 중단합니다. 과거 idempotent replay는 읽기만 하며, 이동·교체된 저장소의 기존 lease는 `release`로 정리한 뒤 실제 상태를 대조해 새 mission을 시작합니다.

각 ownership 실행은 재사용하지 않는 새 owner ID를 만듭니다. 예를 들어 로컬 UUID를 `<execution-owner-id>`로 사용합니다. claim에는 직전에 관측한 `mission.lease_generation`과 `mission.version`을 각각 `--expected-generation`, `--expected-version`으로 전달합니다. 성공한 claim 응답의 `mission`은 같은 writer transaction에서 확인한 현재 snapshot이고, `lease.generation`은 해당 실행의 fencing token입니다. 이 token은 `heartbeat`, `record`, `transition`, `release`에 반드시 그대로 전달합니다.

```bash
python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 claim \
  <mission-id> --owner <unique-execution-owner-id> \
  --expected-generation 0 --expected-version 1 --ttl-seconds 900

python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 record \
  <mission-id> --owner <unique-execution-owner-id> --lease-generation 1 \
  --kind checkpoint --summary "현재 checkout과 diff를 확인했다" \
  --metadata-json '{"validation":"not-run"}' \
  --idempotency-key example-checkpoint-001

python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 heartbeat \
  <mission-id> --owner <unique-execution-owner-id> \
  --lease-generation 1 --ttl-seconds 900
```

재시작 뒤에는 먼저 상태와 실제 작업물을 대조합니다.

```bash
python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 show \
  <mission-id> --events-limit 100

python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 list \
  --state active --repo-root /path/to/existing/repository
```

`list --repo-root`는 저장된 canonical 경로와 filesystem-aware path key를 대조하고, 현재 경로가 존재하면 filesystem identity도 대조합니다. 따라서 case-insensitive alias나 저장소 디렉터리가 이동된 뒤의 새 경로로도 기존 mission을 찾을 수 있습니다.

검증 단계와 완료는 분리합니다. `complete`에는 가장 최근 `verifying` 전이 뒤에 새로 기록한 `evidence` 이벤트와 완료 요약이 필요합니다.

```bash
python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 transition \
  <mission-id> --owner <unique-execution-owner-id> --lease-generation 1 \
  --to verifying --expected-version 1 \
  --summary "성공 기준별 최종 검증을 시작한다" \
  --idempotency-key example-verifying-001

python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 record \
  <mission-id> --owner <unique-execution-owner-id> --lease-generation 1 \
  --kind evidence --summary "요구된 검증이 통과했고 diff를 확인했다" \
  --idempotency-key example-evidence-001

python3 scripts/outcome_ledger.py --db /tmp/outcome-owner-example/objectives.sqlite3 transition \
  <mission-id> --owner <unique-execution-owner-id> --lease-generation 1 \
  --to complete --expected-version 2 \
  --summary "성공 기준을 모두 확인했다" \
  --completion-summary "요청된 결과와 검증 근거를 전달했다" \
  --idempotency-key example-complete-001
```

generation과 version 값은 예시입니다. claim의 두 expected 값은 직전 `start`, `show`, 성공한 `claim` 또는 `transition`의 current `mission` snapshot에서 가져옵니다. 이후 mutation의 `--lease-generation`은 성공한 claim의 `lease.generation`, 전이의 `--expected-version`은 가장 최근 current `mission.version`을 사용합니다. generation 또는 version conflict가 나면 현재 상태와 실제 증거를 다시 대조하고 숫자만 바꿔 재시도하지 않습니다. lease가 만료·해제되거나 새 실행이 인수하면 새 owner ID로 claim하며 generation이 증가합니다. 이전 실행은 같은 owner 문자열을 알고 있어도 stale generation 때문에 mutation할 수 없습니다.

시스템 wall clock이 뒤로 이동해도 mutation timestamp는 해당 mission과 lease의 마지막 영속 시각보다 작아지지 않는 logical time을 사용합니다. lease 만료 여부는 transaction lock을 얻은 뒤 관측한 실제 wall clock으로 판단하므로 clock rollback은 기존 lease를 보수적으로 더 오래 유지할 수 있지만, timestamp 순서를 깨뜨리거나 조기 takeover를 허용하지 않습니다.

`transition` 응답의 `event_effect.lease_released`는 해당 전이 이벤트가 발생했을 때의 효과입니다. `mission`과 `active_lease`는 같은 transaction에서 읽은 현재 상태이므로, 오래된 idempotent 전이를 replay한 뒤에는 과거 이벤트가 lease를 해제했더라도 현재 `active_lease`가 존재할 수 있습니다. `waiting`, `blocked`, `interrupted` 같은 비종료 released state에서 발견되는 lease는 그 state에 들어간 generation보다 새 generation이어야 하므로, 해제 전의 오래된 lease를 다시 끼워 넣은 상태는 source를 열기 전에 거부됩니다.

mission의 목표 계약 필드는 불변입니다. 사용자 steering으로 목표·목적·완료 상태·성공 기준·제약·저장소·권한이 실질적으로 바뀌면 event를 숨은 덮어쓰기로 사용하지 않습니다. 기존 mission에 교체 결정을 기록하고 새 idempotency key로 replacement mission을 만든 뒤, 기존 목표가 실제로 무효가 된 경우에만 기존 mission을 `abandoned`로 전이해 lease를 해제합니다. 그 다음 replacement를 claim하고 기존 mission ID를 기록합니다. 중간에 중단되면 두 mission을 함께 대조해 하나의 유효한 계약만 이어갑니다.

모든 성공 명령은 JSON을 stdout에 출력합니다. 계약 위반과 충돌은 nonzero로 종료하며 JSON 오류를 stderr에 출력합니다. wire JSON은 비ASCII 문자를 escape하므로 ASCII `PYTHONIOENCODING`에서도 mutation 뒤 출력 실패 없이 기계 판독할 수 있습니다. 전체 명령은 다음과 같습니다.

```text
start  list  show  claim  heartbeat  record  transition  release
```

## 검증

저장소 루트에서 실행합니다.

```bash
python3 -m unittest discover -s skills/outcome-owner/tests -p 'test*.py' -v
python3 scripts/validate_kit.py
```
