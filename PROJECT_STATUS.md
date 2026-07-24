# Project Status

- **Current stage:** Stage 3B.2 complete - development-only public-gold loader and held-out guard implemented; deterministic rule engine next
- **Last updated:** 2026-07-24
- **Latest milestone:** Implemented hash-verified, metadata-first access to 25 development facts and three development challenge cases while denying held-out access before I/O
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

## In progress

- Stage 3B.3 deterministic candidate-extraction rule engine.

No deterministic or LLM extractor, reconciliation layer, extraction result or extraction metric exists yet.

## Next tasks

1. Define source-independent rule modules for the eight supported predicates.
2. Ensure extractor inputs contain `ParsedDocument` only.
3. Generate deterministic `CandidateExtractionResult` records.
4. Add unit fixtures without held-out values.
5. Do not compute public-gold metrics until rule implementation is reviewed.
6. Do not enable held-out access.

## Blockers

No technical blocker. Held-out access remains intentionally unavailable.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
