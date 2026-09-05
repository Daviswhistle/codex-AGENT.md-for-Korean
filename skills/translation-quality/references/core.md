# Translation Quality Core Reference

Read this reference for every non-trivial translation or revision, then follow the loading path selected in `SKILL.md`. `core-only` uses this file without a primary profile; speaker-only rules belong in `references/profiles/transcript.md`, page/table/report-only rules belong in `references/profiles/report.md`, and terminology/entity rules belong in `references/terminology.md` when its trigger applies.

## Portable Quality Contract

The skill must work from a fresh git install with no prior chat history or hidden accepted output. Treat `SKILL.md`, bundled resources, the user's request, and the source as the complete standard. For long or quality-sensitive work, read `references/quality_benchmark.md`. Resolve resources from `${CODEX_HOME:-$HOME/.codex}/skills/translation-quality` when installed globally.

Do not claim knowledge of unavailable prior work. Record which benchmark items were applied and which were inapplicable in `work/qa_report.md`.

## Reader Contract

1. The final artifact is for a Korean reader, not for an engineer inspecting extraction residue.
2. Preserve each passage's communicative role: a handoff remains a handoff, a disclaimer remains a disclaimer, and a financial comparison remains a financial comparison.
3. Korean honorifics imply hierarchy. Choose register from the speaker-listener relationship, not from an English verb such as “said” or “remarks.”
4. Financial units shape the reader's economic intuition. Preserve currency, scale, fiscal period, percentage, basis points, and recurrence so the Korean reader infers the same magnitude. Keep wording such as `2027 회계연도 1분기` when fiscal year and calendar year differ.
5. Domain terms must preserve business relationships. For example, merchant, seller, first-party brand, marketplace, direct retail, and franchise must not collapse into interchangeable labels.
6. When terminology review applies, names must preserve entity identity as well as spelling. Comparable naming classes need a deliberate convention, and a later alias or rename discovery must be reflected at the earliest relevant occurrence.
7. Visual emphasis is semantic. Separate translator notes from source emphasis. Translator notes, source-emphasized titles, product/program names, and ordinary acronyms are distinct roles; ordinary finance acronyms such as `GAAP`, `SG&A`, `EPS`, `SKU`, `APAC`, and `EMEA` usually should remain plain body text.
8. Notes prevent likely misunderstanding; they do not decorate the translation. For every explanatory note, record a basis field in QA. Do not let a note repeat the adjacent sentence. Mark a justified source repair as `source correction` and preserve its evidence.
9. If the user points out a phrase, infer the underlying class of failure. Do not merely blacklist the exact string. The underlying principle must change the translation, reviewer prompt, benchmark, helper, or evaluation where recurrence is possible.
10. Mechanical QA guards objective defects. It must not treat ordinary Korean words as forbidden or replace conceptual judgment about tone, hierarchy, polarity, identity, and business meaning.
11. Correct an apparent source/extraction/transcript error only when internal consistency or an external primary source supports it, and disclose the correction when it affects reader interpretation.

## Work Discipline

1. State the task objective and completion conditions in one sentence before substantial work.
2. Trace the source-to-output flow before editing: extraction, source units, terminology ledger when applicable, speaker or page map, chunks, assembly, final artifact, QA helper, and local evaluators.
3. Identify affected resources before changing the skill itself. Keep `SKILL.md`, references, reviewer prompts, examples, README, and directly relevant executable checks consistent. Do not add a phrase-presence test merely to mirror prose.
4. Before translating, scan the current task directory for explicit local evaluation files such as rubrics, `evaluate_*.py`, `check_*.py`, and `test_*.py`.
5. Do not report "mechanical QA pass" while a relevant local evaluator is failing or has not run without a concrete reason.
6. Separate verification from approval or publication. A passing helper alone is not enough when source coverage, conceptual review, or the selected loading-path contract remains unchecked.
7. Check naming and visible labels as part of quality: title, date, speaker labels, entity names, file names, `data-unit` IDs, note fields, and helper option names must describe their current role.
8. Keep scope tight, but fix directly connected contract drift and regression coverage.

## Intake And Chunking

1. Identify the source format, document type, loading path, optional primary profile, whether terminology review applies, output format, title, date, fiscal period, and reader-visible metadata.
2. Preserve structural extraction evidence until QA is complete.
3. When terminology review applies, scan the full source before substantive translation and prepare the terminology ledger. Save it for long documents; use a separate alias map only when relationships are complex.
4. Choose single-pass or chunked execution based on source length and model capability:
   - When the active model (such as a frontier large-context model) can reliably translate the full document in a single pass without omission or drift, translate directly to `outputs/`.
   - For sources exceeding the active model's reliable single-pass output limit, or when omission risk warrants segmented verification (historically ~3,000 words for earlier models), create reviewable source units, chunk files, a progress ledger, and `work/qa_report.md`.
