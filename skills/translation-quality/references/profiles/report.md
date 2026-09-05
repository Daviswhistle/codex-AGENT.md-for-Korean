# Formal Report Profile

Use for annual reports, audit reports, prospectuses, financial statements, governance reports and other page/table-heavy formal documents. Read `references/core.md` first.

## Contract

1. Preserve page/section hierarchy, table inventory, defined terms, bilingual names, statutory/legal labels, footnotes, signatures, audit blocks and financial-statement structure.
2. Build a page/section map and table inventory during intake.
3. Preserve table column parity and semantic alignment: descriptive text left, numeric/financial cells right, short codes centered.
4. Remove repeated extraction headers, footers, page markers and raw Markdown without removing substantive content.
5. Use `agents/korean_report_reviewer.md` for conceptual review.

## Final QA

Verify:

- page/section order and heading hierarchy
- table count/shape, row parity and alignment
- footnotes, links, signatures, audit opinions and governance labels
- exact title and reporting period
- absence of extraction residue
- reviewer findings and residual risk

Resolve `<skill-root>` as the directory containing the skill's `SKILL.md`.

```bash
python3 "<skill-root>/scripts/qa_html_translation.py" \
  --output outputs/<document>_ko.html \
  --expect-title "<exact Korean title>" \
  --profile report \
  --strict-style
```

When the user supplies an accepted reference HTML and asks for equivalence:

```bash
python3 "<skill-root>/scripts/evaluate_report_equivalence.py" \
  --candidate outputs/<candidate>_ko.html \
  --reference /path/to/accepted_reference.html \
  --expect-title "<exact Korean title>" \
  --expect-pages <page-count> \
  --require-core-counts-match
```

Structural equivalence is only one axis. Source fidelity, numeric checks, defined-name consistency, natural Korean and conceptual review remain separate gates. Record commands/results in `work/qa_report.md`; do not create permanent repository evidence solely for one evaluation.

## Final-file checks

1. Korean charset/language metadata and closing structural tags are present.
2. Tables have exact row/column parity and meaningful alignment classes.
3. Links and footnotes remain usable.
4. No raw source/helper metadata appears in the reader-facing title block.
5. No accepted material report-review finding remains unresolved.
