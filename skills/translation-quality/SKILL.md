---
name: translation-quality
description: |
  Use this skill whenever the user asks for a non-trivial translation, transcript translation, annual-report or financial-report translation, financial/earnings-call translation, blog-ready translation, or review/revision of an existing Korean translation. It preserves source structure while producing natural Korean, applies the user's preferred formatting, and requires a full-document QA pass before delivery.
---

# Translation Quality

This skill defines the user's expected translation workflow and output standard. It applies even when the user does not ask for a blog-ready file. The goal is a deliverable that can be pasted or published with minimal cleanup.

## Core Standard

1. Translate meaning, not English syntax. Korean must read like polished Korean business prose, not a literal transcript.
2. Preserve the original document's information, order, structure, emphasis, links, and explanatory context.
3. Do not treat the first draft as final. Conceptual review and full-document QA are mandatory for non-trivial work.
4. Do not rely on the user to catch translationese, source omissions, numeric drift, terminology drift, or publication defects.
5. When reader-visible names require a Korean rendering or identity decision, build a source-wide terminology ledger before translating. Apply one evidence-backed convention within each naming class.
6. Use an established Korean rendering when one exists. Otherwise preserve the source form by default; transliterate only when it materially helps the reader and the pronunciation or naming convention can be verified. Do not mix source spelling and Korean transliteration arbitrarily among comparable entities.
7. Resolve aliases and renames across the whole source. When a later passage proves that two names identify the same entity, revise the first occurrence to show the current canonical name and the former or alternate name when that relationship matters to the reader.
8. If a term needs explanation, place the note at the first occurrence and record its basis in QA.
9. Prefer deterministic, copy-paste-safe HTML when rich formatting or long-document navigation matters.
10. The final standard is a reader-facing Korean document, not an extraction dump or an internal QA artifact.

## Staged Reference Loading

Use progressive disclosure. Do not load every rule for every document.

1. Read `references/core.md` for every non-trivial translation or revision. It contains the portable reader contract, common workflow, style, notes, HTML, conceptual review, and shared QA gates.
2. Read `references/terminology.md` when the source contains reader-visible names that require a rendering or identity map, such as brands, medicines, drug candidates, programmes, trial names, aliases, former names, or development codes. Routine stable acronyms or ordinary technical terms alone do not trigger this reference.
3. Choose the applicable loading path during intake:
   - Use `core-only` for general business prose, press releases, articles, blog posts, web documents, and other inputs that are neither speaker-driven nor formal report artifacts.
   - Use `references/profiles/transcript.md` for earnings calls, interviews, Q&A, interpreted calls, or any speaker-driven document.
   - Use `references/profiles/report.md` for annual reports, audit reports, prospectuses, financial statements, governance reports, or page/table-heavy formal documents.
   Choose one primary document profile only when a transcript or report profile applies; `core-only` intentionally has no primary profile.
4. Load both profiles only when the source genuinely combines both contracts. Record the loading path, primary profile if any, any secondary profile, and whether the terminology reference applied in `work/qa_report.md`.
5. For long, quality-sensitive, or reference-matching work, also read `references/quality_benchmark.md`.
6. Resolve all bundled resources relative to this `SKILL.md` first. The default installed root is `${CODEX_HOME:-$HOME/.codex}/skills/translation-quality`.

## Execution Contract

1. State the task objective and completion conditions in one sentence.
2. Identify the source, document type, loading path, optional profile, output format, and reader-visible metadata.
3. Trace the source-to-output flow and discover task-local evaluators before editing.
4. If the terminology reference applies, scan the entire source before translating chunks and prepare the terminology ledger. Save it under `work/` for long documents; create a separate alias map only when the relationships are complex.
5. For sources longer than roughly 3,000 words, create source units, chunk files, a progress ledger, and a QA report under `work/`.
6. Translate and save reviewable chunks; do not simulate chunking by generating one monolithic translation and splitting it afterward.
7. Assemble the final deliverable deterministically under `outputs/`.
8. Run conceptual review with the applicable profile reviewer; for `core-only`, use `agents/korean_translation_reviewer.md`. When terminology review applies, include naming-class consistency, alias identity, and first-occurrence placement in that pass. Then run mechanical and source-fidelity QA.
9. Fix accepted findings, rerun the closest affected checks, and verify the final file itself before delivery.

## Completion Gates

Do not claim completion until all applicable gates pass or a concrete limitation is disclosed:

1. source coverage and order
2. selected loading-path contract
3. natural Korean and communicative role
4. when applicable, terminology-ledger consistency and alias or former-name handling at the earliest relevant occurrence
5. financial number, unit, fiscal-period, and repeated-guidance fidelity
6. note basis and first-occurrence placement
7. structure, links, emphasis semantics, and HTML invariants
8. conceptual reviewer ledger
9. applicable helper and task-local evaluator results
10. final output existence and file sanity
11. clear separation of verification, approval, and publication readiness

## Resource Map

- `references/core.md`: shared workflow and quality contract loaded for every non-trivial task
- `references/terminology.md`: conditional source-wide terminology ledger, established Korean rendering, naming-class consistency, aliases, former names, and entity-code mapping
- `references/profiles/transcript.md`: speaker flow, interpreted speech, earnings-call language, and transcript QA
- `references/profiles/report.md`: page/section hierarchy, tables, legal/reporting labels, and equivalence evidence
- `references/quality_benchmark.md`: portable acceptance benchmark and bad-to-target examples
- `agents/korean_translation_reviewer.md`: conceptual reviewer for speaker-driven and `core-only` documents
- `agents/korean_report_reviewer.md`: conceptual reviewer for formal reports
- `scripts/qa_html_translation.py`: HTML, source-artifact, style-template, and numeric QA helper
- `scripts/evaluate_report_equivalence.py`: report structure and reference-equivalence evaluator
- `scripts/merge_chunks.py`, `scripts/md_to_html.py`: deterministic long-document assembly helpers

## Final Response

1. State what was delivered and where.
2. Name the selected loading path, the primary profile if one applies, whether terminology review applied, and the concrete QA checks performed.
3. List skipped checks, reasons, and residual risk.
4. If a browser file is already open, tell the user to refresh the existing tab.
5. Do not overclaim perfection or publication approval.