5. When chunking is used, do not fake chunking by writing one giant translation dictionary and splitting it afterward. Translate and save independent reviewable chunks, then assemble deterministically.
6. Keep the original order, material repetition, links, footnotes, and emphasis semantics unless a documented reader-facing reason justifies compression.

## Natural Korean And Meaning

Translate meaning rather than English syntax. Restructure sentences when needed, but preserve polarity, modality, comparison direction, causal relationship, timing, and degree of confidence. A positive enablement phrase must not become constraint or problem language.

Growth ranges must preserve the source scale every time they recur. For example, `mid-to-high teens` -> `10%대 중반에서 후반`, not a single-digit range. Repeated numeric guidance is not covered by checking one representative occurrence.

Platform-governance terms must preserve what is measured. A phrase such as “time to action platform violations” should retain the meaning `플랫폼 내 위반 사항 처리 소요 시간`, not become generic service time.

For opaque initiative or program names, preserve the name consistently and add one concise first-occurrence explanation only when needed. When a named program and a nearby investment plan share the same large monetary scale, verify whether they are the same commitment, related commitments, or separate amounts before adding a note.

## Notes And Source Corrections

For every explanatory note, record:

- output location
- reader risk prevented
- evidence or source basis
- disposition

Use a concise first-occurrence note. Do not let a note repeat the adjacent sentence. If a source period, number, speaker, or label appears inconsistent, preserve the source unless evidence supports correction. Record the basis and use `source correction` in QA when the change is reader-visible.

## HTML And Assembly

Prefer deterministic, copy-paste-safe HTML when rich formatting matters. Verify a Korean UTF-8 shell, balanced structural tags, live links, semantic emphasis, and explicit blank-line elements where pasted spacing must survive. Tables require exact column parity and table alignment classes that reflect meaning: descriptive text left, numeric values right, short codes centered.

Use bundled helpers where applicable:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translation-quality/scripts/merge_chunks.py" \
  --input-dir work/translation_chunks \
  --output work/combined_translation.md \
  --title "<document title>"

python3 "${CODEX_HOME:-$HOME/.codex}/skills/translation-quality/scripts/md_to_html.py" \
  --input work/combined_translation.md \
  --output outputs/<document>_ko.html \
  --title "<exact Korean title>" \
  --date "YYYY.MM.DD."
```

## Review Fanout For Long Documents

For long or high-risk documents, separate review concerns when tools allow:

1. prose and reader-facing Korean
2. source fidelity, numbers, units, fiscal periods, and entity identity when applicable
3. loading-path-specific structure and publication behavior

Record reviewer mode for each pass: sub-agent, separate process, external runner, or self-run. Fanout does not replace final synthesis by the primary agent.

## Conceptual Review Gate

Use `agents/korean_translation_reviewer.md` for `core-only` and speaker-driven work, and the report reviewer named by the report profile for formal reports. Record conceptual review findings as a ledger with reader-facing problem, underlying principle, source/output location, revision, evidence, disposition, and remaining risk.

The reviewer must inspect every material occurrence of repeated guidance, unit conversions, source corrections, notes, hierarchy-sensitive language, domain relationships, and emphasis decisions. When terminology review applies, the reviewer must also inspect the ledger, naming-class consistency, alias identity, and earliest relevant occurrence. Fix accepted findings and rerun the closest checks.

## Shared Mandatory QA Gate

Before delivery:

1. Compare the assembled output against source units for omissions, duplication, order, structure, and material repetition.
2. For numeric content, compare each numeric source unit against the matching final HTML paragraph. Verify currency, scale, range, percentage, bp, fiscal period, and repeated occurrence.
3. When terminology review applies, compare the final output against the terminology ledger occurrence by occurrence and verify aliases or former names appear at the earliest relevant occurrence.
4. Check title, date, fiscal wording, links, emphasis semantics, notes, source corrections, and visible labels.
5. Run the selected loading path's final-file checks and all applicable task-local evaluators. For `core-only`, run shared checks without loading a transcript or report profile.
6. Record exact commands, pass/fail results, accepted and rejected reviewer findings, skipped checks with reasons, and residual risk.
7. Do not report "mechanical QA pass" while a relevant local evaluator is failing.
8. A passing helper alone is not enough; conceptual review, source coverage, and loading-path compliance remain separate gates.
9. Separate verification from approval or publication readiness in the final response.

For transcript HTML, use the helper command described in `references/profiles/transcript.md`. For report equivalence, use `scripts/evaluate_report_equivalence.py`, `--profile report`, and the applicable exemplar axes in `reference-quality-suite.md`. Metrics prove shape and artifact cleanup; they do not by themselves prove natural Korean or source fidelity.
