# Transcript Profile

Use this profile for earnings calls, interviews, Q&A, interpreted calls, and other speaker-driven documents. Read `references/core.md` first.

## Profile Contract

1. Preserve speaker order, Q&A mechanics, communicative roles, and the distinction among operator, company host, executive, analyst, and interpreter.
2. Build a speaker map before translation and split any source unit that contains multiple speakers. Source units support coverage and numeric QA in both generation modes; they do not require chunked generation.
3. Attribute interpreted speech to the original speaker whenever source flow supports it; keep extraction-only labels out of reader-facing output.
4. Preserve every material occurrence of financial guidance, including repeated ranges and fiscal-period references.
5. Use `agents/korean_translation_reviewer.md` for conceptual review.

## Speaker And Paragraph Formatting

Use this format for transcripts unless the user explicitly requests otherwise:

1. Add a speaker label only when the speaker changes.
2. Put the speaker label on its own line.
3. Do not insert a blank line between the speaker label and that speaker's first paragraph.
4. Do not add a speaker label to every sentence.
5. Break by natural paragraphs, not sentence by sentence.
6. Do not cram the entire answer into one dense block. Separate distinct ideas, financial guidance, operational commentary, and Q&A turns into readable paragraphs.
7. For blog/copy-paste HTML, use actual blank-line elements such as `<div class="blank"><br></div>`, not CSS margins alone, because CSS-only spacing may disappear when pasted.
8. Speaker names in HTML should be bold, for example `<strong>Executive A</strong>`.
9. Keep call roles distinct. Translate the bridge `Operator` as `사회자`; translate the company IR host or moderator as `진행자` when the source uses an anonymous speaker label. Do not collapse both roles into the same Korean label.
10. For bilingual or interpreted calls, do not print `[Non-English content]`, `[비영어 발언]`, or equivalent markers in the final output when an interpreted version is present. Attribute the interpreted paragraph to the original speaker whenever the source flow makes that clear. Use internal attributes such as `data-source-speaker` or QA notes for traceability rather than showing `통역` as the reader-facing speaker.
11. If the interpreter owner is ambiguous, inspect the source around the skipped non-English unit, the Q&A question, and any self-identification in the interpreted answer. Use `통역` as a visible label only when the original speaker cannot be determined after that check, and record the ambiguity in QA.

## Earnings Call Specific Checklist

For earnings-call transcripts, perform these additional checks:

1. Operator lines should sound like a call operator, not like a literal written document:
   - Prefer "다음은 X입니다. 부탁드립니다."
   - Prefer "마지막은 X입니다. 부탁드립니다."
   - Avoid "다음 질문은 X에게서 나옵니다."
2. Prepared remarks and Q&A should not collapse separate speakers into one paragraph. Source extraction often joins lines like `Executive A: ... Executive B: ...`; split these manually.
3. Guidance language should be natural and compact:
   - "we now expect" does not need to become "현재 예상합니다" every time.
   - Use "봅니다", "예상합니다", "가이던스에는 ... 반영했습니다", or sentence restructuring according to context.
4. Product/campaign names should be preserved consistently and italicized in HTML when useful.
5. Analyst pleasantries should be readable Korean, not literal ceremony.
6. Proxy contests, shareholder actions, board-seat fights, or other governance events should be explained at first occurrence if a Korean reader may not understand the context.
7. If an internally inconsistent transcript period or number is corrected, verify the correction against internal source evidence or an external primary source, add a concise note at the corrected sentence, and record the source-correction basis in QA.
8. For Chinese-company calls or any call with interpretation, verify:
   - non-English source markers are not visible when interpretation exists
   - interpreted answers are attributed to the original executive or analyst, not to `통역`
   - `Operator` and company host/moderator labels are distinct
   - RMB/CNY and billion-to-억 conversions are correct
   - program names with large monetary figures are introduced once with the currency unit if needed
