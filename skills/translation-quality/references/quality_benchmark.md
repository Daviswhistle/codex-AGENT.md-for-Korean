# Translation Quality Benchmark

Use this reference when a translation must stand on its own for a Korean business reader. It replaces any hidden assumption that the agent remembers a prior completed translation.

## Acceptance Bar

A deliverable is ready only when all applicable statements are true:

1. The reader-facing output looks like a polished Korean document, not a PDF extraction, QA artifact, or simultaneous-interpretation dump.
2. The title and date identify the event cleanly. Internal labels such as filename date, financial period, source title, evaluation, fixture, or generated-output metadata are kept in QA, not displayed.
3. Speaker labels show effective speakers and roles. Operator, company host, executive, analyst, and interpreter are not collapsed into one label.
4. Interpreted speech is attributed to the original speaker when inferable from source flow. Visible `통역` is allowed only when the interpreter is genuinely the speaker or the original speaker cannot be determined.
5. Korean register does not imply unintended hierarchy. Do not use `말씀` as a default translation for "remarks", "comments", "said", or "talk through".
6. Financial scale is natural for Korean readers. RMB/CNY is `위안`, `100 billion` is `1,000억`, `15 billion` is `150억`, percentages and bp preserve the source scale, and fiscal years are not collapsed into calendar years.
7. Domain relationships are preserved. Translate commercial roles by the relationship in the source: a platform seller is not automatically a franchise merchant, and an owned or private-label brand strategy is not automatically direct-operated retail.
8. Polarity and modality are preserved. Language about enablement, upside, opportunity, optionality, or confidence must not become a constraint, problem, or obligation unless the source frames it that way.
9. Explanatory notes prevent likely misunderstanding, appear at first occurrence, are visually distinct when required, and have a recorded basis: `source`, `generic definition`, `externally verified`, or `source correction`.
10. Boilerplate is smoothed without losing substance. Greetings, thanks, and self-identification should not make the Korean read like raw interpretation.
11. QA evidence exists: source coverage, speaker flow, numbers, notes, formatting, bad-pattern search, conceptual review findings, and any task-local evaluator results.
12. Notes do not duplicate adjacent prose. If the source already explains a relationship in the same sentence, the Korean should integrate that explanation naturally or use a shorter note, not state the same point twice.
13. Numeric QA checks every material occurrence in the final assembled output. Repeated guidance ranges such as `mid-to-high teens`, bp guidance, EPS, margin, inventory, store counts, and currency amounts are compared source-unit by source-unit, not sampled once.
14. Long-document chunking is real. The workflow does not translate the whole document into one giant map and split it after the fact; each chunk is saved and reviewable before the next chunk is authored.
15. The task objective and completion conditions are explicit. QA explains what was run, what was skipped, why any skipped check was acceptable, and what residual risk remains.
16. The source-to-output flow is inspectable. A reviewer can connect source extraction, source units, chunk files, assembly, final output, and QA findings without relying on prior chat history.
17. Skill updates are consistent across the contract, reviewer prompt, benchmark, helper checks, tests, and README when those resources are affected by the same rule.
18. Long reports preserve report usability, not only prose meaning. Page sections, major headings, tables, notes, links, and financial statement order remain navigable and inspectable.
19. Reviewer work is split when the document is long enough to justify it. Prose/source fidelity, report/table structure, and HTML publication checks are separate passes or explicitly self-run as separate passes.
20. Reference-quality claims require reference evidence. A tool test, prompt update, or checklist is not enough; a generated candidate must pass the relevant QA and equivalence gate against the accepted reference or benchmark.
21. Reference quality is multi-axis. Structural metrics are necessary for HTML/report integrity, but they do not prove translation quality unless paired with conceptual review, source-fidelity evidence, numeric checks, and reader-facing Korean review.
22. Lexical checks are not a blacklist. Common words such as `말씀`, `측면에서`, and `비교됩니다` may be right or wrong depending on role, register, and sentence purpose. Mechanical checks should catch objective defects and exact recurring failure templates; conceptual review decides whether ordinary wording is appropriate.
23. Visual emphasis has meaning. Translator notes, source titles or names, and ordinary finance acronyms should not all be italicized by default. Common acronyms such as `GAAP`, `SG&A`, `EPS`, `SKU`, `APAC`, and `EMEA` usually remain plain body text unless the source formatting or reader purpose justifies emphasis.
24. Reader-visible source corrections are transparent. If a transcript period, number, speaker, or label appears wrong and the translation corrects it based on internal source consistency or an external primary source, the corrected sentence carries a concise translator note and the QA records the source-correction basis.
25. When terminology review applies, comparable names follow an evidence-backed naming-class convention, aliases and former names map to the correct entity, and later identity evidence is propagated to the earliest relevant occurrence. The QA records the terminology ledger and any justified exceptions.

