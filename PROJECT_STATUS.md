# Project Status

- **Current stage:** Stage 3B.4B-D complete - deterministic-baseline-v0.1 failed observation diagnosed and preserved; v0.2 experiment planning next
- **Last updated:** 2026-07-26
- **Latest milestone:** Isolated the reproducible S004 extractor defect to a commitment candidate with an incompatible metric subject type, without modifying v0.1 code or observation artifacts
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
- Immutable `deterministic-baseline-v0.1` first-observation evidence.

## In progress

- `deterministic-baseline-v0.2` experiment planning.

The authoritative v0.1 first observation is the versioned `observation_lock.json`. S004 has no candidate output, so no complete development evaluation report or final baseline freeze exists. Formal challenge-case owner review is deliberately deferred. No held-out extraction result, LLM extractor or reconciliation layer exists.

## Next tasks

1. Merge the v0.1 workflow, failed observation and diagnosis.
2. Create and review the `deterministic-baseline-v0.2` experiment plan.
3. Freeze the permitted source-independent correction and tuning scope.
4. Implement the neutral S004 regression test and approved v0.2 changes.
5. Rerun all five development sources twice.
6. Complete owner challenge review only after a complete run.
7. Finalize and freeze only if every acceptance gate passes.
8. Keep held-out access blocked.

## Blockers

- v0.1 cannot be finalized.
- v0.2 implementation cannot begin until its plan is reviewed and frozen.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
