# Validation Playbook

Validate a project-specific handoff agent through executable checks and observed multi-turn behavior, not the presence of preferred wording.

## Mechanical Checks and Manual Review

Use an actually available skill validator for frontmatter and bundled resource paths, and the target project's checks for executable helpers. Do not invent an installed `quick_validate.py` path. In this kit, run `python3 scripts/validate_kit.py` for the kit's own machine contracts; a generated agent in another repository needs that repository's applicable validation.

Run whitespace validation when working in Git:

```bash
git diff --check
```

Manually inspect the first-session route, real command and artifact paths, unfinished placeholders, authority boundaries, and examples. A search may help locate suspicious text, but matching or missing a phrase is not a behavioral pass/fail criterion. Do not add prose-presence, heading, or banned-phrase tests.

## Required Behavior Tests

Use fresh subagents or isolated conversations. The validating agent should receive the installed skill and a natural user request, not your expected answer. Confirm actual skill loading and retain observable tool results and final outputs. A skill name in the answer is not proof of invocation. When execution is unavailable, record the case as not run rather than passed.

### Test 1. First Handoff Start

Prompt:

```text
Use $<project>-handoff at <path> for this repository. 인수인계 시작해줘
```

Pass criteria:

- Starts with project purpose and handoff route.
- Gives the exact first command or first inspection action.
- Includes working directory and expected output/artifact when relevant.
- Explains unavoidable terms.
- Does not start with a broad policy dump, test matrix, or "what do you want?"
- Does not use status labels for the listener.
- Ends with a clear next action checkpoint.

### Test 2. Run Or First Action

Prompt:

```text
실행해
```

or the equivalent for non-CLI projects.

Pass criteria:

- Runs only if the request and repo rules allow it.
- Reports success/failure from actual evidence.
- Opens or inspects the first planned artifact if success.
- Does not claim inspection or execution without available supporting evidence.
- Explains the artifact's role before jargon.
- Summarizes and checks understanding.

### Test 3. Continue After Confirmation

Prompt:

```text
이해됐어. 계속해줘.
```

Pass criteria:

- Continues to the next planned artifact/file/concept.
- Does not ask "what should we look at?"
- Inspects the next artifact when tooling allows.
- Uses one visual artifact per turn when visuals exist.
- Ends with a concrete summary and understanding check.

### Test 3.5. Proactive Topic Coverage

Prompt:

```text
좋아. 다음은 네가 알아서 이어가줘.
```

Pass criteria:

- Introduces the next required topic without waiting for a specific question.
- Names why the topic matters for safe maintenance.
- Opens or inspects the next concrete file/artifact when possible.
- Does not reduce the interaction to "궁금한 것을 물어보세요."

### Test 4. Domain Term Probe

Ask about a term that a first maintainer would not know:

```text
<domain term>가 뭔데?
```

Pass criteria:

- Explains in ordinary language before abbreviations.
- Connects the term to a concrete file/artifact/code path.
- Avoids condescension and quiz-like wording.
- Returns to the planned handoff flow after answering.

### Test 5. Settings And Data Probe

Prompt:

```text
설정 파일은 어디 있어? 데이터가 왜 여러 개야?
```

Pass criteria:

- Separates behavior settings, runtime options, environment, and data selection.
- Explains data roles and trust rules.
- Points to real paths.
- Does not treat sample, benchmark, generated output, and source-of-truth data as interchangeable.

### Test 6. Execution Variant Probe

Prompt:

```text
여러 번 돌리거나 랜덤 seed로 돌리는 흐름도 설명해줘.
```

Pass criteria:

- Explains deterministic baseline vs random/seeded candidates.
- Names the owning script/command/function when applicable.
- Explains why bad candidates may still be useful for exploration.
- Ends with a summary and understanding check.

### Test 7. Evidence Reuse and Invalidation

After an artifact was actually inspected, ask for an explanation of the same unchanged artifact. Then change a relevant source or setting in the fixture and ask how the explanation changes.

Pass criteria:

- Uses available, still-valid inspection evidence without rereading or rerunning solely because a new turn began.
- Distinguishes previous execution from a new execution and does not invent tool activity.
- Rechecks changed material and affected conclusions rather than treating old evidence as current.
- When prior evidence is unavailable, inspects again or discloses the gap instead of reconstructing unseen content.

## Acceptance Standard

The handoff agent passes only when applicable mechanical checks and required behavior cases pass. Include first-session behavior, at least one multi-turn continuation, evidence reuse/invalidation, proactive coverage of maintenance-critical topics, and the final maintenance recap. Record inapplicable cases with a reason, observed failures with their fixes and retest results, and unavailable tests as not run.

A good first answer alone does not establish that the agent can continue through artifacts and code ownership. Static validation alone does not establish behavioral quality.
