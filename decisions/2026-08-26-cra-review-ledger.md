# CRA 검토 원장과 증분 재검토

날짜: 2026-08-26

결정: CRA는 첫 번째 pass에서 고정된 task parent부터 현재 task commit까지 전체를 검토하고, 검토 대상을 구체적인 주장·불변조건 단위의 review unit으로 나눠 명시적 coverage와 근거를 ledger에 남긴다. finding을 고쳐 commit을 amend한 뒤에는 직전 reviewed SHA와 현재 SHA 사이의 amendment delta 전체를 새 회귀 관점에서 검토하고, 수정으로 결론이 무효화된 unit만 현재 task 상태에서 다시 검토한다. scope, dependency, evidence, invalidation trigger, 적용 지침이 변하지 않은 clean unit만 보수적인 impact analysis와 구체적인 이유를 남긴 뒤 carry forward한다. incremental reviewer에는 carry-forward unit의 claim, scope, dependency, evidence, invalidation trigger, 적용 지침, source·valid-through SHA, carry-forward reason을 모두 전달해 primary impact analysis의 누락을 다시 판정하게 한다. 영향 범위를 자신 있게 한정할 수 없으면 ledger 재사용을 포기하고 전체 task commit을 다시 검토한다.

배경: 기존 CRA는 finding을 수정해 같은 commit을 amend할 때마다 task commit 전체를 새 reviewer에게 다시 읽혔다. 이 방식은 단순하고 안전하지만 앞선 review가 이미 확인한 clean 영역의 판단과 근거를 버리므로, 큰 commit에서 국소적인 finding을 여러 번 고칠수록 같은 코드·문서·테스트를 반복해서 읽는 비용이 커진다. 반대로 기존 finding의 해결 여부만 확인하면 수정 과정에서 생긴 새로운 결함이나 간접 dependency 회귀를 놓칠 수 있다. 필요한 것은 review를 생략하는 것이 아니라, 이전 결론의 유효 조건을 남기고 그 조건이 깨진 부분만 다시 판단하는 구조다.

대안:

1. amend 뒤에도 항상 전체 commit을 다시 검토한다. 가장 단순하지만 반복 비용과 context 소비를 줄이지 못한다.
2. 기존 finding의 수정 여부만 확인한다. 가장 빠르지만 amendment가 새 결함을 만든 경우를 탐지하지 못한다.
3. 변경된 파일과 겹치는 unit만 무효화한다. 구현은 쉽지만 producer-consumer, config-runtime, schema-caller, test-evidence 같은 의미상 dependency를 놓친다.
4. hook, daemon, 별도 coordinator가 ledger와 review lifecycle을 강제한다. 자동화 수준은 높지만 현재 instruction kit의 역할을 다시 runtime orchestration으로 넓힌다.

이유:

1. 최초 full pass는 전체 task diff를 계속 책임지므로 기존 CRA의 기본 안전 경계를 유지한다.
2. unit은 `security`, `tests`, `docs` 같은 일반 범주가 아니라 실제로 참이어야 하는 주장과 그 dependency를 기록하므로 수정의 영향과 재검토 범위를 설명할 수 있다.
3. clean status는 reviewer가 해당 unit의 coverage를 명시했을 때만 생긴다. finding이 없었다는 사실만으로 primary session이 clean을 추정하지 않는다.
4. 모든 incremental pass는 amendment delta 전체를 반드시 검토한다. carry-forward는 이전 코드 재판단을 줄일 뿐 새 수정의 검토를 생략하지 않는다.
5. 파일 비변경은 결론 유지의 충분조건이 아니다. scope, direct·transitive dependency, validation evidence, config, schema, 적용 지침의 의미가 그대로인지 확인한다.
6. carry-forward unit의 전체 ledger 필드를 incremental reviewer에게 전달한다. 필드가 누락되거나 amendment와의 관계를 판정할 수 없으면 carry-forward하지 않고 `invalidated` 또는 `unknown`으로 처리한다.
7. `unknown` 또는 영향 범위 불명확은 cache miss로 취급한다. 잘못된 clean 재사용보다 전체 재검토 비용을 선택한다.
8. ledger, prompt, log, sentinel은 `git rev-parse --git-path cra` 아래에 두어 task commit과 worktree를 오염시키지 않는다.
9. Codex의 표준 review output schema는 유지한다. custom review prompt는 `overall_explanation`의 마지막 문장에 compact coverage marker를 요구하고, marker가 없거나 불완전하면 해당 unit을 `unknown`으로 처리한다.
10. custom review prompt를 지원하지 않는 환경에서는 같은 Sol·Max·long-context override와 blocking log·sentinel discipline을 유지한 `codex review --commit` 전체 검토로 안전하게 폴백한다. 명시적 unit coverage가 없으면 incremental reuse도 하지 않는다.
11. 이번 변경은 skill protocol과 결정 기록만 갱신한다. 새 helper, hook, state machine, daemon, installer surface는 추가하지 않는다.

경계:

1. task parent가 바뀌거나 task scope가 넓어지면 기존 ledger를 재사용하지 않는다.
2. valid finding을 수정한 unit은 항상 invalidated 상태에서 시작한다.
3. carry-forward unit은 claim, scope, dependency, evidence, invalidation trigger, 적용 지침, source·valid-through SHA, 현재 SHA까지 유효하다고 판단한 구체적인 이유를 보존한다.
4. reviewer가 amendment에서 예상하지 못한 scope, evidence, invalidation trigger, dependency, 적용 지침 영향을 발견하면 unit을 추가 invalidation하고 다시 검토한다.
5. broad refactor, rename, migration, auth, persisted data, concurrency, public contract, dependency update처럼 의미 영향이 넓은 변경은 full-review reset을 우선한다.
6. ledger는 review evidence와 navigation이지 actual diff inspection이나 local validation을 대신하지 않는다.
7. 작은 task는 review unit 하나로 유지할 수 있다. 단위 수를 늘리는 것이 목적이 아니다.
8. 서로 다른 task boundary나 provenance가 불확실한 ledger 사이에는 clean status를 공유하지 않는다.

나중에 다시 볼 조건:

- Codex review가 native coverage ledger, finding identity, incremental diff target, dependency invalidation을 직접 지원한다.
- `overall_explanation` coverage marker가 실제 대표 과제에서 안정적으로 생성되지 않는다.
- carry-forward 판단이 반복해서 false clean을 만들거나 reviewer가 놓친 회귀가 발견된다.
- ledger 유지와 impact analysis 비용이 전체 재검토 비용보다 지속적으로 크다.
- symbol·call graph·schema dependency를 신뢰성 있게 계산하는 실행 도구를 skill 안에 둘 근거가 쌓인다.
- CRA lifecycle을 host 또는 App Server가 공식적으로 보존해 별도 runtime orchestration이 단순해진다.
