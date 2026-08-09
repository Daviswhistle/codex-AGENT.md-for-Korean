# Terminology and Entity Naming Reference

Read this reference when a source contains reader-visible names that require a Korean rendering or identity map: brands, medicines, drug candidates, programmes, trial names, aliases, former names, acquired names, or development codes. Routine stable acronyms and ordinary technical terms alone do not trigger this reference. The purpose is to prevent identity confusion and arbitrary script switching across a translation.

## Reader Contract

1. A Korean reader should be able to tell whether two labels identify the same entity, different entities, or a renamed entity.
2. Naming choices must be evidence-backed and stable across the document. Do not decide each occurrence independently while translating chunks.
3. Consistency applies within a naming class, not as a blind rule that every drug name must be transliterated or every proper noun must remain in Latin script.
4. A later Q&A turn, footnote, table, appendix, or speaker correction may reveal an alias or rename that changes how the first occurrence should be presented. Earlier chunks must be revised when later source evidence changes the entity map.

## Build the Terminology Ledger Before Translation

Scan the entire source before translating substantive chunks and record the names whose rendering or identity needs a deliberate decision. Do not force routine acronyms or unambiguous generic terms into the ledger merely because they appear in the source.

Record at least:

- source form and exact case
- entity class: brand, nonproprietary medicine name, drug candidate, trial, programme, company, person, or development code
- canonical reader-facing form
- source spelling to retain at first occurrence, if useful
- aliases, former names, acquired names, and development codes
- current-versus-former status
- first source occurrence and later disambiguating occurrences
- evidence basis: source-derived, official Korean source, regulator or society usage, established specialist usage, or externally verified
- disposition for later occurrences

For long documents, save the ledger under `work/terminology.tsv` or an equivalent inspectable file. A short source may use an in-memory ledger recorded in QA. Create a separate alias map only when the relationships are complex enough that the main ledger would become unclear.

## Selection Hierarchy

Choose the reader-facing form in this order, while considering the document's audience:

1. Official Korean-language material from the entity or rights holder.
2. Korean regulator, clinical-trial registry, medical society, exchange filing, or other authoritative domain usage.
3. Consistent established usage across reputable Korean specialist and business publications.
4. The exact source spelling when no established Korean form exists, or when the item is a code, acronym, trial name, or proprietary styling whose script carries identity.
5. A verified Korean transliteration only when Korean pronunciation materially helps the intended reader and the pronunciation or international naming convention is reliable.

Do not invent a new transliteration from spelling alone. If neither an established Korean rendering nor a reliable pronunciation is available, preserve the source form. Record external verification in QA when it determines the output form.

## Naming-Class Consistency

1. Decide the convention for each comparable class before translation: approved brands, investigational candidates, generic names, trial acronyms, programme names, and development codes may legitimately use different conventions.
2. Within a class, do not leave one candidate in proprietary Latin styling while transliterating a comparable candidate into Korean without a reader-facing reason.
3. When Korean is the primary form, the first occurrence may include the source spelling in parentheses. Use the Korean form alone afterward unless the source spelling is needed to distinguish entities.
4. Preserve trial acronyms, alphanumeric codes, and legally significant proprietary casing when transliteration would reduce traceability.
5. Check spelling, case, spacing, hyphenation, and number attachment at every occurrence. `NN9487`, `REDEFINE 11`, and a medicine's canonical name are different naming roles.

## Aliases, Former Names, and Renames

1. Resolve aliases across the entire source, not only within the current paragraph or chunk.
2. When the source itself later proves that two names refer to the same entity, treat the relationship as source-derived and revise the first occurrence.
3. Prefer the current canonical name as the primary form. Add the former or alternate name at the first relevant occurrence when readers may know the asset by that name or when the source later switches names.
4. Preserve historically accurate speaker wording when material, but clarify identity compactly: `종전 명칭 X`, `현재 Y`, or an equivalent natural construction.
5. Do not describe two names as aliases merely because they appear near each other. Verify the relation from the source or an authoritative external source.
6. Record whether the relation is `source-derived`, `officially verified`, or still uncertain. Uncertainty must remain visible rather than being converted into a confident identity claim.

## Regression Example

Bad:

```text
CagriSema는 ...
경구용 제나감타이드는 ...
[Later in the document]
아미크레틴 질문은 ...
```

Problems:

- comparable candidate names use different script conventions without a reason
- the old and current names of one asset are connected only after the reader has already encountered both
- each chunk appears to have made its own terminology decision

Target when established Korean forms are the chosen convention:

```text
카그리세마(CagriSema)는 ...
경구용 제나감타이드(zenagamtide·구 아미크레틴)는 ...
[Later occurrences]
카그리세마 ... 제나감타이드 ...
```

This example is not a universal rule that all medicine names must be written in Korean. It demonstrates a source-wide term ledger, consistent treatment of comparable candidates, first-occurrence source spelling, and back-propagation of a later alias discovery.

## Conceptual Review

Inspect:

1. whether every ledgered name has a deliberate class and output convention
2. whether comparable entities drift between Korean and source spelling
3. whether current names, former names, aliases, and codes are mapped correctly
4. whether a later source passage should change an earlier first occurrence
5. whether first-occurrence parentheticals are useful rather than cluttered
6. whether the translation preserves distinctions among a combination product, a single molecule, an ingredient, a brand, and a trial programme
7. whether externally verified terminology is supported by an authoritative or established source

Treat identity confusion or a false alias as P1. Treat arbitrary naming-class drift, a missing useful former name, or delayed alias disclosure as P2.

## QA Gate

Before delivery, when this reference applies:

1. compare the final output against the terminology ledger occurrence by occurrence
2. search for every source spelling, Korean rendering, alias, former name, and code recorded in the ledger
3. verify only intentional first-occurrence source spellings remain when the chosen convention uses Korean thereafter
4. verify the earliest relevant occurrence contains any necessary alias or former-name explanation
5. record changed conventions, evidence, accepted exceptions, and residual ambiguity in `work/qa_report.md`
