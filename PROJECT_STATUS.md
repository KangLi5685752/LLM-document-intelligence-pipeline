# Project Status

- **Current stage:** Stage 3B.4A complete - strict development evaluator implemented before score observation; development execution and baseline freeze next
- **Last updated:** 2026-07-25
- **Latest milestone:** Implemented source-bounded strict matching, typed value alignment, evidence metrics and deterministic development-report contracts without running the real benchmark
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

## In progress

- Stage 3B.4B first development execution, error analysis and baseline freeze.

No public-gold extraction metric, held-out extraction result, LLM extractor or reconciliation layer exists yet.

## Next tasks

1. Regenerate or verify the five frozen development `ParsedDocument` inputs.
2. Run deterministic extraction twice.
3. Preserve canonical outputs and hashes.
4. Complete three owner challenge-case assessments.
5. Generate the first development report.
6. Classify unmatched predictions and gold facts.
7. Create and validate the baseline freeze manifest.
8. Keep held-out access disabled until review completes.

## Blockers

No technical blocker. No matching or rule change is allowed after the first development report without an explicit new experiment version or documented pre-freeze correction.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
