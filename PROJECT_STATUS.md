# Project Status

- **Current stage:** Stage 3B.4B - two-checkpoint development execution and baseline-freeze workflow implemented; owner-reviewed finalization remains pending
- **Last updated:** 2026-07-26
- **Latest milestone:** Implemented exact five-source preparation, two-pass canonical extraction evidence, first-observation locking, owner-review packet generation and fail-closed finalization
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0 foundation.
- Stage 1 corpus strategy, audit, synthetic fixtures, evaluation design and `stage1-corpus-v1.0` freeze.
- Stage 2 Common Document Object, PDF/PPTX/EML parsers, dispatcher, CLIs, batch ingestion and frozen-corpus validation.
- Stage 3A candidate extraction schema `0.1`, predicate vocabulary `0.1`, public annotation models and checksummed `public-gold-v0.1` freeze.
- Stage 3B.1 `deterministic-baseline-v0.1` experiment and matching contract.
- Guarded baseline gold API.
- Experiment and manifest compatibility validation.
- Byte-level hash checks.
- Metadata-first JSONL routing.
- Development-only semantic validation.
- Deterministic non-semantic summary CLI.
- Held-out denial tests.
- Ten-family deterministic rule inventory.
- Eight candidate-producing predicates.
- Bounded statement segmentation.
- Same-block subject attribution.
- Typed percentage and money normalization.
- Exact evidence references.
- Fixed confidence and review contract.
- Deterministic IDs and canonical JSON.
- ParsedDocument-only deterministic CLI.
- Neutral source-independent rule tests.
- Protocol-v0.1 comparison normalization.
- Strict one-to-one fact matcher.
- Material qualifier projection.
- Separate normalized-value alignment.
- Evidence source/location metrics.
- Source-attempt and reproducibility models.
- Explicit owner challenge-assessment model.
- Canonical development evaluation report.
- Strict development-run provenance models.
- Exact-path five-source input validation.
- Two-pass canonical candidate-output preservation.
- First-observation lock contract.
- Deterministic structural unmatched inventory.
- Pending owner-review packet and assessment template.
- Final report and baseline-freeze validation workflow.

## In progress

- Stage 3B.4B-1 first development execution and owner-review handoff.

The authoritative first observation, when created, is the versioned `observation_lock.json`; no complete development evaluation report or final baseline freeze exists until owner review and `finalize` complete. No held-out extraction result, LLM extractor or reconciliation layer exists.

## Next tasks

1. Generate fresh development-only `ParsedDocument` inputs with the frozen parser commit.
2. Run checkpoint 3B.4B-1 `prepare` and preserve the observation lock.
3. Have the project owner review the three development challenge cases.
4. Supply all three explicit outcomes and rationales.
5. Run `finalize` to create the complete report, final error analysis and baseline freeze.
6. Keep held-out access disabled pending a separately reviewed Stage 3B.5 guard.

## Blockers

Checkpoint 3B.4B-2 is blocked until the project owner supplies all three challenge-case outcomes and rationales. After the first observation lock, no deterministic-rule, matching or evaluator semantic change is allowed in v0.1; further tuning requires `deterministic-baseline-v0.2`.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