## Reference Quality Suite

When local accepted references are available, use `examples/translation/good/reference-quality-suite.md` to decide which quality axes a new output must inherit:

1. Lululemon represents transcript packaging and polished blog flow: speaker-change-only labels, paragraph rhythm, real blank-line elements, fiscal-year title handling, live links, product/campaign/finance wording, and PDF cleanup. It is not a license to italicize every acronym; new outputs should keep the packaging strengths while applying the current emphasis semantics.
2. PDD Holdings represents interpreted-call/source-fidelity handling: operator/facilitator/executive/analyst role separation, original-speaker attribution, `data-unit` traceability, RMB/billion conversion, platform terminology, and explanatory-note discipline.
3. YesAsia represents long formal-report publication: page/section structure, table inventory, table alignment classes, links, defined names, legal/governance labels, financial statement order, and review fanout.

Do not use these references as hidden answer keys. Use them as a regression bar. If a legacy reference has known weaknesses under the current stricter skill, keep the reference's strengths and require the new output to improve the weakness rather than reproducing it.

## Bad-To-Target Examples

### Metadata

Bad:

```text
PDF filename date: 2026-05-27 · Financial period: Q1 ended March 31, 2026
한국어 번역
```

Target:

```text
Example Company A 2026년 1분기 컨퍼런스콜
2026.05.27.
```

Record filename date and financial-period source in QA if useful.

### Interpreted Speech

Bad:

```text
통역
질문을 받아 주셔서 감사합니다...
```

Target:

```text
Executive B
질문 감사합니다...
```

Use the original executive or analyst when source flow identifies whose words are being interpreted. Keep the extraction label in QA or an internal attribute, not as visible prose.

### Terminology And Alias Identity

Bad:

```text
CagriSema는 ...
경구용 제나감타이드는 ...
[Later]
아미크레틴은 ...
```

Target when established Korean forms are the chosen convention:

```text
카그리세마(CagriSema)는 ...
경구용 제나감타이드(zenagamtide·구 아미크레틴)는 ...
[Later]
제나감타이드 ...
```

Do not treat this as a universal instruction to transliterate every medicine. The target demonstrates naming-class consistency, source spelling at first occurrence, and back-propagation of a later alias discovery. When no established Korean form or reliable pronunciation exists, preserve the source form.

### Currency And Program Scale

Bad:

```text
100억 규모의 공급망 프로그램
RMB 15 billion
```

Target:

```text
1,000억(위안) 규모의 공급망 프로그램
150억 위안
```

After the first named-program occurrence, `1,000억 규모 프로그램` is acceptable if the currency has already been established and the shortened name cannot be confused with a different program.

### Honorific And Handoff

Bad:

```text
이제 Executive C에게 넘겨 추가 말씀을 듣겠습니다.
```

Target:

```text
이제 Executive C에게 순서를 넘기겠습니다.
```

Choose the Korean role of the line. A handoff is a handoff; do not add honorific hierarchy just because the English says "remarks".

### Fiscal Period

Bad:

```text
Example Company B 2027년 1분기 실적 발표 컨퍼런스콜
```

Target:

```text
Example Company B 2027 회계연도 1분기 실적 발표 컨퍼런스콜
```

Use `회계연도` when the source period is fiscal and a calendar-year reading would mislead.

### Domain Polarity

Bad:

```text
기술적으로 풀어야 할 과제들이 있습니다.
```

Target:

```text
기술 도입으로 가능해질 개선 여지가 있습니다.
```

Use positive enablement language for words such as "unlock", "opportunity", "can", "could", or "room to improve" unless the source explicitly frames the item as a constraint.

### Numeric Range QA

Bad:

```text
Source: China revenue growth is expected in the mid-to-high teens.
Output: 중국 매출은 한 자릿수 후반에서 10%대 중반 증가할 것으로 봅니다.
QA: China mid-to-high teens preserved.
```

Target:

