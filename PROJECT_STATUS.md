# Project Status

- **Current stage:** Stage 1 complete - product contract and corpus v1.0 frozen; Stage 2 ingestion next
- **Last updated:** 2026-07-20
- **Latest milestone:** Frozen a 15-source PDF, PPTX and EML corpus with family-level development and held-out splits, synthetic ground truth, and documented evaluation gates
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

## In progress

None for Stage 1.

## Next tasks

1. Create the Stage 2 common Document Object.
2. Implement PDF parsing with page-level provenance.
3. Implement PPTX parsing with slide-level provenance.
4. Implement EML parsing with message headers and quoted-history separation.
5. Add parser tests across development fixtures.
6. Validate all 15 frozen sources without changing corpus membership.
7. Do not begin extraction until ingestion acceptance gates are met.

## Blockers

No Stage 2 blocker is identified.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
