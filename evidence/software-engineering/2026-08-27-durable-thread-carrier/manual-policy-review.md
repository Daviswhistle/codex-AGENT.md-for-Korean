# Manual policy diff review

날짜: 2026-08-27
기준선: `aa2ae97856d7968e50511864c03f1babcd608d0d`
후보 정책: `8b1e358a3142d2011a4c5ed6c8e735489d8d7f1a`

이 기록은 자동 문자열 검사 결과가 아니다. primary session이 고정된 policy diff와
연결 문서를 읽고 다음 의미 경계를 수동으로 검토했다.

- ordinary bounded task의 기본 carrier는 child agent다.
- durable thread의 독립 선택 조건은 기존 문맥 재사용, 여러 turn/session의
  addressability, 사용자의 별도 visible task 요청 세 가지뿐이다.
- active writer의 종료 또는 별도 worktree·snapshot 확보가 durable preflight보다 앞선다.
- acknowledgement와 현재 상태를 다시 대조한 뒤 별도 activation으로만 write 권한이
  시작된다.
- activation 전 확정적 실패만 자동 fallback할 수 있다.
- activation 전달 가능성 이후 transport 손실은 fallback이 아니라 blocked 상태이며,
  terminal 또는 명시적 stop과 worktree reconciliation이 선행돼야 한다.
- 구현 carrier와 reviewer independence, primary의 diff·검증 책임은 분리돼 있다.

이 수동 검토는 문서 정합성 판단일 뿐 모델의 실제 carrier 선택이나 tool-call 순서를
증명하지 않는다. 그 근거는 `cases.json`의 baseline/candidate 실행으로 별도 확보해야 한다.
