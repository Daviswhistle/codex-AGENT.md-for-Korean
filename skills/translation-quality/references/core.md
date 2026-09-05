# Translation Quality Core

Read this for every non-trivial translation or revision.

## Reader contract

1. The final artifact is for a Korean reader, not for an engineer inspecting extraction residue.
2. Preserve the role of each passage: handoff, disclaimer, comparison, question, answer, table, note and legal language must remain functionally equivalent.
3. Korean register must come from speaker/listener relationship, not literal English verbs.
4. Preserve currency, scale, fiscal period, percentage, basis points, recurrence and comparison direction so the reader infers the same magnitude.
5. Preserve business relationships. Merchant, seller, marketplace, direct retail, franchise and first-party brand are not interchangeable.
6. When terminology review applies, comparable names need a deliberate convention and later alias/rename evidence must be propagated to the earliest relevant occurrence.
7. Visual emphasis is semantic. Translator notes, source emphasis, names and ordinary acronyms are different roles.
8. Notes exist only to prevent likely misunderstanding and need an evidence basis. Reader-visible source corrections also need a basis.
9. Mechanical QA guards objective defects; it does not replace judgment about tone, hierarchy, identity, polarity or business meaning.
10. Correct apparent source errors only when internal consistency or a primary source supports the correction, and disclose material corrections.

## Intake and generation mode

Before substantive translation:

1. identify source format, document type, output format, title/date/period and applicable profile;
2. preserve structural extraction evidence and a source-to-output coverage map until QA is complete;
3. build speaker/page/table maps when the selected profile requires them;
4. scan the whole source and build a terminology ledger when terminology review applies;
5. inspect task-local evaluators or format constraints that affect completion.

Choose the simplest generation mode that can finish and be verified. Consider usable runtime context, maximum output/tool-payload limits, remaining budget, expected Korean/markup expansion and reasoning headroom. A model name or advertised input window is not evidence that a full deliverable will fit.

### Single-pass

Use when the complete source and necessary instructions fit, the full output has material headroom, and an end-to-end coverage check is credible. Generate a real draft directly; do not create empty chunk folders or run a merge just to satisfy a template.

### Semantic chunks

Use when output capacity is insufficient or uncertain, document structure benefits from segmented checking, omission risk is materially lower with boundaries, or recoverable checkpoints are valuable. Save real reviewable units and assemble them deterministically.

Do not compress a requested translation merely to fit a limit. Change generation mode instead.

In both modes keep a compact QA record with the source coverage, selected mode and rationale, actual review/check results, skipped checks and residual risk. Only chunked work needs chunk files or a chunk-progress ledger.

## Translation standard

Translate meaning rather than syntax. Preserve polarity, modality, comparison direction, causal relationship, timing and confidence. Restructure sentences when Korean requires it.

Repeated financial guidance must be correct at every occurrence. A correct translation of one `mid-to-high teens`, bp range, EPS, margin or currency amount does not cover a later incorrect occurrence.

When an opaque programme or initiative needs explanation, keep the name consistent and add one concise first-occurrence note only when it prevents likely misunderstanding. Verify relationships among nearby programmes or similarly sized commitments before adding explanatory claims.

## Notes and source corrections

For each explanatory note or reader-visible source correction, retain enough QA evidence to identify:

- output location
- misunderstanding prevented or source inconsistency corrected
- source/definition/primary-source basis
- disposition

Do not repeat the adjacent sentence in a note.

## Assembly and HTML

Use copy-paste-safe HTML when rich formatting matters. Verify Korean UTF-8 output, balanced structural tags, live links, semantic emphasis and table parity/alignment.

Resolve `<skill-root>` as the directory containing the skill's `SKILL.md`.

For chunked Markdown:

```bash
python3 "<skill-root>/scripts/merge_chunks.py" \
  --input-dir work/translation_chunks \
  --output work/combined_translation.md \
  --title "<document title>"

python3 "<skill-root>/scripts/md_to_html.py" \
  --input work/combined_translation.md \
  --output outputs/<document>_ko.html \
  --title "<exact Korean title>" \
  --date "YYYY.MM.DD."
```

For single-pass output, skip merging. Convert the actual single draft only if the requested format needs conversion. Pass `--chunks` to HTML QA only when real chunk files were used.

## Review

For long or high-risk documents, separate review concerns when useful:

1. reader-facing Korean
2. source fidelity, numbers, units, periods and entity identity
3. profile-specific structure/publication behavior

Use the selected profile's reviewer. Record meaningful findings, evidence, revision and disposition. Self-review is not independent review.

## Shared mandatory QA

Before delivery:

1. compare the final output against source units/passages for omissions, duplication, order, structure and material repetition, including the ending;
2. compare every material numeric occurrence against the matching final passage;
3. when terminology review applies, check the final output against the terminology ledger occurrence by occurrence;
4. verify title/date/period, links, emphasis, notes, corrections and visible labels;
5. run the selected profile's final-file checks and applicable task-local evaluators;
6. inspect the actual final artifact after the last change;
7. record exact checks, results, skipped checks and residual risk.

A passing helper is not proof of natural Korean, source fidelity or publication readiness.
