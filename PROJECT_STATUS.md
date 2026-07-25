# Project Status

- **Current stage:** Stage 3B.3 complete - deterministic candidate-extraction rule engine implemented; development evaluation and baseline freeze next
- **Last updated:** 2026-07-25
- **Latest milestone:** Implemented source-independent ParsedDocument-to-CandidateExtractionResult rules for eight predicates with exact evidence, deterministic IDs and conservative abstention
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

## In progress

- Stage 3B.4 development evaluation, error analysis and baseline freeze.

No public-gold extraction metric, held-out extraction result, LLM extractor or reconciliation layer exists yet.

## Next tasks

1. Build the strict matching implementation from protocol v0.1.
2. Run extraction on the five development public-PDF ParsedDocuments.
3. Compute development-only metrics with exact numerators and denominators.
4. Produce per-predicate and failure-taxonomy analysis.
5. Freeze code, rules, outputs and metrics.
6. Keep held-out access disabled.

## Blockers

No technical blocker. Held-out access remains unavailable until the Stage 3B.4 freeze manifest is completed and reviewed.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
