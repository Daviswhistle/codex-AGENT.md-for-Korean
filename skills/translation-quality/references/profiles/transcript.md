# Transcript Profile

Use for earnings calls, interviews, Q&A, interpreted calls and other speaker-driven documents. Read `references/core.md` first.

## Contract

1. Preserve speaker order, Q&A mechanics and the distinction among operator, company host, executive, analyst and interpreter.
2. Build a speaker map before translation and split source units that contain multiple speakers. Source units support coverage and numeric QA in both generation modes; they are not generation chunks.
3. Attribute interpreted speech to the original speaker whenever source flow supports it.
4. Preserve every material occurrence of financial guidance and fiscal-period references.
5. Use `agents/korean_translation_reviewer.md` for conceptual review.

## Speaker formatting

Unless the user requests another format:

- show a speaker label only when the speaker changes;
- put it on its own line with no blank line before the first paragraph;
- break by natural paragraphs rather than sentence by sentence;
- keep Operator and company host/moderator roles distinct;
- do not expose `[Non-English content]`, `[비영어 발언]` or extraction-only interpreter labels when an interpreted version exists;
- use a visible `통역` label only when the original speaker cannot be determined after checking the surrounding source, and record the ambiguity in QA.

For HTML, speaker names should be visually distinct and copy-paste spacing must survive the target environment.

## Earnings-call risks

Re-read passages involving:

- guidance ranges, EPS, margins, inventory, tariffs and store counts;
- product launches, halo effects and promotional/clearance language;
- enablement, upside, optionality and constraints;
- supply-chain programmes and adjacent commitments;
- fiscal-year titles when the period year differs from the call date;
- marketplace roles such as merchant, seller, first-party brand, direct retail, franchise and self-operated stores.

Operator and analyst pleasantries should read as natural Korean, not literal ceremony.

## Mandatory QA

Before delivery:

1. compare the final transcript against source units for omissions, duplicated turns, speaker-order errors and numeric drift;
2. inspect every material repeated numeric occurrence in its own final passage;
3. verify visible speaker labels, paragraph structure and interpreter attribution;
4. verify source URLs, title/date and period wording;
5. record source-unit count, generation mode, chunk count only when chunks were actually used, numeric QA and conceptual-review findings.

For HTML, retain source unit IDs and matching `data-unit` IDs when practical.

A contextual search may help locate known failure patterns, but matches are reviewed in context and the search is not a semantic quality score.

Resolve `<skill-root>` as the directory containing the skill's `SKILL.md`.

```bash
python3 "<skill-root>/scripts/qa_html_translation.py" \
  --output outputs/<document>_ko.html \
  --source-units work/source_units.tsv \
  --expect-title "<exact Korean title>" \
  --expect-date "YYYY.MM.DD." \
  --strict-style
```

For chunked work, add `--chunks work/translation_chunks` using the actual location. For single-pass work, omit it. Non-HTML output still requires source, speaker and numeric comparison; record that this HTML helper is not applicable.

## Final-file checks

1. speaker/paragraph counts are plausible and speaker blocks are followed by content;
2. no anonymous interpreted executive or analyst answer is mislabeled `통역`;
3. every material repeated financial figure has occurrence-level evidence;
4. accepted material reviewer findings are resolved or disclosed.
