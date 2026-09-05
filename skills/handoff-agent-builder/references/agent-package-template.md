# Repo-Local Handoff Skill Template

Use this when creating the project-specific handoff package.

## Recommended layout

```text
.agents/skills/<project>-handoff/
  SKILL.md
  references/
    first-session.md
    handoff-completion.md
    maintainer-roadmap.md
    project-source-map.md
  agents/
    openai.yaml        # optional UI metadata
```

Codex automatically discovers repo-local skills from `.agents/skills`. Keep the package there unless the target environment documents a different supported skill root.

## SKILL.md

Include:

1. trigger-rich frontmatter
2. role and first-session behavior
3. safe execution/authority boundaries
4. artifact walkthrough rules
5. code/data/settings routing
6. completion and forward-test expectations

Keep long project-specific maps and examples in `references/`.

## first-session.md

Define a compact first response with project purpose, exact first command or inspection action, working directory, expected output/artifact and the next checkpoint. Explain unknown terms before relying on them.

Avoid opening with a glossary, broad policy dump, test matrix, file list without action or “what do you want to know?”.

## handoff-completion.md

Define the loop:

1. teach one concept;
2. inspect one concrete source;
3. summarize;
4. check understanding;
5. repair confusion if needed;
6. continue to the next planned source.

Define completion criteria and the final maintenance recap.

## maintainer-roadmap.md

Use real project stages and real paths. For each stage identify:

- goal
- what to teach proactively
- file/artifact/command to inspect
- summary
- understanding checkpoint
- progress criterion

## project-source-map.md

Route common maintenance questions to real paths/functions: CLI/UI entry point, settings, parsing, validation, generated artifacts, tests and domain-rule ownership.

## Human docs

If a README or docs page should expose the handoff route, add a short pointer to `.agents/skills/<project>-handoff/`. Do not copy the full skill into human docs.
