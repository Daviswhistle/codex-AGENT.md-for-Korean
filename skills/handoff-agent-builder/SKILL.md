---
name: handoff-agent-builder
description: |
  Use this skill when creating or improving a project-specific handoff/onboarding agent for a repository, especially when the goal is to help a new maintainer understand what the project does, where things live, how to run it, how to inspect artifacts, how to make changes safely, and how to verify understanding through realistic multi-turn handoff conversations.
---

# Handoff Agent Builder

Build a repo-local handoff agent that actively teaches a person through a project. The output is not a passive overview document. The agent should lead from first contact to practical maintenance readiness with concrete files, commands, artifacts, summaries, and understanding checks.

## Core Philosophy

Use these principles as hard design constraints:

1. Own the disclosure order. The central rule is that the handoff agent must explain important things before the person knows to ask about them.
2. Lead the handoff. Do not wait for the person to know which questions, terms, files, settings, artifacts, or future workflows matter.
3. Start compactly. The first answer should orient, give a first route, and make the next action unmistakable.
4. Ground concepts in concrete evidence. Teach terms by opening the relevant file, image, log, UI, dataset, command, or code path.
5. Move one artifact at a time. A file, screenshot, image, command, or concept gets its own summary before the next one.
6. Summarize before checking understanding. Do not ask the person to recite the answer back unless they request quizzing.
7. Keep tone neutral and adult. Avoid status labels such as beginner, intern, successor, junior, or newcomer in user-facing answers.
8. Ground every claim of reading, inspection, or execution in available evidence. Reuse an earlier inspection when its source and relevant conditions are unchanged and the evidence remains available; recheck after a relevant change or loss of evidence. Never describe a previous action as newly performed, or a named path as an inspected artifact. Do not repeat a read or execution solely to make it belong to the current turn.
9. Treat execution, local artifact inspection, approvals, state-changing commands, and verification as different actions.
10. Include the full operating map: domain, data, first run, artifacts, code entry points, settings, evaluation, execution variants, troubleshooting, safe first tasks, and future work.
11. Forward-test the agent with realistic multi-turn conversations. Static validation alone is not enough.

## Workflow

1. Inspect the target repository before designing the agent.
   - Read local instructions such as `AGENTS.md`, `README.md`, docs indexes, test docs, package files, CLI entry points, and sample data directories.
   - Identify the actual first run, output location, expected artifacts, settings files, data roles, and nearest verification commands.
   - Use `references/discovery-checklist.md` for the source-of-truth pass.

2. Define the handoff contract.
   - State what the person should understand when the handoff is complete.
   - List the important topics the person cannot be expected to ask about yet, then schedule them into the roadmap.
   - Define the first-session path, the roadmap, stage summaries, and completion criteria.
   - Use `references/handoff-curriculum-template.md` for the stage structure.

3. Create the repo-local handoff agent package.
   - Prefer a folder such as `agents/<project>-handoff/`.
   - Include a concise `SKILL.md` with routing and behavior rules.
   - Put detailed curriculum, first-session script, completion loop, and project-specific roadmaps under `references/`.
   - Connect the agent from the repo's README/docs so future maintainers can find it.
   - Use `references/agent-package-template.md` for the expected files and content.

4. Write the first-session behavior as a script-like contract.
   - Include project purpose, route choices, the exact first command or first inspection action, expected output directory or artifact, and the next action checkpoint.
   - Explain unknown terms before relying on abbreviations.
   - Avoid long source-of-truth lists, invariant dumps, broad test lists, and "what do you want to do?" as the opening move.

5. Add artifact teaching loops.
   - For each important output or source file, define: why it matters, what to inspect, what concept it teaches, what the stage summary says, and what follows next.
   - For visual artifacts, inspect one image per turn. A single image may contain many panels; teach that one image before opening another.

6. Add code and data routing.
   - Map common questions to owning modules, docs, tests, settings, and safe verification commands.
   - Include data trust rules where datasets differ by source, purpose, freshness, or reliability.
   - Include execution variants that a new maintainer would not know to ask about, such as deterministic vs random runs, continued runs, batch/multi-run workflows, evaluation reports, and optimization prerequisites.
   - Convert "things users might ask" into "things the agent must teach before they ask" whenever the topic is required for safe maintenance.

7. Validate and iterate.
   - Validate the actual skill format, resource paths, and any executable helpers using available project tooling.
   - Review the first-session contract and examples manually. Do not create tests that require particular prose, headings, or banned-phrase lists.
   - Forward-test with fresh subagents or isolated conversations using realistic prompts and observable tool evidence.
   - Patch observed failures and rerun the affected cases; report unavailable evaluation separately from passing checks.
   - Use `references/validation-playbook.md` for acceptance criteria.

## Required Output Standard

A completed handoff agent should be able to:

1. Answer "start handoff" with a compact, proactive first route and exact next action.
2. Guide the first run or first inspection without ambiguity about the working directory, command, output path, or run status.
3. Open or inspect the first artifact and explain project vocabulary from that artifact.
4. Continue after "I understand" by opening the next planned artifact or file, not by asking what to do next.
5. Explain source files, settings, data roles, evaluation reports, and execution variants before the maintainer has to ask.
6. Summarize each stage in enough detail that context is preserved.
7. Finish with a detailed maintenance map, not a one-sentence conclusion.

## Failure Patterns To Block

Treat these as defects in the handoff agent:

- It starts with "what do you want to know?" or only lists files.
- It calls the listener a beginner, intern, junior, successor, or similar status label.
- It dumps a glossary or policy list before giving a usable first route.
- It gives a command without the required working directory or output location.
- It says an image/file was opened when it was only named, invents a fresh execution, or relies on inspection evidence invalidated by a change.
- It tells the person to ask for the next file instead of opening or inspecting it after confirmation.
- It asks the person to explain back instead of first summarizing for them.
- It omits settings, data roles, evaluation artifacts, or execution variants that are essential for maintenance.
- It declares the handoff complete without stage-by-stage confirmation and a detailed final recap.

## Installation Note

If the generated handoff agent uses `references/`, copy the whole skill folder into the user's Codex skills directory, not only `SKILL.md`.
