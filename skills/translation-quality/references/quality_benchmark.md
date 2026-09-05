# Translation Quality Benchmark

Use this for long, high-risk or publication-quality translation. It is a reader-quality bar, not a mandatory execution shape.

## Acceptance bar

A deliverable is ready only when all applicable statements are true:

1. It reads like a polished Korean document, not extraction residue, QA output or simultaneous-interpretation dump.
2. Title, date and reporting period identify the material cleanly; internal extraction metadata stays out of reader-facing output.
3. Speaker/role handling or report hierarchy preserves the source's actual structure.
4. Interpreted speech is attributed to the original speaker when the source supports that attribution.
5. Korean register does not create unintended hierarchy.
6. Currency, billion/억 conversion, percentages, bp and fiscal/calendar periods preserve economic magnitude.
7. Domain relationships and polarity/modality are preserved.
8. Explanatory notes prevent likely misunderstanding, appear at the first useful occurrence and have a recorded basis.
9. Boilerplate is smoothed without dropping substance.
10. Every material repeated numeric occurrence is checked in the final output, not sampled once.
11. The chosen generation mode is real and reviewable: single-pass produces a complete draft that is checked end-to-end; chunked generation saves genuine semantic units before assembly.
12. The source-to-output path remains inspectable without relying on prior chat history.
13. Structural metrics are not treated as proof of semantic quality.
14. Reader-visible source corrections are transparent and evidence-backed.
15. When terminology review applies, naming classes, aliases and former names are consistent from the earliest relevant occurrence.
16. QA records what was run, what was skipped, why, and what uncertainty remains.

## Representative failure classes

### Interpreted speech

Bad:

```text
통역
질문을 받아 주셔서 감사합니다...
```

Target when source flow identifies the speaker:

```text
Executive B
질문 감사합니다...
```

Keep extraction/interpreter metadata in QA rather than reader-facing prose unless the interpreter genuinely is the speaker.

### Fiscal period

Bad:

```text
Example Company B 2027년 1분기 실적 발표
```

Target when the source is fiscal:

```text
Example Company B 2027 회계연도 1분기 실적 발표
```

### Currency and scale

Bad:

```text
100억 규모의 공급망 프로그램
RMB 15 billion
```

Target when the source is RMB 100 billion / 15 billion:

```text
1,000억 위안 규모의 공급망 프로그램
150억 위안
```

### Repeated numeric guidance

Bad:

```text
Source: mid-to-high teens
Output: 한 자릿수 후반에서 10%대 중반
```

Target:

```text
10%대 중반에서 후반
```

QA must check every material recurrence against its own final passage.

### Terminology and aliases

A later-discovered alias, former name or development code must map back to the earliest relevant occurrence. Do not transliterate every medicine or programme mechanically; choose an evidence-backed naming convention and keep it consistent.

### Domain polarity

Do not translate opportunity/enablement language as a constraint or problem unless the source frames it that way.

### Formal-report structure

A long report is not ready merely because the prose exists. Preserve navigable sections, table parity and semantic alignment, notes, links, defined names, financial-statement order and applicable audit/governance labels.

## Reference claims

If the user supplies an accepted reference artifact and asks for equivalent quality:

1. identify the source, candidate and accepted reference;
2. define which structural and semantic axes matter for this document;
3. run applicable candidate QA and, for report HTML, `scripts/evaluate_report_equivalence.py`;
4. compare source fidelity, numeric coverage and reader-facing Korean separately from structural metrics;
5. record differences and residual risk.

Do not claim equivalence from prompt changes, unit tests or shape metrics alone.
