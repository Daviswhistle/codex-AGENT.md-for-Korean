# Manual policy diff review

날짜: 2026-08-28
기준선: `aa2ae97856d7968e50511864c03f1babcd608d0d`
후보 정책: `a7056f2469b1b8c6ae8cb996f4624e9c333205cd`

이 기록은 자동 문자열 검사 결과가 아니다. Primary session이
[`policy-diff.txt`](policy-diff.txt)에 고정된 baseline→candidate diff를 읽고
연결된 정책·metadata·reference 변경의 의미 경계를 수동으로 검토했다.

diff는 `git diff <baseline> <candidate> -- <9 paths>`로 위 두 commit과 아래
9개 경로만 지정해 생성했다. 고정 결과는 726 lines / 74,332 bytes,
SHA-256 `12af146306ef06f863921716ae87e4a179792660c644b98475ce5dcf3222301b`이며
9 files changed, 367 insertions, 201 deletions이다.

고정 diff에는 다음 직접 연결 파일을 모두 포함한다.

1. `README.md`
2. `skills/README.md`
3. `skills/software-engineering/SKILL.md`
4. `skills/software-engineering/agents/openai.yaml`
5. `skills/software-engineering/references/README.md`
6. `skills/software-engineering/references/execution-delegation.md`
7. `skills/software-engineering/references/tca-loop.md`
8. 삭제된 `skills/software-engineering/references/worker-delegation.md`
9. `decisions/2026-08-27-durable-thread-execution-carrier.md`

수동 검토 결과:

- ordinary bounded task의 기본 carrier는 child agent다.
- durable thread의 독립 선택 조건은 기존 문맥 재사용, 여러 turn/session의
  addressability, 사용자의 별도 visible task 요청 세 가지뿐이다.
- execution mode와 permitted-mutation 문구는 coordination constraint일 뿐 runtime
  enforcement가 아니다. 후보는 prompt-only read-only preflight, acknowledgement,
  activation을 writer 권한 경계로 삼는 방식을 명시적으로 기각한다.
- 구현 경계는 surfaced runtime·worktree identity와 실제 branch, starting revision,
  관측한 worktree status를 대조해 검증한다. Stable dirty state도 clean state와
  구분해 계약에 남긴다.
- read-only carrier와 fixed snapshot은 writer로 승격하지 않는다. 쓰기가 필요하면
  새 writer를 선택하고 기존 writer가 종료된 quiescent mutable target 또는 exact
  starting revision의 별도 mutable worktree·branch를 사용한다.
- implementation-capable instruction이 전달됐을 가능성이 생긴 순간부터 해당
  carrier를 potential active writer로 취급한다. 자동 fallback은 그 전에 creation
  또는 delivery 실패가 확정된 경우에만 허용한다.
- 결합된 create-and-start 호출의 missing/error 응답은 writer가 존재할 수 있는
  ambiguous delivery다. 이 경우나 post-dispatch transport loss 뒤에는 다른 writer를
  시작하지 않는다.
- replacement writer 전에는 surfaced state에서 원 writer의 terminal 상태 또는
  explicit stop을 확인하고, 실제 worktree를 검사·reconcile한 뒤 branch, revision,
  observed status를 새 starting state로 갱신해야 한다. 어느 하나라도 증명할 수
  없으면 blocked 상태를 유지한다.
- 하나의 mutable worktree는 carrier 종류와 무관하게 single-writer, stable-reader
  경계이며 durable thread 자체는 worktree·branch 격리나 독립 reviewer가 아니다.
- 구현에 참여한 carrier는 자기 작업을 승인하지 않는다. Primary session은 사용자
  의도와 task·commit 경계, 실제 diff 확인, 완료 필수 검증의 독립 확인, 최종 완료
  판정을 유지하고 CRA reviewer independence를 별도로 보존한다.
- interface metadata, reference index, 이전 worker 계약 삭제가 새 execution-carrier
  계약과 모순되지 않는다.

이 수동 검토는 문서 정합성 판단일 뿐 모델의 실제 carrier 선택이나 tool-call 순서를
증명하지 않는다. 그 근거는 `cases.json`의 baseline/candidate 실행으로 별도 확보해야
한다.
