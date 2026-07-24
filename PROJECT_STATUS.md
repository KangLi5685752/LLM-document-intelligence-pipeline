# Project Status

- **Current stage:** Stage 3B.1 complete - `deterministic-baseline-v0.1` plan frozen; development-only loader next
- **Last updated:** 2026-07-24
- **Latest milestone:** Froze the deterministic candidate-extraction experiment, matching and held-out-access contract before implementation
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0 foundation.
- Stage 1 corpus strategy, audit, synthetic fixtures, evaluation design and `stage1-corpus-v1.0` freeze.
- Stage 2 Common Document Object, PDF/PPTX/EML parsers, dispatcher, CLIs, batch ingestion and frozen-corpus validation.
- Stage 3A candidate extraction schema `0.1`, predicate vocabulary `0.1`, public annotation models and checksummed `public-gold-v0.1` freeze.
- `deterministic-baseline-v0.1` machine-readable plan.
- Public-PDF development/held-out boundary.
- Supported predicate scope.
- Matching protocol v0.1.
- Confidence and review-routing contract.
- Baseline freeze and first-held-out-run protocol.

## In progress

- Stage 3B.2 development-only annotation loader and held-out access guard.

No deterministic or LLM extractor, reconciliation layer, extraction result or extraction metric exists yet.

## Next tasks

1. Implement metadata-first development-only annotation loading.
2. Fail closed on held-out access by default.
3. Add tests proving held-out values are not returned to rule-design code.
4. Implement source-independent deterministic rules only after loader review.
5. Evaluate on development labels.
6. Freeze code and rules before held-out evaluation.

## Blockers

No technical blocker. Held-out access must remain disabled until a future baseline freeze manifest exists.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
