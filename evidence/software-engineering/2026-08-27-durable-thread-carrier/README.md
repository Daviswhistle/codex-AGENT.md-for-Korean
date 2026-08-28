# Durable-thread carrier representative evaluation

날짜: 2026-08-28

## 결론

이 기록은 PR #42의 정책 수정, 실행 가능한 fixture, 평가 계획, 실제 행동 평가를
분리해 보존한다. v4 계획은 각 baseline/candidate 실행에 완전히 독립된 상태를
부여하고, cross-session handoff와 post-activation transport loss에 명시적
controller barrier를 사용한다. 또한 preflight mismatch의 blocked 경로와 안전한
fallback 경로를 각각 독립 사례로 고정한다.

기준선과 후보를 실제 Codex model/tool session에서 실행하는 행동 평가는 아직
**수행되지 않았다**. 현재 사용 가능한 환경에는 `codex` 실행 파일과
child-agent·durable-thread tool surface가 없었다. 따라서 실행하지 않은 결과를
통과로 표시하지 않으며 durable-thread 행동 검증은 명시적인 병합 차단 항목으로
남는다.

## 고정 조건

- 평가 ID: `software-engineering-durable-thread-v4`
- 기준선 commit: `aa2ae97856d7968e50511864c03f1babcd608d0d`
- 후보 정책 commit: `4a87005223d235dc29873fbe602445617a52decb`
- 실행 환경과 v4 self-test run: GitHub Actions run `33133238362`
- model·reasoning effort·sandbox·approval policy: unavailable
- surfaced child-agent tools: unavailable
- surfaced durable-thread tools: unavailable
- fixture v4 self-test: passed (exit `0`)
- evidence-run `python3 scripts/validate_kit.py`: failed (exit `1`)

원시 환경은 [`environment-probe.txt`](environment-probe.txt), fixture 실행은
[`fixture-self-test.log`](fixture-self-test.log), 저장소 검증은
[`validate-kit.log`](validate-kit.log), 모든 직접 연결 정책 변경의 고정 diff는
[`policy-diff.txt`](policy-diff.txt), 수동 의미 검토는
[`manual-policy-review.md`](manual-policy-review.md)에 보존한다.

## 실행 가능한 fixture

[`fixture/task.md`](fixture/task.md)는 모든 사례가 공유하는 동일한 실제 코드 과제다.
[`fixture/setup.py`](fixture/setup.py)는 각 실행마다 clean primary repository,
mismatch worktree, controller state를 만든다.
[`fixture/verify.py`](fixture/verify.py)는 숨겨진 독립 oracle 역할을 한다.
[`fixture/thread_barrier.py`](fixture/thread_barrier.py)는 activated thread를 명시적
controller release까지 non-terminal 상태로 유지한다.
[`fixture/controller.md`](fixture/controller.md)는 다음을 고정한다.

- baseline과 candidate 각각의 독립된 `RUN_DIR`, `CODEX_HOME`, root/model context,
  thread/task identity와 contract ID
- cross-session addressability의 Session A 종료 지점과 Session B 전체 입력
- activation 전 거절과 activation 후 transport loss의 서로 다른 failure injection
- active writer와 writable durable preflight의 순서
- trace capture, terminal confirmation, reconciliation, teardown

Reference solution은 oracle의 self-test에만 사용한다.

## 대표 사례

[`cases.json`](cases.json)은 다음 열 사례를 각각 독립 실행 단위로 고정한다.

1. ordinary bounded task의 child-agent 기본값
2. 기존 durable context 재사용
3. 두 fresh root session 사이의 정확한 durable-role handoff
4. explicit visible task 요청
5. recovery·ownership-only 음성 사례
6. mismatch에서 write 없이 blocked 종료
7. mismatch에서 write 없이 허용된 bounded fallback
8. activation 전 확정적 거절과 validation-preserving fallback
9. barrier에 머문 activated writer의 transport loss와 fallback 금지
10. writable thread에서 active writer 종료 또는 별도 mutable worktree가
    preflight보다 앞서는지

[`manual-grades.json`](manual-grades.json)은 20개 baseline/candidate
실행을 모두 `not-run`으로 기록한다. Fixture self-test와 수동 policy review를 모델
행동 평가로 대체하지 않는다.

## 남은 병합 차단 항목

실제 child-agent와 durable-thread tools가 노출되는 Codex runtime에서 각 사례를
기준선과 후보에 새 문맥·새 mutable state로 실행해야 한다. 최소 원시 근거는 다음과
같다.

- model, reasoning effort, sandbox, approval policy와 전체 tool inventory
- 각 실행의 독립된 run manifest, root/carrier tool-call trace, approvals, messages,
  status changes와 최종 응답
- 각 lifecycle 양성 조건과 recovery·ownership-only 음성 조건의 carrier 선택
- cross-session handoff artifact와 같은 thread ID의 재addressability
- writer quiescence 또는 별도 mutable worktree가 writable preflight보다 앞선 순서
- read-only preflight, acknowledgement 재대조, 별도 activation의 호출 순서
- mismatch thread에 activation·write가 없고 blocked 또는 허용 fallback이 정확히
  수행됐다는 근거
- barrier 뒤에 주입된 post-activation loss와 fallback 금지의 실제 행동
- fixture oracle 결과와 사례별 수동 판정

이 실행이 완료되기 전에는 PR #42를 행동 검증 완료 상태로 표현해서는 안 된다.
