# Project Status

- **Current stage:** Stage 3B.4C - deterministic-baseline-v0.2 experiment planning and freeze
- **Last updated:** 2026-07-26
- **Latest milestone:** Frozen a source-independent v0.2 correction and tuning scope based on the immutable v0.1 development observation, without modifying v0.1 evidence or accessing held-out semantics
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
- Read-only S004 source-independent failure diagnosis.
- Frozen `deterministic-baseline-v0.2` experiment identity, error matrix, bounded change families and additive version boundary.
- Automated v0.2 plan validation, including all nine immutable v0.1 artifact hashes.

## In progress

- Review and merge of the frozen `deterministic-baseline-v0.2` plan.

The authoritative v0.1 first observation is the versioned `observation_lock.json`. S004 has no candidate output, so no complete v0.1 development evaluation report or final baseline freeze exists. The v0.2 scope is frozen before implementation; no v0.2 extractor, output, score, observation lock, owner assessment or freeze manifest exists. No held-out extraction result, LLM extractor or reconciliation layer exists.

## Next tasks

1. Review the v0.2 plan.
2. Merge the planning PR.
3. Implement the neutral compatibility regression.
4. Implement only approved v0.2 change families.
5. Commit implementation before real execution.
6. Run all five development sources twice.
7. Preserve the v0.2 observation lock.
8. Complete owner review.
9. Finalize only if process gates pass.

## Blockers

- v0.1 cannot be finalized.
- v0.2 implementation cannot begin until its frozen plan is reviewed and merged.
- Real v0.2 development execution cannot begin until the approved implementation is committed and all pre-observation gates pass.
- Held-out access remains blocked pending a successful v0.2 development freeze and a separate reviewed guard.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
