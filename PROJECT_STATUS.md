# Project Status

- **Current stage:** Stage 3A.1 - candidate contract hardening and public-gold correction
- **Last updated:** 2026-07-22
- **Latest milestone:** Enforced runtime predicate usage, corrected two semantic annotation defects and expanded owner review to all 35 draft facts
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
- Candidate extraction models.
- Predicate vocabulary v0.1.
- Public annotation models and deterministic validator.
- 35 draft public-PDF fact annotations.
- Ambiguous, unsupported, and missing-value challenge cases.
- Structural public annotation validation.
- Owner review checklist.
- Shared runtime predicate-use validation for candidate and gold fact models.
- Structured metric, recommendation and budget qualifiers across the 35-fact draft.
- Corrected recommendation subject attribution and removed false day-level date precision.
- Full 35-fact owner review worksheet.

## In progress

- Full owner review of all 35 public annotations.
- Any further correction and verification identified by owner review.
- Public-gold v0.1 approval.
- Deterministic baseline design.

## Next tasks

1. Complete the full 35-fact owner review.
2. Correct rejected or ambiguous annotations.
3. Mark accepted records `owner_verified`.
4. Freeze public-gold v0.1.
5. Implement deterministic extraction on development sources only.
6. Do not access held-out annotations during baseline rule design.

## Blockers

No technical blocker is identified. Public-gold approval depends on project-owner review.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
