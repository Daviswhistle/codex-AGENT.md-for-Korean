---
name: handoff-agent-builder
description: |
  Use when creating or improving a repository-specific handoff/onboarding skill that should teach a maintainer what the project does, where important parts live, how to run or inspect it, how to make changes safely, and how to verify understanding through realistic multi-turn handoff conversations.
---

# Handoff Agent Builder

Create a repo-local handoff skill that actively teaches a person through the project. The output is not a passive overview.

## Design constraints

1. Lead the disclosure order. Explain important things before the maintainer knows to ask.
2. Start compactly with project purpose, the first route and one unmistakable next action.
3. Ground concepts in concrete files, commands, artifacts, logs, UI or code paths.
4. Teach one artifact or concept at a time and summarize before checking understanding.
5. Keep tone neutral and adult.
6. Reuse still-valid inspection evidence; recheck when the source or relevant conditions changed. Never describe a prior read or execution as newly performed.
7. Separate inspection, execution, approval, state-changing actions and verification.
8. Cover the operating map: domain, first run, artifacts, entry points, settings, data, evaluation, execution variants, troubleshooting, safe first tasks and future work.
9. Forward-test realistic multi-turn behavior. Static validation alone is not enough.

## Workflow

1. Inspect the target repository and its local instructions, README/docs, package/CLI entry points, settings, tests, sample data and representative artifacts. Use `references/discovery-checklist.md`.
2. Define what a maintainer should understand when handoff is complete and schedule topics they cannot be expected to ask about yet. Use `references/handoff-curriculum-template.md`.
3. Create the repo-local skill under:

```text
.agents/skills/<project>-handoff/
  SKILL.md
  references/
  agents/openai.yaml   # optional
```

Codex automatically discovers repo-local skills under `.agents/skills`. Do not put the primary package under a generic `agents/` directory and then require a second copy step.

4. Keep `SKILL.md` concise. Put project-specific first-session flow, maintenance roadmap and source map under `references/`. Use `references/agent-package-template.md`.
5. Connect human-facing README/docs to the handoff route when that materially helps maintainers find it; do not duplicate the skill.
6. Validate frontmatter, resource paths and executable helpers with the target repository's actual tooling.
7. Forward-test with fresh subagents or isolated conversations and observable tool evidence. Use `references/validation-playbook.md`.
8. Patch observed failures and rerun affected cases. Record unavailable behavior tests as not run, not passed.

## Required behavior

A useful handoff skill should:

- respond to “start handoff” with project purpose and an exact first action;
- make working directory, command, output/artifact and run status unambiguous;
- explain vocabulary from actual project evidence;
- continue to the next planned topic after confirmation instead of asking what to do next;
- proactively cover settings, data roles, evaluation and execution variants;
- finish with a practical maintenance map and remaining risks.

## Boundaries

- Do not claim to have opened, run or inspected something without available evidence.
- Do not mutate the repository when the user asked only for review or design.
- Do not broaden authority for execution, push, deployment, migration or external writes.
- Do not add prose-presence or banned-phrase tests.
- Do not use handoff ceremony to duplicate ordinary project documentation.
