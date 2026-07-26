# Stage 3B v0.1 First-Observation Failure

## Status

`deterministic-baseline-v0.1` completed its first development observation, but the run did not satisfy baseline acceptance. No complete development evaluation report or baseline freeze manifest exists, held-out access remains blocked, and the published v0.1 observation artifacts are immutable.

## Ingestion result

- All 9 development sources parsed successfully, with 0 ingestion failures.
- The five scored public PDFs were identified as S001, S002, S003, S004 and S006.
- S004 ingestion succeeded; its failure occurred later during deterministic extraction.

## Extraction result

- S001, S002, S003 and S006 succeeded twice with byte-identical primary and repeat outputs.
- S004 failed twice with the same exception and produced no candidate output.
- `all_outputs_byte_identical=false` because the five-source aggregate was incomplete.
- Four candidate outputs exist; no S004 candidate output exists.

## Exact S004 failure

Both direct calls raised the sanitized exception:

- type: `DeterministicExtractionError`;
- message: `deterministic output violates CandidateExtractionResult schema 0.1`;
- underlying validation cause: predicate `commitment` does not allow subject type `metric`;
- deepest relevant repository function: `extract_deterministic_candidates` in `document_intelligence.extraction.deterministic`;
- failure stage: `CandidateFact` validation while constructing the aggregate `CandidateExtractionResult`;
- block: `DOC-S004-B0018`, sequence 18, page 18;
- rule and predicate: `DET-RULE-COM-001`, `commitment`.

The direct full-document calls failed identically, including the complete exception chain. A block-level replay isolated the same failure to the block above. Segmentation, subject attribution, rule matching, value normalization and evidence-span construction completed before the incompatible candidate reached schema validation. No source text, absolute path or full traceback is retained in this report.

The primary root-cause category is **extractor implementation defect**. The source-independent subject classifier can assign `metric` to a subject matched by the commitment rule, although the frozen predicate contract does not permit that combination. The schema correctly rejects the incompatible candidate.

A neutral one-block synthetic fixture reproduces the same exception without any source ID, filename, title, page-specific condition or expected value. A minimal neutral regression test can therefore cover the defect in a later version. Any correction must decide whether to abstain or produce a differently typed candidate, so it changes extraction output semantics rather than merely suppressing an exception.

## Preliminary diagnostics

The incomplete first observation records:

- TP: 0;
- FP: 288;
- FN: 25;
- precision: 0/288;
- recall: 0/25;
- F1: null under protocol v0.1;
- duplicate candidates: 7;
- review-required candidates: 0.

These are first-observation diagnostics, not an accepted or finalized benchmark. Strict matching may under-credit semantic equivalents. The large commitment candidate population indicates over-triggering that requires versioned analysis.

## Acceptance-gate outcome

- `all_sources_complete`: failed;
- `candidate_schema_valid`: incomplete because S004 produced no result;
- `repeat_outputs_byte_identical`: failed at the five-source aggregate level;
- `exact_metrics_reported`: preliminary only;
- `challenge_cases_owner_assessed`: pending and deliberately deferred;
- `held_out_semantics_not_loaded`: passed;
- `source_independent_rules`: passed for the v0.1 implementation;
- `no_minimum_f1_gate`: passed.

`BaselineFreezeManifest` cannot legally be instantiated because its contract accepts passed gates only.

## Challenge-review boundary

Review packets exist for S001 and S006. S004 is not assessable as a successful do-not-extract behaviour because its source attempt crashed before candidate generation. Formal owner outcomes are deferred until a complete v0.2 run, and no v0.1 owner outcome is inferred.

## v0.2 requirement

The v0.1 code and observation remain immutable. Correcting the S004 defect or tuning any rule requires `deterministic-baseline-v0.2`, with a new experiment plan reviewed and frozen before implementation. All changes must remain source-independent, and held-out data must remain inaccessible.

## Claim boundary

The project may claim:

- successful first real baseline execution workflow;
- reproducible outputs on four development sources;
- explicit failed-source preservation;
- observation locking and fail-closed freeze behaviour;
- honest identification of an unsuccessful baseline.

The project may not claim:

- a completed five-source baseline;
- accepted development metrics;
- a baseline freeze;
- extraction accuracy;
- held-out performance;
- an LLM comparison;
- production readiness.
