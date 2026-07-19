# LLM Document Intelligence & Knowledge Extraction Pipeline

Work in progress. This repository is being developed incrementally as an evaluated portfolio prototype, not as a production enterprise system.

## Problem statement

Project information is often scattered across heterogeneous PDF, PowerPoint, and email-style documents. Manually converting those sources into consistent records is slow, while automated extraction can be difficult to trust when it loses source context or presents ambiguous claims as facts. This project will explore how to produce schema-validated, traceable, and queryable project intelligence while preserving document-level evidence and routing uncertain outputs for review.

## Target users

- Analysts and project professionals who need structured facts from mixed document collections.
- Data and AI practitioners evaluating evidence-aware document extraction workflows.
- Reviewers who need to verify extracted claims against page, slide, or section-level evidence.

## Planned core capabilities

- Parse PDF, PPTX, and email-style text into a common document representation.
- Segment content and compare baseline extraction with structured LLM extraction.
- Validate extracted records against explicit schemas.
- Align extracted claims with source evidence.
- Detect unsupported or conflicting outputs and route ambiguous cases for human review.
- Evaluate extraction quality before adding retrieval or deployment layers.

## Current status

**Stage 1B: expanded corpus audit and synthetic challenge-set design (in progress).** S001–S007 have completed public-PDF source and technical review and are approved for documented local corpus and future evaluation use. All seven original PDFs remain local and uncommitted. S004–S007 add complex visual, tabular, statistical, and multi-column cases. Synthetic PPTX and email-style challenge sets remain outstanding. No Stage 2 parser or extraction evaluation exists, and no extraction evaluation results exist yet.

## Stage 1B audit utility

The deterministic PDF audit utility records file integrity, page counts, and screening-level text-density warnings during local corpus review. It is not the production ingestion parser and does not perform OCR, licence decisions, or semantic extraction evaluation.

~~~powershell
audit-pdfs --input-dir data/raw --output artifacts/audits/pdf_audit.csv
~~~

Source files under data/raw and generated audit artefacts under artifacts/audits remain local and ignored by Git. See the [pilot utility validation](docs/stage_1b_audit_utility_validation.md) for observed Stage 1B results and limitations.

## Planned stages

1. **Stage 0 — Project Charter and Repo Setup**: **Completed.** Define the scope, architecture, decisions, packaging, and evaluation intent.
2. **Stage 1 — Corpus Audit**: **In progress: Stage 1B.** Verify pilot sources, audit exact local files, record rights and technical evidence, and decide corpus suitability without treating acquisition as approval.
3. **Stage 2 — Document Ingestion**: **Planned.** Add format-specific parsing, a common Document Object, preprocessing, and segmentation for the MVP formats.
4. **Stage 3 — Baseline and Structured Extraction**: **Planned.** Add deterministic baseline and structured LLM extraction, schema validation, evidence alignment, conflict checks, and review routing.
5. **Stage 4 — Extraction Evaluation**: **Planned.** Evaluate extraction quality, schema validity, evidence alignment, and review-routing behaviour on a labelled corpus.
6. **Stage 5 — Storage and Data Model**: **Planned.** Define the validated knowledge model and local persistence before considering BigQuery.
7. **Stage 6 — Interface**: **Planned.** Add an interface or API only for capabilities supported by evaluation evidence.
8. **Stage 7 — Retrieval and RAG**: **Planned.** Add structured retrieval and grounded RAG over validated, evidence-linked records.
9. **Stage 8 — Cloud Deployment**: **Planned.** Consider Docker, Cloud Run, and cloud data services after the local prototype is justified.
10. **Stage 9 — Portfolio Packaging**: **Planned.** Consolidate reproducible results, limitations, documentation, and demonstration materials without overstating outcomes.

## Local development

The development workflow is intentionally minimal at this stage. From the repository root, the planned setup commands are:

~~~powershell
python -m pip install -e ".[dev]"
python -m pytest
~~~

Future stages will expand these instructions only when executable capabilities are added.
