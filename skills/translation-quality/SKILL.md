---
name: translation-quality
description: |
  Use for non-trivial Korean translation, transcript translation, annual or financial report translation, earnings-call translation, blog-ready translation, or review/revision of an existing Korean translation. Preserve source structure and meaning, produce natural Korean, and verify source coverage, terminology, numbers, and final output before delivery.
---

# Translation Quality

Deliver a faithful, natural Korean document that can be used with minimal cleanup. Preserve information, order, material repetition, links, emphasis, speaker or report structure, and the source's communicative roles. Translate meaning rather than English syntax.

## Load only what applies

Resolve every bundled resource relative to this `SKILL.md`.

1. Read `references/core.md` for every non-trivial translation or revision.
2. Read `references/terminology.md` when reader-visible names, aliases, former names, programmes, trials, medicines, products, or development codes require an identity/rendering convention.
3. Use `references/profiles/transcript.md` for speaker-driven material.
4. Use `references/profiles/report.md` for page/table-heavy formal reports.
5. Read `references/quality_benchmark.md` for long, high-risk, or publication-quality work.

Do not load both document profiles unless both genuinely apply.

## Execute and verify

The first draft is not final. Follow `references/core.md` for source mapping, generation-mode selection, conceptual review and shared QA.

Choose the simplest generation mode that can finish with reliable coverage:

- use single-pass when the complete deliverable fits with material output headroom and can be checked end-to-end;
- use semantic chunks when output capacity is uncertain, segmented checking materially reduces omission risk, or recoverable checkpoints are needed.

Single-pass does not waive source mapping, revision, numeric checks or full-document QA. Chunked work must contain real reviewable translation units before assembly; do not create dummy chunks to satisfy a procedure.

Use `agents/korean_translation_reviewer.md` for general/transcript work and `agents/korean_report_reviewer.md` for formal reports. Record whether review was independent or self-run. Fix accepted findings and rerun affected checks.

Completion requires:

- source coverage and order
- natural Korean and preserved modality/polarity
- applicable terminology and alias consistency
- every material number, unit, period and repeated guidance occurrence
- justified notes and source corrections
- profile-specific structure and formatting
- conceptual review
- applicable helper/task-local evaluator results
- inspection of the actual final artifact

Disclose an unmet gate rather than calling the work complete or publication-ready.

## Helpers

Resolve `<skill-root>` as the directory containing this `SKILL.md`.

- `<skill-root>/scripts/qa_html_translation.py`: HTML, source-artifact, style and numeric checks
- `<skill-root>/scripts/evaluate_report_equivalence.py`: report structure/reference equivalence evidence
- `<skill-root>/scripts/merge_chunks.py`: deterministic chunk assembly when chunking is used
- `<skill-root>/scripts/md_to_html.py`: Markdown-to-HTML conversion when applicable

## Final response

State the delivered artifact, selected document profile if any, generation mode, terminology-review applicability and checks actually performed. Separate verification from approval/publication readiness and disclose skipped checks with residual risk.
