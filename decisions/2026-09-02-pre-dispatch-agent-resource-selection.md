# 실행 전 에이전트 자원 선택

날짜: 2026-09-02

결정: worker, explorer, 독립 reviewer를 실행하기 전에 역할 → 모델 → reasoning effort → service tier → context window → context propagation/fork 순서로 선택하고 근거를 기록한다. 모델 배치와 대화 이력 전달은 서로 독립된 판단이다. 전역 지침은 모델 중립으로 유지하고, 특정 모델·effort·tier·context를 모든 역할의 기본값으로 승격하지 않는다.

배경: 대화 전체를 넘기기 편하다는 이유로 `fork_turns=all`을 먼저 고르면, 현재 런타임에서는 부모 모델과 reasoning effort가 그대로 상속되고 override를 지정할 수 없다. 그러면 실제 역할과 위험을 보고 모델을 고르는 판단이 실행 뒤의 사후 설명으로 밀린다. 반대로 모델만 먼저 고정하고 모든 작업에 1M context나 Fast tier를 붙여도 범위·증거량·지연 가치·사용량을 구분하지 못한다.

선택 계약:

1. 역할은 bounded implementation worker, read-only explorer, independent reviewer 중 필요한 책임과 독립성으로 정한다.
2. 모델은 역할, 오류 비용, 작업 난도, 독립 검토의 중요도로 정한다.
3. reasoning effort는 선택한 모델 안에서 과업의 복잡성과 모호성으로 정한다.
4. service tier는 지연 개선의 가치, 추가 사용량, 현재 계정과 런타임 지원으로 정한다.
5. context window는 diff 크기만이 아니라 prompt, instructions, evidence packet, 예상 reasoning·tool output을 합친 peak live context로 정한다. 가능한 경우 가장 가까운 유사 실행의 peak per-request input과 compaction 실측을 우선한다. 불필요한 출력을 먼저 줄인 뒤에도 ordinary effective limit에 충분한 여유가 없거나 예측 불확실성이 크면 확장 context를 사용한다. requested value, catalog-clamped nominal limit, `task_started`가 보고한 runtime-effective limit을 서로 구분한다.
6. 마지막으로 context propagation/fork를 정한다. 현재 `spawn_agent` 계약에서 `fork_turns` 생략과 `all`은 모두 full-history이며 부모 모델과 effort를 상속하고 override를 허용하지 않는다. 따라서 fork mode를 항상 명시하고, 그 상속 자체가 의도일 때만 `fork_turns=all`을 사용한다. 다른 모델이나 effort를 선택했으면 `fork_turns=none` 또는 필요한 최소 recent-turn fork와 self-contained handoff를 사용한다.

선택 뒤에는 launcher/profile 실행 가능성과 inherited config를 확인한다. 선택한 model, effort, tier, context, fork를 호출 표면이 모두 표현하지 못하면 호환되는 launcher를 쓰거나 실행 전에 기록을 실제 profile로 수정한다. 사용자가 Fast를 허용했다는 사실, repository에 Fast 예시가 있다는 사실, model override를 적었다는 사실만으로 Fast가 활성화됐다고 주장하지 않는다. 현재 catalog의 Fast 요청과 runtime `priority` ID는 같은 가속 티어로 취급한다. standard tier를 선택하려면 가능한 launcher에서 `service_tier=default`와 `fast_mode=false`를 명시하고, 설정 생략은 default가 아니라 상속으로 기록한다. 같은 방식으로 full-history fork만으로 1M context가 요청됐다고 간주하지 않는다.

주 세션은 비싼 모델을 호출하기 전에 exact snapshot·diff·관련 계약·검증·runtime metadata를 직접 정리하고, 재귀·바이너리·생성물·cache·session-log 탐색처럼 큰 출력을 낼 수 있는 기계적 작업을 제한한다. 독립 reviewer는 이 evidence packet의 핵심 주장을 검증하고 반박하는 데 집중하며, 구체적인 결함 가설이 있을 때만 범위를 넓힌다. 실행 뒤에는 runtime-effective window, peak per-request input, compaction 여부, 예상 밖의 대용량 명령을 기록해 다음 선택에 사용한다.

역할별 경계:

- Luna Max + Fast는 bounded implementation worker에서 지연 이득이 추가 사용량보다 가치 있을 때 사용할 수 있다. 허용이지 의무나 전역 기본값이 아니다.
- 높은 오류 비용의 독립 리뷰에는 Sol Max 같은 더 강한 reviewer가 합리적일 수 있다. worker의 Fast 허용을 reviewer에 자동 전이하지 않는다.
- reviewer 모델이 강하다는 이유만으로 항상 1M context를 요청하지 않는다. 작은 변경은 강한 모델과 ordinary nominal context의 조합도 의도적인 선택이며, 실제 usable context는 launch metadata로 확인한다.
- `~/.codex/agents/worker.toml`은 named worker를 선택할 때 쓰는 optional profile이다. 이를 설치해도 full-history 상속을 명시한 invocation의 모델을 뒤집는 것으로 가정하지 않는다.
- 키트는 optional Luna 예시를 자동 설치하거나 기존 `worker.toml`을 덮어쓰지 않는다.

기록 형식: 각 invocation 전에 role, model, effort, tier, requested context, catalog-clamped nominal context, `runtime-effective=pending`, propagation/fork, compatible launcher/profile, 선택 근거를 남긴다. 실행 뒤 `task_started`가 보고한 runtime-effective context와 실제 tier 등 확인 가능한 값을 갱신한다. 결과를 보고 모델 선택 이유를 새로 만들거나 launcher가 표현하지 않은 설정을 활성 profile로 보고하는 것은 이 계약을 충족하지 않는다.

대안:

1. 모든 worker를 Luna Max + Fast로, 모든 reviewer를 Sol Max + 1M으로 고정한다.
2. 항상 `fork_turns=all`을 사용하고 상속된 모델에 작업을 맞춘다.
3. custom `worker.toml` 설치만으로 모델 라우팅을 해결한다.
4. 선택을 기록하지 않고 주 세션의 암묵적 판단에 맡긴다.

이유: 역할과 오류 비용이 모델 품질을, 모호성이 effort를, 지연 가치와 사용량이 tier를, 증거량이 context를, 필요한 대화 계보가 fork를 결정한다. 이 순서를 분리하면 작은 diff에 불필요한 1M을 쓰지 않으면서도, 편의상 full-history를 먼저 골라 중요한 작업을 의도하지 않은 모델에 맡기는 일을 막을 수 있다. 또한 2026-07-16 모델 중립 원칙과 2026-08-24 optional Luna worker 결정을 유지한다.

나중에 다시 볼 조건:

- Codex의 full-history fork가 모델·effort override를 허용하도록 바뀐다.
- custom-agent discovery와 fork 상속의 우선순위가 바뀐다.
- 모델 카탈로그의 context window, reasoning effort, Fast tier 지원 계약이 바뀐다.
- 실제 대표 과제에서 사전 선택 기록이 잘못된 모델 배치나 불필요한 context 사용을 줄이지 못한다.
- 역할별 고정 profile이 모델 중립 선택보다 반복적으로 더 나은 품질·비용·지연 결과를 낸다는 측정이 쌓인다.
