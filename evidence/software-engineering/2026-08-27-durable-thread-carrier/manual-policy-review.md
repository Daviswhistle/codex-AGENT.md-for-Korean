# Manual policy diff review

날짜: 2026-08-28
기준선: `aa2ae97856d7968e50511864c03f1babcd608d0d`
후보 정책: `4a87005223d235dc29873fbe602445617a52decb`

이 기록은 자동 문자열 검사 결과가 아니다. Primary session이
[`policy-diff.txt`](policy-diff.txt)에 고정된 baseline→candidate diff를 읽고
연결된 정책·metadata·reference 변경의 의미 경계를 수동으로 검토했다.

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
- 최초 durable-thread turn은 read-only preflight이며 acknowledgement와 현재 상태를
  다시 대조한 뒤 별도 activation으로만 write 권한이 시작된다.
- fixed commit snapshot은 read-only source일 뿐 writable worktree가 아니며, 그
  preflight를 edit·상태 변경 test·commit activation으로 승격할 수 없다.
- writable thread는 기존 writer 종료 후 새로 읽은 mutable worktree 또는 별도
  mutable worktree·branch를 사용해야 한다.
- activation 전 확정적 실패만 자동 fallback할 수 있다.
- activation 전달 가능성 이후 transport 손실은 fallback이 아니라 blocked 상태이며,
  terminal 또는 명시적 stop과 worktree reconciliation이 선행돼야 한다.
- 구현 carrier와 reviewer independence, primary의 diff·검증 책임은 분리돼 있다.
- interface metadata, reference index, 이전 worker 계약 삭제가 새 execution-carrier
  계약과 모순되지 않는다.

이 수동 검토는 문서 정합성 판단일 뿐 모델의 실제 carrier 선택이나 tool-call 순서를
증명하지 않는다. 그 근거는 `cases.json`의 baseline/candidate 실행으로 별도 확보해야
한다.
