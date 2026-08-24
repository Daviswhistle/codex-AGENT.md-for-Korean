# Codex Runtime Examples

이 디렉터리의 파일은 선택적 런타임 예시이며 `scripts/install_codex.sh`가 자동으로 설치하지 않습니다. 전역 지침과 스킬은 모델 중립적으로 유지하고, 모델·추론 수준·service tier 같은 비용 및 성능 선택은 사용자가 명시적으로 복사해 적용합니다.

## Luna Max Fast worker

[`agents/worker.toml`](agents/worker.toml)은 범위가 명확한 구현과 로컬 검증을 맡는 `worker` 예시입니다.

- model: `gpt-5.6-luna`
- reasoning effort: `max`
- service tier: `fast`
- sandbox: `workspace-write`

개인 설정으로 사용하려면 파일을 `${CODEX_HOME:-$HOME/.codex}/agents/worker.toml`에 복사합니다. 특정 프로젝트에서만 사용하려면 프로젝트의 `.codex/agents/worker.toml`에 둡니다. `name = "worker"`가 Codex의 기본 `worker`와 같은 이름이므로 이 custom agent가 우선합니다.

Fast tier는 지원되는 모델과 계정에서 더 빠른 실행을 위해 추가 사용량 또는 비용을 소비할 수 있습니다. 적용 후 새 Codex 세션을 시작하고 현재 model catalog가 `gpt-5.6-luna`, `max`, `fast` 조합을 지원하는지 확인합니다.
