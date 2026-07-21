# Project Status

- **Current stage:** Stage 2A - Common Document Object and development-source parsing
- **Last updated:** 2026-07-21
- **Latest milestone:** Implemented the initial provenance-preserving PDF, PPTX and EML ingestion boundary for frozen development sources
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0 foundation.
- Stage 1A corpus and licence strategy.
- Stage 1B public-PDF audit.
- Deterministic PDF audit utility.
- S001-S007 source and technical review.
- Synthetic PPTX and EML fixtures.
- Synthetic ground truth.
- Product definition.
- Extraction-schema design.
- Evaluation plan.
- Corpus-split manifest.
- `stage1-corpus-v1.0` freeze.
- Stage 1 completion report.
- Versioned Common Document Object.
- PDF parser.
- PPTX parser.
- EML parser.
- Parser dispatcher.
- Single-document CLI.
- Ingestion tests.
- Development-source validation.

## In progress

- Held-out ingestion validation.
- Full frozen-corpus ingestion report.
- Parser hardening based on format-general defects.
- Stage 2 acceptance report.

## Next tasks

1. Freeze the Stage 2A parser commit.
2. Run all six held-out sources without content-specific tuning.
3. Run all 15 frozen sources through a batch validator.
4. Record structured parser failures and warnings.
5. Complete the Stage 2 acceptance report.
6. Do not begin extraction until all Stage 2 gates are satisfied.

## Blockers

No Stage 2 blocker is identified.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
