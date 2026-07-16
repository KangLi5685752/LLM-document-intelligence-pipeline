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

**Stage 0A: project foundation.** The repository currently contains the project charter, architecture plan, decision log, minimal Python package, and a smoke test. No document-processing pipeline has been implemented and no evaluation results exist yet.

## Planned stages

1. **Stage 0 - Foundation:** define scope, architecture, decisions, packaging, and evaluation intent.
2. **Stage 1 - Document model and parsing:** introduce the common Document Object and MVP format parsers.
3. **Stage 2 - Extraction and trust controls:** add preprocessing, baseline and LLM extraction, validation, evidence alignment, and review routing.
4. **Stage 3 - Evaluation and local persistence:** build a reproducible benchmark and store validated local outputs.
5. **Stage 4 - Query and grounded retrieval:** add structured search and, only after evaluation, grounded RAG.
6. **Stage 5 - Interface and deployment:** consider an API, containerisation, BigQuery, and Cloud Run after the local prototype is justified.

## Local development

The development workflow is intentionally minimal at this stage. From the repository root, the planned setup commands are:

~~~powershell
python -m pip install -e ".[dev]"
python -m pytest
~~~

Future stages will expand these instructions only when executable capabilities are added.
