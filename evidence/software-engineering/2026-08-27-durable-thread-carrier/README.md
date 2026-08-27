# Durable-thread carrier representative evaluation

날짜: 2026-08-27

## 결론

이 기록은 PR #42의 정책 수정과 평가 시도를 분리해 보존한다. 세 lifecycle 조건의 연결 문서 정합성, read-only preflight, 별도 write activation, validation-preserving fallback, single-writer 경계는 후보 정책에 반영됐다. 그러나 기준선과 후보를 실제 Codex 모델 세션에서 같은 대표 과제로 실행하는 행동 평가는 **수행되지 않았다**. 현재 실행 환경에는 `codex` 실행 파일과 child-agent·durable-thread tool surface가 없었기 때문이다.

따라서 이 evidence는 대표 행동 평가가 통과했다는 증거가 아니다. 실행하지 않은 결과를 통과로 표시하지 않으며, durable-thread 행동 검증은 명시적인 병합 차단 항목으로 남는다.

## 고정 조건

- 평가 ID: `software-engineering-durable-thread-v2`
- 기준선 commit: `aa2ae97856d7968e50511864c03f1babcd608d0d`
- 후보 정책 commit: `1020f977ff2a64039a6f59a9db39618dee55d165`
- 실행 환경: GitHub Actions run `33089746491` / `Linux` / `X64`
- 실행 기록 URL: `https://github.com/Daviswhistle/davis-agent-kit/actions/runs/33089746491`
- `command -v codex` exit: `1`
- model·reasoning effort·sandbox·approval policy: unavailable
- Codex 모델 세션: unavailable
- surfaced child-agent tools: unavailable
- surfaced durable-thread tools: unavailable
- 정적 정책 검사: passed (exit `0`)
- `python3 scripts/validate_kit.py`: `failed` (exit `1`)

원시 환경 확인은 [`environment-probe.txt`](environment-probe.txt), 저장소 검증 출력은 [`validate-kit.log`](validate-kit.log), 정적 정책 검사는 [`static-policy-check.txt`](static-policy-check.txt), 기준선과 후보 정책 diff는 [`policy-diff.txt`](policy-diff.txt)에 보존했다.

## 대표 사례

[`cases.json`](cases.json)은 다음 여덟 사례를 기준선과 후보 모두에 독립적으로 고정한다.

1. ordinary bounded task는 child agent 선택
2. 이미 관련된 durable task 문맥 유지·재사용
3. 여러 turn/session에 걸쳐 addressable한 역할
4. persistence가 없어도 사용자가 명시적으로 요청한 별도 visible task
5. recovery·ownership 이점만 있고 세 lifecycle 조건은 없는 음성 사례
6. repository·worktree·branch·starting revision acknowledgement 불일치 시 read-only 유지와 write 금지
7. thread 생성·메시징·activation 불가 또는 거절 시 validation을 낮추지 않는 fallback
8. 같은 mutable worktree의 active writer와 repository-state-dependent 작업 직렬화 또는 별도 snapshot/worktree

[`manual-grades.json`](manual-grades.json)은 16개 baseline/candidate 실행을 모두 `not-run`으로 기록한다. 후보 문서가 여덟 경계를 정적으로 포함하는지는 확인했지만, 정적 문구 검토를 모델 행동 평가로 대체하지 않았다.

## 이 평가로 확인한 것

- root README, skill README, skill 본문과 reference의 durable-thread 선택 계약을 같은 세 lifecycle 조건으로 통일했다.
- recovery·ownership 이점만 있는 음성 사례를 별도로 고정했다.
- 최초 durable-thread 메시지는 read-only preflight이고, acknowledgement가 일치한 뒤 별도 activation 메시지로만 edit·test·commit 권한을 부여하도록 계약했다.
- activation 실패와 transport 부재 시 child agent 또는 primary fallback을 사용하되 검증 기준을 낮추지 않도록 했다.
- 같은 mutable worktree의 single-writer, stable-reader 경계를 유지했다.
- 저장소 정적 검증 결과와 실제 정책 diff를 보존했다.

## 남은 병합 차단 항목

Codex runtime에서 기준선과 후보를 각 사례마다 새 문맥으로 실행해야 한다. 그 환경은 실제 child-agent와 durable-thread 도구를 노출해야 하며, 최소한 다음 원시 근거를 저장해야 한다.

- 모델, reasoning effort, sandbox, approval policy와 tool surface
- 전체 tool-call trace와 최종 응답
- 각 lifecycle 양성 조건과 recovery·ownership-only 음성 조건의 실제 carrier 선택
- 생성 권한·read-only handshake·별도 activation의 실제 호출 순서
- mismatch에서 write 호출이 없었다는 근거
- fallback과 worktree 직렬화의 실제 행동
- 사례별 수동 판정과 기준선/후보 diff

이 실행이 완료되기 전에는 PR #42를 행동 검증 완료 상태로 표현해서는 안 된다.
