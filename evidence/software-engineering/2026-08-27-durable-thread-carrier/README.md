# Durable-thread carrier representative evaluation

날짜: 2026-08-27

## 결론

이 기록은 PR #42의 정책 수정, 실행 가능한 fixture, 평가 계획, 실제 행동 평가를
분리해 보존한다. fixture와 독립 oracle은 self-test를 통과했고, 연결 문서의 policy
diff는 수동 검토했다. 그러나 기준선과 후보를 실제 Codex model/tool session에서
실행하는 행동 평가는 **수행되지 않았다**. 현재 실행 환경에는 `codex` 실행 파일과
child-agent·durable-thread tool surface가 없었기 때문이다.

따라서 이 evidence는 대표 행동 평가가 통과했다는 증거가 아니다. 실행하지 않은
결과를 통과로 표시하지 않으며, durable-thread 행동 검증은 명시적인 병합 차단
항목으로 남는다.

## 고정 조건

- 평가 ID: `software-engineering-durable-thread-v3`
- 기준선 commit: `aa2ae97856d7968e50511864c03f1babcd608d0d`
- 후보 정책 commit: `8b1e358a3142d2011a4c5ed6c8e735489d8d7f1a`
- 실행 환경: GitHub Actions run `33092751533` / `Linux` / `X64`
- 실행 기록 URL: `https://github.com/Daviswhistle/davis-agent-kit/actions/runs/33092751533`
- `command -v codex` exit: `1`
- model·reasoning effort·sandbox·approval policy: unavailable
- surfaced child-agent tools: unavailable
- surfaced durable-thread tools: unavailable
- fixture self-test: passed (exit `0`)
- evidence-run `python3 scripts/validate_kit.py`: `failed` (exit `1`)

원시 환경은 [`environment-probe.txt`](environment-probe.txt), fixture 실행은
[`fixture-self-test.log`](fixture-self-test.log), 저장소 검증은
[`validate-kit.log`](validate-kit.log), 고정 policy diff는
[`policy-diff.txt`](policy-diff.txt), 수동 의미 검토는
[`manual-policy-review.md`](manual-policy-review.md)에 보존했다.

## 실행 가능한 fixture

[`fixture/task.md`](fixture/task.md)는 모든 사례가 공유하는 동일한 실제 코드 과제다.
[`fixture/setup.py`](fixture/setup.py)는 clean primary repo, mismatch worktree, active-writer
state를 만들고, [`fixture/verify.py`](fixture/verify.py)는 숨겨진 독립 oracle 역할을 한다.
[`fixture/controller.md`](fixture/controller.md)는 baseline/candidate session isolation,
setup, failure injection, trace capture, teardown을 고정한다. reference solution은 oracle의
self-test에만 사용한다.

## 대표 사례

[`cases.json`](cases.json)은 다음 아홉 사례를 각각 독립 실행 단위로 고정한다.

1. ordinary bounded task의 child-agent 기본값
2. 기존 durable context 재사용
3. 여러 root session에 걸친 addressability
4. explicit visible task 요청
5. recovery·ownership-only 음성 사례
6. wrong worktree·branch·revision preflight mismatch
7. activation 전 확정적 거절과 validation-preserving fallback
8. activation 후 transport loss와 fallback 금지
9. active writer 종료·격리가 preflight보다 앞서는지

[`manual-grades.json`](manual-grades.json)은 18개 baseline/candidate 실행을 모두
`not-run`으로 기록한다. fixture self-test와 수동 policy review를 모델 행동 평가로
대체하지 않았다.

## 남은 병합 차단 항목

실제 child-agent와 durable-thread tools가 노출되는 Codex runtime에서 각 사례를
기준선과 후보에 새 문맥으로 실행해야 한다. 최소 원시 근거는 다음과 같다.

- model, reasoning effort, sandbox, approval policy와 전체 tool inventory
- root/carrier tool-call trace, approvals, messages, status changes와 최종 응답
- 각 lifecycle 양성 조건과 recovery·ownership-only 음성 조건의 carrier 선택
- writer quiescence 또는 isolation이 preflight보다 앞선 순서
- read-only preflight, acknowledgement 재대조, 별도 activation의 호출 순서
- mismatch에서 activation·write가 없었다는 근거
- pre-activation fallback과 post-activation fallback 금지의 실제 행동
- fixture oracle 결과와 사례별 수동 판정

이 실행이 완료되기 전에는 PR #42를 행동 검증 완료 상태로 표현해서는 안 된다.
