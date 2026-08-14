from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class AgentKitContractTests(unittest.TestCase):
    def test_global_and_project_instruction_contracts_are_separated(self) -> None:
        self.assertTrue((ROOT / "AGENTS.md").is_file())
        self.assertTrue((ROOT / "AGENTS.override.md").is_file())
        self.assertFalse((ROOT / "PHILOSOPHY.md").exists())
        self.assertFalse((ROOT / "PRINCIPLES.md").exists())
        self.assertTrue((ROOT / "guidelines").is_dir())
        self.assertFalse((ROOT / "STRATEGY.md").exists())
        self.assertFalse((ROOT / "principles").exists())

        agents = read("AGENTS.md")
        project_override = read("AGENTS.override.md")
        for heading in (
            "## 역할과 우선순위",
            "## 작동 철학",
            "## 핵심 원칙",
            "## 기본 동작",
            "## 행동 권한",
            "## 중단 조건",
            "## 스킬과 리소스 라우팅",
        ):
            self.assertIn(heading, agents)

        for statement in (
            "필요한 것을 잃지 않는 가장 단순한 형태를 찾는다.",
            "불필요한 것은 제거한다.",
            "필요한 것은 통합한다.",
            "확인하지 않은 사실을 단정하지 않는다.",
            "사용자가 변경도 요청하지 않았다면 구현하거나 파일을 수정하지 않는다.",
            "일반 질의 응답이 산문이라는 이유만으로 호출하지 않는다.",
        ):
            self.assertIn(statement, agents)

        self.assertEqual(
            agents.count("내 자리에서 맞는 판단은 상대의 자리에서도 버텨야 한다."),
            1,
        )
        self.assertNotIn("## Davis Agent Kit 수정", agents)
        self.assertIn("## 적용 범위", project_override)
        self.assertIn("## 수정 계약", project_override)
        self.assertIn("이 파일은 `davis-agent-kit` 저장소 안에서 작업할 때만 적용", project_override)
        self.assertIn("`AGENTS.md`에는 전역 지침 역할을 넘는 저장소 전용 절차를 넣지 않는다.", project_override)

        checked_paths = [
            path
            for path in ROOT.rglob("*.md")
            if ".git" not in path.parts
            and "scratch" not in path.parts
            and "private" not in path.parts
            and "user-model" not in path.parts
        ]
        stale_hits: dict[str, list[str]] = {}
        for path in checked_paths:
            text = path.read_text(encoding="utf-8")
            matches = [
                token
                for token in (
                    "PHILOSOPHY.md",
                    "PRINCIPLES.md",
                    "STRATEGY.md",
                    "principles/",
                )
                if token in text
            ]
            if matches:
                stale_hits[str(path.relative_to(ROOT))] = matches

        self.assertEqual(stale_hits, {})

    def test_delegation_contract_is_model_neutral(self) -> None:
        agents = read("AGENTS.md")

        for statement in (
            "최종 결과를 통합하는 주 세션은 사용자의 의도, 완료 기준, 검증, 최종 응답의 책임을 유지한다.",
            "위임할 때는 목표, 범위, 제약, 필요한 완료 근거를 명시한다.",
            "하위 에이전트의 완료 선언이나 요약만으로 완료를 판정하지 않는다.",
            "특정 모델, 추론 수준, 공급자, 비용 등급을 전역 기본값으로 강제하지 않는다.",
        ):
            self.assertIn(statement, agents)

        for model_specific_token in (
            "gpt-5.6-sol",
            "model_reasoning_effort",
            "Max",
            "Medium",
            "Ultra",
        ):
            self.assertNotIn(model_specific_token, agents)

    def test_prompt_migration_guideline_preserves_measured_change_discipline(self) -> None:
        guideline = read("guidelines/prompt-migration.md")
        for statement in (
            "사용자가 받게 될 산출물이나 완료 상태",
            "현재 모델과 reasoning effort로 대표 과제의 기준선을 기록한다.",
            "한 번에 하나의 의미 있는 변경 묶음만 적용한다.",
            "동일한 입력과 평가 기준으로 다시 실행한다.",
            "정적 계약 테스트는 파일·라우팅·필수 문구의 구조적 회귀를 막는다.",
            "`max`는 가장 어려운 품질 우선 작업에만 사용",
        ):
            self.assertIn(statement, guideline)

    def test_software_engineering_skill_replaces_coding_workflow(self) -> None:
        self.assertTrue((ROOT / "skills" / "software-engineering" / "SKILL.md").is_file())
        self.assertFalse((ROOT / "skills" / "coding-workflow").exists())

        skill = read("skills/software-engineering/SKILL.md")
        metadata = read("skills/software-engineering/agents/openai.yaml")
        agents = read("AGENTS.md")
        skills_readme = read("skills/README.md")

        self.assertIn("name: software-engineering", skill)
        self.assertIn('display_name: "Software Engineering"', metadata)
        self.assertIn("$software-engineering", metadata)
        self.assertIn("`software-engineering` 스킬", agents)
        self.assertIn("`software-engineering`", skills_readme)
        self.assertNotIn("coding-workflow", agents)
        self.assertNotIn("coding-workflow", skills_readme)

    def test_software_engineering_references_are_bundled(self) -> None:
        skill_root = ROOT / "skills" / "software-engineering"
        reference_paths = [
            "references/cra-loop.md",
            "references/tca-loop.md",
            "references/naming-docs-consistency.md",
        ]

        skill = read("skills/software-engineering/SKILL.md")
        for rel_path in reference_paths:
            self.assertTrue((skill_root / rel_path).is_file())
            self.assertIn(rel_path, skill)

        reference_text = "\n".join(
            (skill_root / rel_path).read_text(encoding="utf-8")
            for rel_path in reference_paths
        )
        software_engineering_text = skill + "\n" + reference_text

        self.assertIn('-c model="gpt-5.6-sol"', software_engineering_text)
        self.assertNotIn("service_tier=", software_engineering_text)
        self.assertNotIn("review_model=", software_engineering_text)
        self.assertNotIn("codex review --commit", skill)
        self.assertIn("codex review --commit", reference_text)
        self.assertIn("Task-Commit-Approve", reference_text)
        self.assertIn("Names are maintenance interfaces", reference_text)

    def test_writing_quality_is_integrated_as_a_general_writing_skill(self) -> None:
        skill_root = ROOT / "skills" / "writing-quality"
        self.assertTrue((skill_root / "SKILL.md").is_file())
        self.assertTrue((skill_root / "agents" / "openai.yaml").is_file())

        skill = read("skills/writing-quality/SKILL.md")
        metadata = read("skills/writing-quality/agents/openai.yaml")
        agents = read("AGENTS.md")
        root_readme = read("README.md")
        skills_readme = read("skills/README.md")
        writing_guideline = read("guidelines/writing-style.md")

        self.assertIn("name: writing-quality", skill)
        self.assertIn("display_name: Writing Quality", metadata)
        self.assertIn("$writing-quality", metadata)
        self.assertIn("`writing-quality` 스킬", agents)
        self.assertIn("skills/writing-quality", root_readme)
        self.assertIn("`writing-quality`", skills_readme)
        self.assertIn("writing-quality", writing_guideline)
        self.assertIn("## 호출 경계", skill)
        self.assertIn("Do not invoke solely because an ordinary answer", skill)
        self.assertIn("user-facing text", metadata)
        self.assertIn("독자가 그대로 읽거나 보내거나 게시할", skills_readme)
        self.assertIn(
            "일반 질의 응답이 산문이거나 기술·투자 내용을 다룬다는 이유만으로 호출하지 않는다.",
            skills_readme,
        )
        self.assertNotIn("- `writing-quality`: 분석, 투자 리서치", skills_readme)

        references = [
            "references/genre-playbooks.md",
            "references/review-rubric.md",
            "references/recipient-centered-persuasion.md",
            "references/test-matrix.md",
        ]
        for rel_path in references:
            self.assertTrue((skill_root / rel_path).is_file())
            self.assertIn(rel_path, skill)

        playbooks = read("skills/writing-quality/references/genre-playbooks.md")
        core_and_playbooks = skill + playbooks
        self.assertNotIn("네이버웹툰", core_and_playbooks)
        for inherited_metaphor in ("시간선", "완충재", "유사 구독"):
            self.assertNotIn(inherited_metaphor, core_and_playbooks)


if __name__ == "__main__":
    unittest.main()
