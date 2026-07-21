# Project Status

- **Current stage:** Stage 2 complete - frozen-corpus ingestion validated; Stage 3 extraction next
- **Last updated:** 2026-07-21
- **Latest milestone:** Validated all 15 frozen PDF, PPTX and EML sources as schema-valid provenance-preserving ParsedDocument outputs
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
- Manifest-driven batch ingestion.
- First held-out ingestion validation.
- Full frozen-corpus ingestion validation.
- Stage 2 acceptance report.

## In progress

None for Stage 2.

## Next tasks

1. Define the versioned Stage 3 predicate vocabulary.
2. Create the public-PDF gold annotation subset.
3. Implement a deterministic extraction baseline.
4. Evaluate the baseline on development labels.
5. Freeze the baseline before held-out extraction evaluation.
6. Do not begin RAG before extraction evaluation.

## Blockers

No Stage 3 planning blocker is identified.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
