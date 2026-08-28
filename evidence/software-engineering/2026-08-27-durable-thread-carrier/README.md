# Durable-thread runtime-boundary representative evaluation

날짜: 2026-08-28

## 결론

평가된 로컬 후보 `a7056f2469b1b8c6ae8cb996f4624e9c333205cd`는 v6 런타임
경계 대표 사례 10개를 모두 통과해 **행동 기준으로 준비됨**으로 판정한다. 기준선
`aa2ae97856d7968e50511864c03f1babcd608d0d`는 4 pass / 5 fail / 1
`invalid-or-unsupported`, 후보는 10 pass / 0 fail / 0 invalid이며 manifest
오류는 0건이다.

다만 원격 PR head `1e914444`는 평가한 로컬 후보가 아니다. 지금 원격 head를 바로
병합하지 말고, `a7056f2`와 이 증거 변경을 게시한 뒤 CI와 blocking review를 다시
통과시켜야 한다.

## 동결된 평가 경계

- 평가 ID: `software-engineering-durable-thread-v6-runtime-boundary`
- 실행 harness SHA-256: `2c5910b7870d8befe33d205dbab19a0434c211e614766034cbc15f433906417b`
- 독립 grader SHA-256: `924d9ac42a95fbe3c86ecd0397ae8b55c13cb15aae0fbba79708935fa43b02da`
- 최종 manifest SHA-256: `fded79e1ab82e775ebb9c8be6eb7b16d6f799bd4c871848806edaed8471c48cb`
- 교정 grade report SHA-256: `4b9bfe8921b4a58a8476327a5da09d08b1ebe1b5dd53618c4d21a2a0df495cdf`
- model / effort: `gpt-5.6-luna` / `high`
- 실행 표면: Codex CLI `0.150.1`의 official app-server stdio와
  controller-hosted dynamic-tool compatibility surface
- 제한: stock TUI approval 경로의 end-to-end 증거는 아니다.

v6는 prompt-only 권한 선언을 oracle로 쓰지 않는다. 실제 surfaced
runtime/worktree identity, exact branch/HEAD/status, permitted mutation 및
no-commit audit, implementation dispatch 이후 writer lifecycle, 단일 writer,
fallback·ambiguous delivery·terminalization·reconciliation, fixed-snapshot
non-upgrade, final-primary oracle를 관측한다. 각 실행은 fresh state이며 manifest가
동일 execution-harness identity와 allowlisted 결과·raw trace hash를 고정한다.

## 결과

| 사례 | baseline | candidate | 핵심 관찰 |
|---|---:|---:|---|
| `SE-BOUNDED-CHILD-CONTROL` | pass | pass | bounded child와 최종 primary 검증 |
| `SE-DURABLE-MATCHING-REUSE` | pass | pass | 일치하는 mutable binding의 durable reuse |
| `SE-DURABLE-VISIBLE-CREATE` | pass | pass | surfaced identity를 검증한 새 durable task |
| `SE-DURABLE-ADDRESSABILITY-RESUME` | invalid | pass | baseline은 overlapping writers로 injection 자체가 무효; 후보는 같은 task resume |
| `SE-BINDING-MISMATCH-SAFE-FALLBACK` | fail | pass | baseline의 mixed inventory는 state-neutral help 증거가 부족; 후보는 exact empty inventory와 안전 fallback |
| `SE-FIXED-SNAPSHOT-NON-UPGRADE` | fail | pass | 후보만 read-only fixed snapshot을 writer로 업그레이드하지 않음 |
| `SE-ACTIVE-WRITER-WAIT-REFRESH` | fail | pass | baseline은 durable writer와 native child가 겹침 |
| `SE-DEFINITE-PREDISPATCH-FAILURE-FALLBACK` | pass | pass | 명확한 dispatch 전 실패에서만 fallback |
| `SE-COMBINED-CREATE-START-AMBIGUOUS` | fail | pass | 후보만 may-have-delivered writer를 terminalize·reconcile |
| `SE-POSTDISPATCH-TRANSPORT-LOSS-RECONCILE` | fail | pass | 후보만 replacement writer 없이 원 writer를 reconcile |

