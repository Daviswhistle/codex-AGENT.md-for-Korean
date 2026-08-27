# Durable-thread carrier representative evaluation

날짜: 2026-08-27

## 결론

이 기록은 PR #42의 정책 수정과 평가 시도를 분리해 보존한다. 선택 조건 통일, read-only preflight, 별도 write activation, fallback, single-writer 경계는 후보 정책에 반영됐다. 그러나 기준선과 후보를 실제 Codex 모델 세션에서 같은 대표 과제로 실행하는 행동 평가는 **수행되지 않았다**. 현재 실행 환경에는 `codex` 실행 파일과 child-agent·durable-thread tool surface가 없었기 때문이다.

따라서 이 evidence는 첫 번째 P1을 통과했다는 증거가 아니다. 실행하지 않은 결과를 통과로 표시하지 않으며, durable-thread 행동 검증은 명시적인 병합 차단 항목으로 남는다.

## 고정 조건

- 평가 ID: `software-engineering-durable-thread-v1`
- 기준선 commit: `aa2ae97856d7968e50511864c03f1babcd608d0d`
- 후보 정책 commit: `f9926ebd6b53945a3cabf516f764af8d1e6c65e1`
- 실행 환경: GitHub Actions run `33087931679` / `Linux` / `X64`
- 실행 기록 URL: `https://github.com/Daviswhistle/davis-agent-kit/actions/runs/33087931679`
- `command -v codex` exit: `1`
- Codex 모델 세션: unavailable
- surfaced child-agent tools: unavailable
- surfaced durable-thread tools: unavailable
- 정적 정책 검사: passed (exit `0`)
- `python3 scripts/validate_kit.py`: `failed` (exit `1`)

원시 환경 확인은 [`environment-probe.txt`](environment-probe.txt), 저장소 검증 출력은 [`validate-kit.log`](validate-kit.log), 정적 정책 검사는 [`static-policy-check.txt`](static-policy-check.txt), 기준선과 후보 정책 diff는 [`policy-diff.txt`](policy-diff.txt)에 보존했다.

## 대표 사례

[`cases.json`](cases.json)은 다음 다섯 사례를 기준선과 후보 모두에 고정한다.

1. ordinary bounded task는 child agent 선택
2. 기존 문맥 재사용·여러 session addressability·사용자의 별도 visible task 요청에서만 durable thread 선택
3. repository·worktree·branch·starting revision acknowledgement 불일치 시 read-only 유지와 write 금지
4. thread 생성·메시징·activation 불가 또는 거절 시 validation을 낮추지 않는 fallback
5. 같은 mutable worktree의 active writer와 repository-state-dependent 작업 직렬화 또는 별도 snapshot/worktree

[`manual-grades.json`](manual-grades.json)은 10개 baseline/candidate 실행을 모두 `not-run`으로 기록한다. 후보 문서가 다섯 경계를 정적으로 포함하는지는 확인했지만, 정적 문구 검토를 모델 행동 평가로 대체하지 않았다.

## 이 평가로 확인한 것

- durable-thread 선택 조건의 문서 간 모순을 제거했다.
- 최초 durable-thread 메시지는 read-only preflight이고, acknowledgement가 일치한 뒤 별도 activation 메시지로만 edit·test·commit 권한을 부여하도록 계약했다.
- activation 실패와 transport 부재 시 child agent 또는 primary fallback을 사용하되 검증 기준을 낮추지 않도록 했다.
- 같은 mutable worktree의 single-writer, stable-reader 경계를 유지했다.
- 저장소 정적 검증 결과와 실제 정책 diff를 보존했다.

## 남은 병합 차단 항목

Codex runtime에서 기준선과 후보를 각 사례마다 새 문맥으로 실행해야 한다. 그 환경은 실제 child-agent와 durable-thread 도구를 노출해야 하며, 최소한 다음 원시 근거를 저장해야 한다.

- 모델, reasoning effort, sandbox, approval policy와 tool surface
- 전체 tool-call trace와 최종 응답
- 생성 권한·read-only handshake·별도 activation의 실제 호출 순서
- mismatch에서 write 호출이 없었다는 근거
- fallback과 worktree 직렬화의 실제 행동
- 사례별 수동 판정과 기준선/후보 diff

이 실행이 완료되기 전에는 PR #42를 행동 검증 완료 상태로 표현해서는 안 된다.
