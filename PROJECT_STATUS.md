# Project Status

- **Current stage:** Stage 4A LLM extraction planning in progress
- **Last updated:** 2026-08-03
- **Latest milestone:** Stage 3B closed with the immutable `deterministic-baseline-v0.4` development freeze; Stage 4A now defines a controlled development-only LLM comparator contract
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
- PR #19 merged through commit `4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc`, completing and integrating Stage 3B.5B.
- Corrected additive `deterministic-baseline-v0.4` authoritative development comparison: TP 5, FP 173, FN 20, precision 0.028089887640449437, recall 0.2, F1 0.04926108374384237, 178 candidates and 25 commitments. All five original v0.3 strict matches remain; no S002 commitment is a strict match. The final actor-method inventory is one `authors_or_senders`, two `explicit_statement_actor`, eleven `preserved_parent_subject` and eleven `unresolved`; non-commitment facts and resolved evidence are identical to v0.3.
- Stage 3B.5C deterministic v0.4 owner-review preparation: exact five-source input and candidate hashes, three frozen challenge cases, all evidence-linked candidates, resolved evidence and warning inventories were assembled with three blank owner assessment rows. At that preparation checkpoint, automated challenge diagnostics were 3/3 structural passes while formal owner outcomes remained 0 completed and 3 pending.
- PR #20 merged the Stage 3B.5C owner-review preparation package at `36fe312ef07716a3597ea62a5d146a12b1c9312b`.
- Stage 3B.5D formal v0.4 owner assessment: Kang Li supplied `passed` outcomes and exact evidence-based rationales for `PGC-V01-S001-001`, `PGC-V01-S004-001` and `PGC-V01-S006-001`. The separate completed record retains candidate counts 6, 0 and 6, preserves the blank template, and passes deterministic metadata, reference, evidence-consistency, owner-versus-machine and held-out-isolation checks.
- PR #21 merged Stage 3B.5D through commit `d9cddfd21a302151213ea5cde27f400a382e1e64`. The required independent read-only audit passed with no critical findings or required corrections and is recorded separately as machine review evidence.
- Stage 3B.5E-1 finalization and freeze transaction implementation completed through PR #22, with the predicate string-counting correction in PR #23 and lifecycle-safe read-only audit coverage in PR #24. The finalization implementation commit is `d798868bd8b66a30babfc1b14450fb253f2dbc63`.
- Stage 3B.5E-2 controlled real finalization completed successfully with freeze date `2026-08-02`. PR #25 merged the finalized evidence and post-finalization test compatibility at `3d16248` and closed Stage 3B.
- The committed finalization inventory contains exactly fourteen artifacts: five primary candidate outputs, five repeat candidate outputs, `development_evaluation_report.json`, `final_error_analysis.json`, `finalization_record.json` and `baseline_freeze_manifest.json`. Every primary/repeat pair is byte-identical.
- The frozen `deterministic-baseline-v0.4` development observation contains 178 candidates and 25 commitment candidates, with TP 5, FP 173, FN 20, precision 0.028089887640449437, recall 0.2, F1 0.04926108374384237, zero duplicate candidates and zero S002 strict matches.
- Formal project-owner outcomes passed 3/3: S001 `preserve_missing`, S004 `do_not_extract` and S006 `route_to_review`. Automated diagnostics also passed 3/3 but remain separate from formal owner judgment.
- Public validation at the implementation commit returned `valid`; all fourteen artifacts were present, all 28 process gates passed, nine quality observations remained non-binding, the independent review verdict was `approved_for_evidence_commit`, transaction residue was absent, and evidence and candidate hashes remained fixed.
- The final post-finalization suite passed with 1107 tests and 6 skips. GitHub Actions passed on Python 3.10, 3.11 and 3.12.
- Stage 3B is closed as a reproducible engineering and evaluation milestone, not as evidence of strong extraction quality, exhaustive candidate precision, held-out generalization or production readiness. Held-out execution remained unauthorized; no S005 or S007 ParsedDocument was opened or executed during finalization, and held-out semantic annotations were not loaded for execution.

## In progress

- Stage 4A planning for `llm-extraction-baseline-v0.1`: development-only scope, provider decision gate, prompt/output contract, request budget, cache and provenance, strict comparison and LLM-specific evaluation metrics.
- No provider or model has been selected, no LLM API has been called, and no Stage 4 extraction or evaluation result exists.
- Stage 3B and `deterministic-baseline-v0.4` remain completed, frozen and immutable. Held-out execution remains unauthorized.

## Next tasks

1. Complete and review Stage 4A planning and the `llm-extraction-baseline-v0.1` experiment contract.
2. Stage 4B: implement the provider-neutral interface, deterministic mock mode and versioned prompt/output contracts without real network calls.
3. Stage 4C: implement the development-only runner, append-only local cache and complete request/response provenance using mock execution.
4. Accept a separate provider/model decision, then Stage 4D may perform one bounded five-source development execution with at most one provider.
5. Stage 4E: evaluate fixed candidates with the unchanged matcher, complete error analysis and owner review, and optionally freeze only if every mandatory process gate passes.
6. Preserve immutable deterministic v0.4 evidence and keep held-out execution blocked behind a later separately reviewed guard and explicit project-owner authorization.

## Blockers

- Stage 3B has no remaining implementation work and its v0.4 evidence is immutable.
- The Stage 4 provider and model have not been selected; real-provider implementation and execution remain blocked until a separate reviewed decision is accepted.
- Held-out execution remains blocked pending a separate reviewed guard and explicit authorization.
- `deterministic-baseline-v0.4` is frozen and immutable; any later semantic change requires `deterministic-baseline-v0.5`.
- Sparse development gold cannot independently establish exhaustive candidate precision.
- The weak deterministic development score and absence of any LLM result do not support model-superiority, held-out-generalization or production-readiness claims.

## AG News replacement status

Not yet eligible. Stage 4A is a plan rather than an implemented LLM extraction layer. Weak deterministic development quality, no LLM comparison result, no held-out result and the lack of a final portfolio presentation still prevent replacement.