9. Re-read all passages involving:
   - markdowns and clearance
   - full-price sales
   - inventory dollars versus units
   - tariffs and offsets
   - gross margin and operating margin
   - store openings and optimizations
   - product launch performance and halo effects
   - enablement, upside, calendar or process compression, sourcing flexibility, go-to-market timing, and whether they are opportunities, constraints, or tradeoffs in the source
   - supply-chain investment programs and their relationship to adjacent initiatives
   - fiscal-year titles when the period year differs from the call date
   - platform terminology such as merchants, sellers, first-party brand models, marketplace, direct retail, franchise, and self-operated stores

## Transcript Mandatory QA

Before final delivery:

1. Compare the final transcript against source units for omissions, duplicated turns, speaker-order errors, and mistranslated numeric guidance.
2. For HTML numeric QA, retain source `unit` IDs and matching paragraph `data-unit` IDs in either generation mode. Compare each numeric source unit against its matching final paragraph; chunking is not a prerequisite for this evidence.
3. Repeated numeric guidance is not covered by checking one representative occurrence. If `mid-to-high teens`, `high single digits`, bp guidance, EPS, margin, inventory growth, store count, or a currency amount recurs, inspect every occurrence and final rendering.
4. Verify transcript mechanics:
   - speaker labels appear only on changes
   - speaker labels are bold in HTML
   - no blank line separates a speaker from the first paragraph
   - paragraphs are readable and not one-sentence-per-line
   - copied blank lines survive as real elements
5. Verify `[Non-English content]`, `[비영어 발언]`, raw `Speaker <number>` labels, anonymous visible interpreter labels, raw `[[em:` markers, and incorrect RMB scale do not remain.
6. Record source unit count, generation mode, translated chunk count when used (otherwise not applicable), speaker-transition sanity check, title/date, link count, emphasis inventory, note count, mechanical-search dispositions, manually reread sections, and numeric QA in `work/qa_report.md`.
7. For earnings calls, create a numeric QA table with source unit, source number and unit, matching final `data-unit` for HTML or passage location for another requested format, Korean rendering, pass/fail, and correction made. A row is not acceptable if the exact final passage was not read.

Use a contextual mechanical search on the final HTML when applicable:

```bash
rg -n "높은 수준에서 말씀드리겠습니다|에게서 나옵니다|파급 효과를 만들어내지 못|새로운 .{1,20}원단|것으로 현재|현재 예상|관문 요인|제품을 이동|업데이트해 주실 수|행운을 빕니다|위임장 변경|준비한 말씀|이상으로 준비한|추가 말씀|에게 넘겨|매장 위반 처리 시간|\\[Non-English content\\]|\\[비영어 발언\\]|\\[\\[em:|RMB|100억(\\(위안\\))?\\s*(규모|지원|투자|프로그램|계획|펀드)" outputs/*.html
```

Inspect matches in context; this search is not a semantic quality score. Search chunk files additionally only when they exist and an affected check needs them.

Run the bundled transcript QA helper on the final HTML in either generation mode:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/translation-quality/scripts/qa_html_translation.py" \
  --output outputs/<clear_document_name>_ko.html \
  --source-units work/source_units.tsv \
  --expect-title "<exact Korean title>" \
  --expect-date "YYYY.MM.DD." \
  --strict-style
```

For chunked work, add `--chunks work/translation_chunks` using the actual chunk location. For single-pass work, omit this optional argument; do not create an empty directory or bypass source-unit checks. Use the helper's source-unit format rather than inventing a new schema. Non-HTML output still requires source, speaker, and numeric comparison; disclose that this HTML-specific helper is not applicable.

If a style match is acceptable, waive it only after recording the context and disposition. Structural failures, source artifacts, raw emphasis markers, and incorrect visible interpreter labels must be fixed. Use `--allow-visible-interpreter-label` only when the visible speaker genuinely is an interpreter and the QA report records why attribution to an original speaker was impossible.

## Transcript Final-File Checks

1. speaker, paragraph, and blank-line block counts are plausible
2. every speaker block is followed by a paragraph block
3. source URLs remain live
4. no anonymous interpreted executive or analyst answer is labeled `통역`
5. every material repeated financial figure has occurrence-level evidence
6. conceptual reviewer findings are recorded and no accepted P1/P2 finding remains unresolved