후보의 직접 개선은 addressability, fixed-snapshot non-upgrade, active-writer
single-writer, combined create/start ambiguity, post-dispatch transport-loss 사례에서
관측됐다. baseline addressability는 모델이 같은 worktree에 두 writer를 시작해
handoff/barrier가 성립하지 않았으므로 `invalid-or-unsupported`로 보존했고, 유리한
결과로 교체하기 위한 재실행은 하지 않았다.

## 독립 grader의 보수적 교정

교정 grader는 model 결과를 바꾸지 않고 raw trace의 두 가지 계측 오탐만 좁게
정정했다.

1. Active-writer의 coarse 외부 interval은 exact `wait-selected` touch 성공 뒤,
   exact `writer-stopped.json`을 기다리는 allowlisted shell wait가 성공한 raw-trace
   sequence가 있을 때만 그 completion을 실제 stop proof로 사용했다. proof 이전
   실제 repository activity와 비외부 writer overlap은 계속 실패다. Boot 구간은
   worktree 밖의 설치된 policy `SKILL.md`를 읽는 exact `sed -n` 한 종류만
   state-neutral로 인정한다. 그래서 후보 오탐은 제거됐지만 baseline의
   durable/native-child overlap은 남았다.
2. Run-local `thread_barrier.py --help`는 그 위반 하나만 존재하고, metadata의 exact
   script path·hash가 동결된 execution-harness start/end의 tracked source hash와
   일치하며, `--help`(선택적 `2>&1`)만 사용하고 exit 0/help output, 관측된 모든
   exact full-path `find … -type f -print`로 관측된 모든 state inventory의 empty
   상태, 사후 빈 marker·cleanup evidence가 모두 확인된 두 실행에서만
   state-neutral argparse probe로 처리했다. 이 identity chain은 `argparse`가 state
   write 코드 전에 종료하는 동결 source를 증명한다. Help 뒤 nonempty inventory가
   하나라도 관측되거나 `%f`, count pipe, output redirect처럼 nonempty를 숨길 수 있는
   inventory 형식이면 교정을 거부한다. Baseline mismatch 실행의 mixed command
   inventory는 empty 증거로 인정하지 않아 그 실행은 fail로 유지했다. 다른 barrier
   호출은 허용하지 않는다.

세부 run ID, assertion, refinement와 hash는
[`manual-grades.json`](manual-grades.json), 실행 provenance는
[`run-metadata.json`](run-metadata.json), 동결된 20-run 목록은
[`behavior-run-manifest.json`](behavior-run-manifest.json)에 있다.

## 제외한 실행

- 이전 `pr42-eval-v6-primary-20`의 8개 실행
  (`b-2df65-235298e`, `b-8c6b4-038126a`, `b-98afd-0fad786`,
  `b-af18d-6485473`, `c-2df65-0a0e646`, `c-8c6b4-843997a`,
  `c-98afd-44e87c6`, `c-af18d-5b5fa86`)은 execution-harness identity 도입
  전 exploratory 결과라 최종 manifest에 넣지 않았다.
- `c-bf220-073f43c`, `c-bf220-c143410`, `c-af18d-4a66cf2`,
  `c-98afd-0532730`은 targeted harness pilots라 제외했다. 첫 ambiguous pilot은
  run-local barrier path 결함을 드러낸 bring-up 결과였다.
- 이전 v5 권한-선언 기반 corpus는 다른 oracle/harness의 역사 자료이며 v6 행렬의
  근거로 사용하지 않았다.

최종 primary 정책은 infrastructure/harness-invalid만 fresh state에서 1회 재실행할
수 있고 양쪽을 보존한다. Valid fail은 교체하지 않으며, required injection을
모델이 성립시키지 못한 실행도 `invalid-or-unsupported` 그대로 유지한다.

원시 run directory에는 per-run `CODEX_HOME`과 인증 파일이 있을 수 있으므로 통째로
게시하지 않는다. Hardcoded publication allowlist의 artifact만 hash와 함께 다룬다.

## 병합 전 남은 저장소 단계

1. 로컬 정책 commit `a7056f2`와 이 evidence commit을 PR branch에 push한다.
2. 갱신된 원격 head에서 CI를 재실행한다.
3. 갱신된 diff와 증거에 대해 blocking review를 다시 수행한다.
4. 원격 head가 평가 후보와 증거 commit을 포함하고 두 gate가 통과한 뒤 병합한다.
