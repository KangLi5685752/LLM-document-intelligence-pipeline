# Project Status

- **Current stage:** Stage 3B.5A local deterministic-baseline-v0.3 development quality recovery complete; review pending
- **Last updated:** 2026-07-29
- **Latest milestone:** Additive v0.3 recovered 5 of 25 development gold facts with unchanged matching protocol `0.1`, the unchanged `match_strict_facts` implementation and an explicitly reconciled additive report calculator; candidates fell from 321 to 177 and all three automated development challenge diagnostics passed
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
- Stage 3B.5A additive `deterministic-baseline-v0.3` local development comparison: TP 5, FP 172, FN 20, recall 0.20, F1 0.04950495049504951 and automated challenge diagnostics 3/3 passed; formal v0.3 owner assessment has not been performed.

## In progress

- Review of the uncommitted Stage 3B.5A v0.3 implementation, neutral source-independent extractor unit tests, development-evidence regression tests and development-only reports.

The authoritative v0.1 observation and complete v0.2 development baseline remain frozen and immutable. Stage 3B.5A uses additive v0.3 modules with unchanged candidate schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1` and `match_strict_facts`. It uses an additive deterministic v0.3 report calculator with explicit matcher reconciliation, not the complete frozen v0.2 evaluator. No held-out semantic annotation model was deserialized; no S005 or S007 ParsedDocument was opened or executed; held-out raw JSONL bytes and row metadata may be scanned by the guarded loader for integrity verification and split routing. No held-out extraction result, LLM extractor or LLM reconciliation layer exists.

## Next tasks

1. Review the additive v0.3 rules, neutral extractor tests, development-evidence regression tests and development-only diagnosis.
2. Review the exact v0.2 versus v0.3 comparison and sparse-gold claim boundary.
3. Defer S002 subject/value representation and actor-resolution work to Stage 3B.5B.
4. Commit and open a separately reviewed v0.3 pull request only after approval.
5. Keep held-out execution blocked behind a later explicit guard and authorization.

## Blockers

- v0.1 cannot be finalized.
- Stage 3B.5A changes remain uncommitted pending review.
- Sparse development gold cannot independently establish exhaustive candidate precision.
- Held-out access remains blocked pending a separate reviewed guard and explicit authorization.

## AG News replacement status

Not yet eligible. Replacement remains conservative until extraction quality improves beyond the small development recovery, benchmark limitations are presented clearly and the project presentation is portfolio-ready.