```text
Output: 중국 매출은 10%대 중반에서 후반 증가할 것으로 봅니다.
QA: source unit 048, final data-unit 048, "mid-to-high teens" -> "10%대 중반에서 후반": PASS.
```

The QA must inspect the final paragraph for that exact unit. A correct statement elsewhere in the document does not cover an incorrect repeated occurrence.

### Platform Governance Terms

Bad:

```text
입점 매장의 위반 사항 처리 시간
```

Target:

```text
플랫폼 내 위반 사항 처리 소요 시간
```

Use the domain object. In marketplace governance, `store` may mean an online store or seller account, not an offline retail store.

### Table Alignment And Parity

Bad:

```text
| 구분 | 2025년 | 2024년 |
| :--- | :---: | :---: |
| 매출액 | 501,544 | – |
```

Target:

```text
| 구분 (Left-aligned) | 2025년 (Right-aligned) | 2024년 (Right-aligned) |
| :--- | :---: | :---: |
| 매출액 | 501,544 | – |
```

Ensure all table columns have matching alignments (left for text, right for numeric with tabular-nums CSS, center for short codes) and have perfect cell count parity between headers and body rows.

### Annual Report Structure

Bad:

```text
The annual report is translated as one long HTML body. Financial tables are pasted as loose paragraphs, repeated page footers remain visible, and the QA says only that the file looks good.
```

Target:

```text
The annual report is translated into page or section chunks, assembled into navigable HTML, and checked for page/section coverage, table parity, table alignment classes, live links, defined-term/name consistency, and financial statement sampling.
```

For formal reports, transcript-specific style warnings such as `말씀`, `이니셔티브`, or raw currency codes may be irrelevant in context. Use a report QA profile and record why any style pattern is intentionally not applicable, while keeping structural and source-fidelity checks strict.

### Review Fanout

Bad:

```text
One agent translates the whole PDF, says it reviewed the result, and provides no finding-level evidence.
```

Target:

```text
QA:
- Main translator: built source units, chunks, assembly, and final fixes.
- Report reviewer: checked page flow, tables, statutory labels, defined terms, and financial statement samples.
- HTML reviewer: checked links, TOC/search, table alignment classes, raw markdown markers, and closing tags.
- Numeric/source reviewer: sampled material tables across the beginning, middle, notes, and end.
- Reviewer mode: sub-agent where available; otherwise self-run separate passes.
```

The point of fanout is independent attention, not parallel unchecked rewrites. Accepted findings must be fixed by the main translator or rejected with evidence.

### Equivalence Evidence

Bad:

```text
The helper tests passed, so future Codex and agy outputs should be similar to the reference.
```

Target:

```text
The candidate output was generated, `qa_html_translation.py --profile report --strict-style` passed, and `evaluate_report_equivalence.py --require-core-counts-match` showed the same page/table/cell/link/emphasis counts as the accepted reference. Source-fidelity sampling, conceptual reviewer findings, and applicable Lululemon/PDD/YesAsia reference axes are recorded separately.
```

For annual-report references, the minimum structural equivalence metrics are page count, contiguous page sequence, table count, table row count, header-cell count, data-cell count, table column parity, table alignment classes, external link count, emphasis count, and raw artifact count. A candidate can exceed the reference only when the QA explains why the extra structure is intentional and source-backed.

### Verification Ledger

Bad:

```text
QA: helper passed. Looks good.
```

Target:

```text
QA:
- Objective: produce a blog-ready Korean earnings-call transcript that preserves speaker flow, numbers, notes, and copy-paste formatting.
- Completion conditions: final HTML exists, all source units are covered, conceptual review has no accepted P1/P2 findings, numeric QA passes source-unit checks, and task-local evaluators pass or are ruled out with reasons.
- Run: qa_html_translation.py --source-units ... --strict-style; local unit tests; manual source re-read of numeric guidance units.
- Skipped: external web verification for generic definitions, because no event-specific note was added.
- Residual risk: wording may differ from a prior unpublished reference, but no material source-fidelity issue remains.
```

Do not collapse verification, approval, and publication readiness into a single vague pass statement.

## Conceptual Review Ledger

For each conceptual review, record finding-level evidence even if everything was fixed:

```text
Location:
Problem:
Underlying principle:
Evidence:
Revision direction:
Disposition:
```

A statement like "no major issues" is not enough unless the QA also shows what was inspected and why no accepted P1/P2 issue remains.
