# Project Status

- **Current stage:** Stage 3B.4D-3 local pre-observation audit passed; PR CI and merge pending
- **Last updated:** 2026-07-28
- **Latest milestone:** Completed the local pre-observation audit and froze the exact Git blob inventory for all 14 deterministic-baseline-v0.2 implementation and test files without running real development data
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
- Stage 3B.4D-1 source-independent deterministic-baseline-v0.2 extractor implementation.
- Stage 3B.4D-2 evaluation, evidence-integrity, owner-review, observation-provenance and transactional-finalization workflow.
- Stage 3B.4D-3 local pre-observation implementation audit and 14-file Git blob hash freeze.

## In progress

- PR review, Python 3.10–3.12 CI, merge-commit integration and post-merge validation for `deterministic-baseline-v0.2`.

The authoritative v0.1 first observation is the versioned `observation_lock.json`. S004 has no candidate output, so no complete v0.1 development evaluation report or final baseline freeze exists. The v0.2 implementation and local audit are complete, but PR CI and merge remain pending. No real v0.2 output, score, observation lock, owner assessment or freeze manifest exists. Real v0.2 development execution is not authorized, and no held-out extraction result, LLM extractor or reconciliation layer exists.

## Next tasks

1. Review the implementation PR.
2. Require Python 3.10, 3.11 and 3.12 CI success.
3. Merge using Create a merge commit.
4. Complete post-merge validation on `main` before authorizing real prepare.

## Blockers

- v0.1 cannot be finalized.
- Stage 3B.4D is not fully complete until the implementation PR is merged and post-merge validation passes.
- Real v0.2 development execution remains blocked until that merge commit and post-merge approval exist.
- Held-out access remains blocked pending a successful v0.2 development freeze and a separate reviewed guard.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
