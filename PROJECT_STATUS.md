# Project Status

- **Current stage:** Stage 3A complete - public-gold-v0.1 frozen; deterministic baseline next
- **Last updated:** 2026-07-23
- **Latest milestone:** Completed project-owner semantic review and froze 35 evidence-linked public facts plus 6 challenge cases
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0 foundation.
- Stage 1 corpus strategy, audit, synthetic fixtures, evaluation design and `stage1-corpus-v1.0` freeze.
- Stage 2 Common Document Object, PDF/PPTX/EML parsers, dispatcher, CLIs, batch ingestion and frozen-corpus validation.
- Candidate extraction contract schema `0.1`.
- Predicate vocabulary `0.1` and runtime predicate-usage validation.
- Public annotation and challenge-case models.
- 35 owner-verified, evidence-linked public facts.
- Six owner-verified challenge cases.
- Exact block, page and excerpt validation against frozen ParsedDocument output.
- Project-owner decision log and completed fact/case review worksheets.
- Checksummed `public-gold-v0.1` freeze manifest.
- Freeze regression tests.
- Stage 3A completion report.

## In progress

- Stage 3B deterministic-baseline experiment planning.

No deterministic or LLM extractor, reconciliation layer or extraction metric exists yet.

## Next tasks

1. Freeze the exact deterministic-baseline experiment plan.
2. Ensure baseline code can load development annotations only.
3. Implement deterministic candidate extraction.
4. Evaluate only on development labels during rule design.
5. Freeze rules and code before held-out evaluation.
6. Do not implement reconciliation or RAG yet.

## Blockers

No technical blocker is identified. Stage 3B must enforce the frozen development/held-out loading boundary.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
