from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from doctor import sanitize_git_remote  # noqa: E402


class ReviewFeedbackContractTests(unittest.TestCase):
    def test_installation_examples_honor_codex_home(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        install = readme.split("## 설치", 1)[1].split("## 현재 스킬", 1)[0]

        self.assertIn("./scripts/install_codex.sh", install)
        self.assertIn(
            "CODEX_HOME=/path/to/codex-home ./scripts/install_codex.sh",
            install,
        )
        self.assertNotIn('mkdir -p "$HOME/.codex/skills"', install)
        self.assertNotIn('rm -rf "$HOME/.codex/skills/', install)

        for relative_path in (
            "skills/translation-quality/README.md",
            "skills/handoff-agent-builder/README.md",
        ):
            skill_readme = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(
                'CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"',
                skill_readme,
                relative_path,
            )
            self.assertNotIn("~/.codex/skills/", skill_readme, relative_path)

    def test_canonical_and_safe_sync_paths_honor_codex_home(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        project_override = (ROOT / "AGENTS.override.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        safe_sync = readme.split("## 수정 전 safe sync", 1)[1].split("## 설치", 1)[0]

        canonical = "${CODEX_HOME:-$HOME/.codex}/davis-agent-kit"
        self.assertNotIn(canonical, agents)
        self.assertIn(canonical, project_override)
        self.assertIn('CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"', safe_sync)
        self.assertIn('cd "$CODEX_DIR/davis-agent-kit"', safe_sync)
        self.assertNotIn('cd "$HOME/.codex/davis-agent-kit"', safe_sync)

    def test_generic_translation_has_core_only_loading_path(self) -> None:
        skill = (ROOT / "skills" / "translation-quality" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        readme = (
            ROOT / "skills" / "translation-quality" / "README.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Use `core-only` for general business prose", skill)
        self.assertIn(
            "for `core-only`, use `agents/korean_translation_reviewer.md`",
            skill,
        )
        self.assertIn("selected loading-path contract", skill)
        self.assertIn("`core-only` 경로", readme)
        self.assertIn("primary profile을 선택하지 않습니다", readme)
        self.assertIn(
            "`core-only`는 `agents/korean_translation_reviewer.md`",
            readme,
        )

    def test_core_reference_and_final_response_accept_core_only(self) -> None:
        skill = (ROOT / "skills" / "translation-quality" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        core = (
            ROOT / "skills" / "translation-quality" / "references" / "core.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`core-only` uses this file without a primary profile", core)
        self.assertIn("loading path, optional primary profile", core)
        self.assertIn("For `core-only`, run shared checks", core)
        self.assertIn(
            "Name the selected loading path, the primary profile if one applies",
            skill,
        )
        self.assertNotIn("Name the primary profile and", skill)

    def test_git_origin_output_removes_credentials_and_query_secrets(self) -> None:
        self.assertEqual(
            sanitize_git_remote(
                "https://user:secret@github.com/owner/repo.git?token=x#fragment"
            ),
            "https://github.com/owner/repo.git",
        )
        self.assertEqual(
            sanitize_git_remote("git@github.com:owner/repo.git"),
            "github.com:owner/repo.git",
        )
        self.assertEqual(
            sanitize_git_remote("https://github.com/owner/repo.git"),
            "https://github.com/owner/repo.git",
        )
        self.assertEqual(
            sanitize_git_remote("https://user:secret@example.com:bad/owner/repo.git"),
            "https://example.com:bad/owner/repo.git",
        )
        self.assertEqual(
            sanitize_git_remote("git@github.com:owner/repo.git?token=secret#fragment"),
            "github.com:owner/repo.git",
        )

    def test_event_based_rereview_prefix_matches_validator_contract(self) -> None:
        user_model = (ROOT / "user-model" / "README.md").read_text(encoding="utf-8")

        self.assertIn("재검토: YYYY-MM-DD 또는 조건: 구체적인 재검토 조건", user_model)
        self.assertIn("`조건: 사용자 정정 시`", user_model)


if __name__ == "__main__":
    unittest.main()
