# Codex durable thread를 실행 백엔드로 추가하되 child agent를 대체하지 않음

날짜: 2026-08-27

결정: `software-engineering` 스킬의 실행 위임 계약을 특정 `worker` 구현에서 분리하고, 실행 carrier를 `primary`, `child agent`, `durable thread` 세 가지로 명시한다. 비사소하고 경계가 분명한 단일 실행은 사용 가능한 child agent를 기본 carrier로 삼는다. durable thread는 기존 관련 task의 문맥을 이어야 하거나, 역할이 여러 turn·session에 걸쳐 주소 가능해야 하거나, 사용자가 별도로 보이는 task를 명시적으로 원할 때만 선택한다. 어떤 carrier를 쓰더라도 주 세션은 사용자 의도, TCA·CRA 선택, 실제 diff 확인, 완료 필수 검증의 독립 확인, 최종 완료 판정을 유지한다.

배경: Codex 0.150.1의 공식 소스에는 app server에 연결된 TUI가 최근 task를 나열하고 읽고 기다리며, 기존 task에 메시지를 보내거나 새 task를 만들고 fork하는 기능이 포함되어 있다. 해당 MCP transport는 `create_thread`, `send_message_to_thread`, `fork_thread`를 승인 요청 대상으로 둔다. task 생성 도구 설명도 사용자가 새 task를 명시적으로 요청한 경우를 전제로 한다. 동시에 Codex에는 `spawn_agent`, 후속 메시지, 대기, agent 목록과 같은 native multi-agent 경로가 계속 존재한다. 따라서 두 기능은 중복 구현이 아니라 lifecycle이 다른 실행 수단이다.

확인한 1차 근거:

1. OpenAI Codex `rust-v0.150.1` tag의 `codex-rs/tui/src/dynamic_tools.rs`: thread/task 도구의 목록, 입력 제한, 읽기와 쓰기 동작.
2. 같은 tag의 `codex-rs/tui/src/dynamic_tools_mcp.rs`: local MCP transport와 create/send/fork 승인 설정.
3. `codex-rs/app-server/README.md`: durable thread의 start, resume, fork, list, read와 turn lifecycle.
4. `codex-rs/core/src/tools/handlers/multi_agents_spec.rs`: child-agent spawn, message, follow-up, wait, list lifecycle.

대안:

1. durable thread로 `worker`를 전면 대체한다.
   - 기각. 현재 thread 생성과 쓰기는 별도 task lifecycle과 승인 계약을 가지며, 한 요청 안의 bounded execution에는 과도할 수 있다. 오래된 문맥을 잘못 재사용하거나 같은 worktree를 독립된 것으로 오인할 위험도 있다.
2. 새 thread 기능을 무시하고 child agent만 유지한다.
   - 기각. 여러 session에 걸친 역할, 기존 task 문맥 재사용, 사용자가 직접 볼 수 있는 장기 task에는 durable thread가 명확한 이점을 준다.
3. `codex_tui` namespace나 0.150 계열의 정확한 tool 이름을 스킬에 규범적으로 고정한다.
   - 기각. transport와 노출 방식은 바뀔 수 있다. 스킬은 현재 runtime에 surfaced된 capability와 각 tool의 계약을 확인해야 한다.
4. 별도 orchestration framework나 새 스킬을 추가한다.
   - 기각. task contract, 권한 경계, worktree 격리, 검증, CRA·TCA는 기존 `software-engineering` 스킬이 이미 소유한다. 필요한 것은 backend 분리이지 새 정책 계층이 아니다.

경계:

1. 실행 계약을 먼저 정의하고 carrier는 그 뒤에 고른다.
2. 새 durable task를 만드는 권한을 일반적인 코드 수정 요청에서 추론하지 않는다. surfaced tool이 요구하는 명시 요청과 승인을 따른다.
3. durable thread를 재사용할 때도 먼저 대상 worktree의 writer가 종료됐는지 확인하거나 별도 worktree·고정 snapshot을 마련하고 branch·revision·상태를 새로 읽는다. 그 안정된 상태에서 첫 메시지를 read-only preflight로 제한해 contract ID, repository·worktree·branch, 시작 revision, 요청할 후속 권한과 검증 계획을 전달한다. acknowledgement를 현재 상태와 다시 대조한 뒤 별도 activation 메시지로만 edit·test·commit 권한을 부여한다. acknowledgement 전에는 구현, 파일 수정, commit, working state를 바꿀 수 있는 명령이나 test를 금지한다.
4. 다른 thread의 제목, 요약, 내용, idle 상태, 완료 선언은 증거가 아니다. 현재 사용자 의도와 저장소 지침에 맞춰 실제 diff와 원문 검증 근거를 확인한다.
5. 하나의 mutable worktree는 carrier 수와 무관하게 single-writer, stable-reader 경계다. durable thread는 worktree 격리를 제공하지 않으며, active writer가 있는 worktree를 읽는 preflight도 안정된 근거가 아니다.
6. 구현에 참여한 child agent나 durable thread는 자기 작업을 독립 승인할 수 없다. CRA와 고정 snapshot 검토 규칙은 그대로 유지한다.
7. write activation 전에 thread 생성·preflight·activation이 확정적으로 불가하거나 거절되면 child agent 또는 primary로 되돌아가되 검증 기준은 낮추지 않는다. activation이 전달됐을 가능성이 생긴 뒤 transport가 끊기면 자동 fallback을 금지하고, 기존 thread의 terminal 상태나 명시적 중단을 확인한 뒤 실제 worktree를 대조·정리하고 새 시작 상태를 확정할 때까지 중단한다.
8. 특정 모델, reasoning effort, provider, service tier를 durable thread의 전역 기본값으로 만들지 않는다. 기존 Luna Max + Fast 예시는 child-agent `worker`의 opt-in 설정으로만 남긴다.
9. `AGENTS.md`는 이미 “하위 에이전트나 격리된 실행 문맥”을 포괄하므로 변경하지 않는다.

변경:

1. `worker-delegation.md`를 `execution-delegation.md`로 교체하고 carrier 선택과 durable-thread protocol을 추가한다.
2. `software-engineering/SKILL.md`, TCA reference, skill interface metadata가 같은 선택 계약을 사용하게 한다.
3. CRA review ledger와 review command는 수정하지 않는다. 실행 carrier의 변화가 reviewer independence나 증분 검토 근거를 대신하지 않기 때문이다.
4. 2026-08-24 worker 위임 결정의 책임 경계와 검증 원칙은 유지하되, “worker가 유일한 기본 backend”라는 구현 가정만 이 결정으로 확장한다.

나중에 다시 볼 조건:

- Codex가 durable thread 생성과 turn correlation에 안정적이고 명시적인 agent-orchestration 계약을 제공한다.
- thread별 worktree·branch 격리가 제품 수준에서 기본 제공된다.
- child agent와 durable thread의 lifecycle이 통합되거나 한쪽이 폐기된다.
- thread history의 pagination·compaction·completion evidence 계약이 바뀐다.
- 실제 사용에서 durable thread의 문맥 보존 이득보다 승인·상태 동기화·검증 비용이 반복해서 더 크다.
