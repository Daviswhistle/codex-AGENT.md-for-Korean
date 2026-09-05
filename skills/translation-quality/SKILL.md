---
name: translation-quality
description: |
  Use this skill whenever the user asks for a non-trivial translation, transcript translation, annual-report or financial-report translation, financial/earnings-call translation, blog-ready translation, or review/revision of an existing Korean translation. It preserves source structure while producing natural Korean, applies the user's preferred formatting, and requires a full-document QA pass before delivery.
---

# Translation Quality

Deliver a faithful, natural Korean document that the reader can use with minimal cleanup, not an extraction dump or internal QA artifact. This standard applies even when no blog-ready file is requested.

## Quality Contract

Preserve the source's information, order, structure, material repetition, emphasis, links, and communicative roles. Translate meaning rather than English syntax. Resolve names and aliases consistently across the whole source; use established Korean names or retain the source form unless a verified transliteration helps the reader. Put necessary, evidence-backed notes at the first relevant occurrence.

The first draft is not final. Conceptual review, source coverage, numeric fidelity, and final-file checks remain required whether generation uses one pass or multiple chunks. A large context window is not evidence of sufficient output capacity or omission-free translation.

## Load Only Applicable References

Resolve bundled resources relative to this `SKILL.md`; the default installed root is `${CODEX_HOME:-$HOME/.codex}/skills/translation-quality`.

1. Always read `references/core.md` for non-trivial translation or revision. It is the shared execution and QA contract, including mode selection, evidence, assembly, and completion.
2. Read `references/terminology.md` when reader-visible names need a rendering or identity map: brands, medicines, candidates, programmes, trials, aliases, former names, or development codes. Ordinary stable acronyms alone do not trigger it. Scan the whole source before substantive translation when this reference applies.
3. Select `core-only` for general prose, releases, articles, blogs, or web documents; it has no primary profile. Read `references/profiles/transcript.md` for speaker-driven material or `references/profiles/report.md` for formal page/table-heavy reports. Select one primary profile; load both only when both contracts genuinely apply.
4. Also read `references/quality_benchmark.md` for long, quality-sensitive, or reference-matching work. Do not claim access to unavailable prior examples.

## Execute and Verify

Use the workflow in `references/core.md`, without duplicating it as a second task checklist. Record the objective, source, loading path, applicable profiles and terminology review, chosen generation mode, and actual QA evidence. Single-pass generation omits chunk files and merging, not the source map or QA record. Chunked work must produce real reviewable translations before deterministic assembly.

Use `agents/korean_translation_reviewer.md` for `core-only` and transcript work, or `agents/korean_report_reviewer.md` for formal reports. Record whether review was independent or self-run. Fix accepted findings, rerun affected checks, and inspect the actual final artifact under `outputs/` before delivery.

Completion requires source coverage and order; natural Korean; applicable terminology and alias consistency; every material number, unit, period, and repeated guidance occurrence; justified notes and source corrections; structure, links, emphasis and format invariants; conceptual review; applicable helper and task-local evaluator results; and final-file existence and sanity. Disclose any unmet gate rather than calling the work complete or publication-approved.

## Helpers

- `scripts/qa_html_translation.py`: HTML, source-artifact, style, and numeric checks; follow the selected profile's invocation.
- `scripts/evaluate_report_equivalence.py`: report structure and reference-equivalence evidence, not proof of semantic quality.
- `scripts/merge_chunks.py` and `scripts/md_to_html.py`: deterministic assembly and conversion when applicable; single-pass work does not need dummy chunks.

## Final Response

State the delivered artifact and location, selected loading path and primary profile if any, whether terminology review applied, and checks actually performed. Disclose skipped checks, reasons, and residual risk. If a browser file is already open, tell the user to refresh that tab. Distinguish verification from approval or publication readiness.
