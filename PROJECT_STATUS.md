# Project Status

- **Current stage:** Stage 3B.5B focused deterministic-baseline-v0.4 actor-classification correction complete; final read-only review pending
- **Last updated:** 2026-07-30
- **Latest milestone:** Corrected additive v0.4 preserved all five v0.3 strict development matches with 178 candidates and 25 commitments; quotation checks now precede actor classification, only two complete parent subjects qualify as explicit actors, and eleven non-actor parent subjects are accurately preserved without semantic rewrites
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0 foundation.
- Stage 1 corpus strategy, audit, synthetic fixtures, evaluation design and `stage1-corpus-v1.0` freeze.
- Stage 2 Common Document Object, PDF/PPTX/EML parsers, dispatcher, CLIs, batch ingestion and frozen-corpus validation.
- Stage 3A candidate extraction schema `0.1`, predicate vocabulary `0.1`, public annotation models and checksummed `public-gold-v0.1` freeze.
- Stage 3B.1 `deterministic-baseline-v0.1` experiment and strict matching protocol `0.1`.
- Guarded development-only gold access with metadata-first routing and held-out denial.
- Pure ParsedDocument deterministic extraction, canonical output, hash-derived IDs and exact evidence provenance.
- Development-run, reproducibility, owner-review, observation-lock and transactional freeze contracts.
- Immutable failed v0.1 observation and read-only S004 diagnosis.
- Frozen additive v0.2 plan, extractor, evaluator, execution workflow and evidence-integrity controls.
- PR #17 merged through commit `35949e538756c2e592533fda1564da29427ae03a`.
- Frozen `deterministic-baseline-v0.2` development evidence: TP 0, FP 321, FN 25, F1 null and challenge pass rate 2/3.
- PR #18 merged through commit `bc758f2a294023b1629565badbbbdb5b89dca4d6`.
- Stage 3B.5A additive `deterministic-baseline-v0.3` integrated development comparison: TP 5, FP 172, FN 20, recall 0.20, F1 0.04950495049504951 and automated challenge diagnostics 3/3 passed; formal v0.3 owner assessment was not performed.
- Stage 3B.5B corrected additive `deterministic-baseline-v0.4` local development comparison: TP 5, FP 173, FN 20, precision 0.028089887640449437, recall 0.2, F1 0.04926108374384237, 178 candidates and 25 commitments. All five v0.3 strict matches remain; no S002 commitment is a strict match. The first attempt's `PG-V01-S002-001` and `PG-V01-S002-003` matches were rejected because print-location and indirect-publication cues do not establish a role-aware government author. The final actor-method inventory is one `authors_or_senders`, two `explicit_statement_actor`, eleven `preserved_parent_subject` and eleven `unresolved`; non-commitment facts and resolved evidence are identical to v0.3, and formal v0.4 owner assessment has not been performed.

## In progress

- Final focused read-only review of the corrected uncommitted Stage 3B.5B v0.4 quotation ordering, explicit-actor eligibility, preserved-parent vocabulary and candidate trace.

The authoritative v0.1 observation and complete v0.2 and v0.3 baselines remain frozen and immutable. Stage 3B.5B uses separate additive v0.4 modules with unchanged candidate schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1` and `match_strict_facts`. Quotation and reported-speech checks precede actor classification; explicit statement actors require bounded eligibility, and unchanged non-actor parent subjects are classified as `preserved_parent_subject` without rewriting their semantics. Role-aware authoring evidence is required for document-level actor resolution; titles, generic publisher/creator metadata, licence or parliamentary boilerplate, and printing/publication location are ignored. Its report calculator explicitly reconciles matcher counts and compares resolved non-commitment evidence as well as fact semantics. No held-out semantic annotation model was deserialized; no S005 or S007 ParsedDocument was opened or executed; held-out raw JSONL bytes and row metadata may be scanned by the guarded loader only for integrity verification and split routing. No held-out extraction result, LLM extractor or LLM reconciliation layer exists.

## Next tasks

1. Complete the final focused read-only review of corrected quotation ordering and actor-method attribution.
2. Review the exact v0.2 versus v0.3 versus corrected v0.4 comparison, lost first-attempt matches and sparse-gold claim boundary.
3. Complete a separate formal v0.4 owner assessment only after implementation review.
4. Commit and open a separately reviewed v0.4 pull request only after approval.
5. Keep held-out execution blocked behind a later explicit guard and authorization.

## Blockers

- v0.1 cannot be finalized.
- Corrected Stage 3B.5B changes remain uncommitted pending independent review.
- Formal v0.4 owner assessment has not been performed.
- Sparse development gold cannot independently establish exhaustive candidate precision.
- Held-out access remains blocked pending a separate reviewed guard and explicit authorization.

## AG News replacement status

Not yet eligible. Replacement remains conservative until extraction quality improves beyond the small development recovery, benchmark limitations are presented clearly and the project presentation is portfolio-ready.
