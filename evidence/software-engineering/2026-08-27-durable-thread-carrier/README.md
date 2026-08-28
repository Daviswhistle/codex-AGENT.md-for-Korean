# Durable-thread carrier representative evaluation

날짜: 2026-08-28

## 결론

이 기록은 PR #42의 정책 수정, 실행 가능한 fixture, 평가 계획, 실제 행동
평가를 분리해 보존한다. v5 계획은 각 baseline/candidate 실행 전에 지정
commit을 detached checkout으로 만들고 그 checkout 자체의 installer로 fresh
`CODEX_HOME`에 설치한다. External manifest와 measured-session boot attestation이
root `AGENTS.md`, 전체 `software-engineering` tree, `SKILL.md`, interface metadata의
identity를 함께 검증해야 한다.

별도 mutable worktree를 쓰는 active-writer 경로도 isolated oracle 통과만으로
끝나지 않는다. 원래 writer를 종료하고 primary worktree를 reconcile한 뒤 허용된
diff를 commit 없이 primary에 통합하고, 지정된 최종 primary worktree에서 oracle을
다시 통과해야 한다.

기준선과 후보를 실제 Codex model/tool session에서 실행하는 행동 평가는 아직
**수행되지 않았다**. 현재 사용 가능한 환경에는 `codex` 실행 파일과
child-agent·durable-thread tool surface가 없었다. 따라서 실행하지 않은 결과를
통과로 표시하지 않으며 durable-thread 행동 검증은 명시적인 병합 차단 항목으로
남는다.

## 고정 조건

- 평가 ID: `software-engineering-durable-thread-v5`
- 기준선 commit: `aa2ae97856d7968e50511864c03f1babcd608d0d`
- 후보 정책 commit: `4a87005223d235dc29873fbe602445617a52decb`
- 실행 환경과 v5 self-test run: GitHub Actions run `33135915211`
- model·reasoning effort·sandbox·approval policy: unavailable
- surfaced child-agent tools: unavailable
- surfaced durable-thread tools: unavailable
- fixture v5 self-test: passed (exit `0`)
- exact policy install/identity self-test: passed
- isolated-worktree integration self-test: passed
- evidence-run `python3 scripts/validate_kit.py`: failed (exit `1`)

원시 환경은 [`environment-probe.txt`](environment-probe.txt), fixture 실행은
[`fixture-self-test.log`](fixture-self-test.log), 저장소 검증은
[`validate-kit.log`](validate-kit.log), 모든 직접 연결 정책 변경의 고정 diff는
[`policy-diff.txt`](policy-diff.txt), 수동 의미 검토는
[`manual-policy-review.md`](manual-policy-review.md)에 보존한다.

## 실행 가능한 fixture

- [`fixture/install_policy.py`](fixture/install_policy.py)는 지정 commit을 detached
  checkout으로 만들고 fresh `CODEX_HOME`에 설치한 뒤 link target, Git object ID와
  SHA-256 identity를 기록한다.
- [`fixture/controller.md`](fixture/controller.md)는 Codex process가 해당
  `CODEX_HOME`으로 새로 시작되고 measured boot attestation이 external manifest와
  일치해야 한다고 고정한다.
- [`fixture/setup.py`](fixture/setup.py)는 clean primary repository, mismatch
  worktree와 controller state를 만든다.
- [`fixture/verify.py`](fixture/verify.py)는 숨겨진 독립 task oracle이다.
- [`fixture/integrate_worktree.py`](fixture/integrate_worktree.py)는 stopped-writer
  marker와 clean primary 상태를 확인한 뒤 isolated diff를 지정 primary worktree에
  commit 없이 적용하고 integration manifest를 남긴다.
- [`fixture/thread_barrier.py`](fixture/thread_barrier.py)는 activated writer를
  controller release까지 non-terminal 상태로 유지한다.
- [`fixture/self_test.py`](fixture/self_test.py)는 policy identity, premature
  integration rejection, final-primary integration, task oracle, barrier와 teardown을
  함께 검증한다.

## 대표 사례

[`cases.json`](cases.json)은 열 사례와 모든 실행에 공통인 exact-policy loading 및
final-primary completion assertions를 고정한다. Baseline/candidate 20개 행동 실행은
모두 `not-run`이다. Fixture self-test와 수동 policy review를 모델 행동 평가로
대체하지 않는다.

## 남은 병합 차단 항목

실제 child-agent와 durable-thread tools가 노출되는 Codex runtime에서 각 사례를
기준선과 후보에 새 policy checkout·새 `CODEX_HOME`·새 process·새 context·새 mutable
state로 실행해야 한다. 최소 원시 근거는 다음과 같다.

- exact policy-load manifest, launcher environment와 measured boot attestation
- model, reasoning effort, sandbox, approval policy와 전체 tool inventory
- 각 실행의 독립된 run manifest, root/carrier tool-call trace, approvals, messages,
  status changes와 최종 응답
- 각 lifecycle 양성 조건과 recovery·ownership-only 음성 조건의 carrier 선택
- cross-session handoff artifact와 같은 thread ID의 readdressability
- writer quiescence 또는 별도 mutable worktree가 writable preflight보다 앞선 순서
- read-only preflight, acknowledgement 재대조, 별도 activation의 호출 순서
- mismatch thread에 activation·write가 없고 blocked 또는 허용 fallback이 정확히
  수행됐다는 근거
- barrier 뒤에 주입된 post-activation loss와 fallback 금지의 실제 행동
- isolated 결과의 stopped/reconciled primary 통합과 final-primary oracle 결과
- 사례별 수동 판정

이 실행이 완료되기 전에는 PR #42를 행동 검증 완료 상태로 표현해서는 안 된다.
