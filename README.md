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

**Stage 3B.4B-D records a failed first development observation for `deterministic-baseline-v0.1`.** S001, S002, S003 and S006 produced byte-identical repeat outputs, while S004 failed reproducibly and produced no candidate output. The immutable preliminary strict counts are 0 TP, 288 FP and 25 FN. No complete development evaluation report or baseline freeze exists, formal owner challenge review is deferred, and no held-out extraction result, LLM extractor or reconciliation implementation exists. The next controlled step is the [read-only S004 diagnosis](docs/stage_3b_v0_1_first_observation_failure.md), followed by a separately reviewed and frozen `deterministic-baseline-v0.2` plan.

## Stage 3B.1 deterministic baseline contract

- [Machine-readable experiment plan](configs/experiments/deterministic_baseline_v0.1.json)
- [Deterministic baseline plan](docs/stage_3b_deterministic_baseline_plan.md)
- [Matching protocol](docs/stage_3b_matching_protocol.md)

These documents freeze the development scope, supported predicates, matching rules, acceptance gates and future held-out controls before implementation. They contain no achieved extraction or performance result.

## Stage 3B.2 development-only gold access

Validate the access contract and print its deterministic non-semantic development summary:

~~~powershell
python -m document_intelligence.extraction.baseline_gold_cli --repository-root . --access development
~~~

The held-out form is documented as an expected rejection, not a routine command. It exits 1 because Stage 3B.2 has no baseline freeze-manifest bypass:

~~~powershell
python -m document_intelligence.extraction.baseline_gold_cli --repository-root . --access held_out
~~~

See the [development-only public-gold loader design](docs/stage_3b_development_gold_loader.md). The loader is for evaluation and failure-analysis tooling; the deterministic extractor receives only `ParsedDocument` input and does not import a gold loader.

## Stage 3B.3 deterministic candidate extraction

Run the source-independent deterministic rule engine over one existing `ParsedDocument` JSON file:

~~~powershell
python -m document_intelligence.extraction.deterministic_cli --input path/to/parsed_document.json --output path/to/candidate_result.json
~~~

The engine covers `action_status`, `budget`, `commitment`, `decision`, `metric`, `recommendation`, `requirement` and `risk`. It preserves exact bounded evidence and emits canonical deterministic JSON without a timestamp. It does not parse a raw source document, load gold labels, compute a metric or enable held-out access. See the [Stage 3B.3 deterministic rule-engine design](docs/stage_3b_deterministic_rule_engine.md).

## Stage 3B.4A strict development evaluator

The [Stage 3B.4A evaluator contract](docs/stage_3b_development_evaluator.md) implements the frozen protocol-v0.1 comparison, one-to-one matching and exact metric semantics before any development score is observed. It accepts already loaded development gold, precomputed successful or failed candidate attempts and explicit owner challenge assessments. It does not invoke the extractor, load files or provide a CLI for running the real benchmark.

Stage 3B.4A generated no metric. Stage 3B.4B `prepare` later recorded preliminary counts only in the immutable observation lock. The failed S004 attempt means the complete report and baseline freeze are unavailable; owner assessment is deliberately deferred rather than treated as the only remaining blocker.

## Stage 3B.4B development execution and freeze

The [two-checkpoint execution and freeze contract](docs/stage_3b_development_execution_and_freeze.md) separates first-score observation from project-owner challenge assessment.

`prepare` validates the frozen Stage 2 ingestion report, opens only S001, S002, S003, S004 and S006, runs deterministic extraction twice, preserves canonical primary/repeat hashes, performs strict diagnostics and writes the pending-owner-review artifacts. The first v0.1 execution preserved four reproducible outputs and both failed S004 attempts. It did not produce a complete evaluation report, final error analysis or baseline freeze manifest.

`finalize` reloads and verifies prepared evidence, requires successful repeat-identical attempts and three completed owner outcomes, and keeps held-out access explicitly blocked. It is implemented and tested, but v0.1 cannot satisfy its all-source gate and must not be finalized. See the [failed first-observation report](docs/stage_3b_v0_1_first_observation_failure.md).

## Stage 3A public annotation validation

Generate fresh ignored `ParsedDocument` JSON with the frozen Stage 2 batch command, then validate the frozen dataset:

~~~powershell
python -m document_intelligence.extraction.annotation_cli --parsed-root artifacts/annotations/public_gold_parsed --report artifacts/annotations/public_gold_validation_report.json --require-owner-verified
~~~

The command validates schemas, frozen split metadata, evidence blocks, page locators, excerpts, value types, counts and completed owner-review status. SHA-256 freeze tests protect both JSONL files. See the [Stage 3 design](docs/stage_3_extraction_design.md), [annotation guide](docs/public_gold_annotation_guide.md), [Stage 3A completion report](docs/stage_3a_completion_report.md), [freeze record](docs/public_gold_freeze.md), and [owner decision log](docs/public_gold_owner_decision_log.md). These controls do not provide an extraction result.

## Stage 2 document ingestion

Parse one supported local document through the installed command:

~~~powershell
ingest-document <file> --source-id <SOURCE_ID> --output <output.json>
~~~

or through the Python module:

~~~powershell
python -m document_intelligence.ingestion.cli <file> --source-id <SOURCE_ID> --output <output.json>
~~~

Run manifest-driven validation over a frozen split:

~~~powershell
python -m document_intelligence.ingestion.batch_cli --output-root <output-directory> --split all --parser-commit <PARSER_COMMIT> --run-type full_corpus_validation --report <report.json>
~~~

The output contains document and block records with page, slide, header, body, or quoted-history provenance. It does not contain extracted facts. See the [Stage 2 ingestion design](docs/stage_2_ingestion_design.md), [Stage 2A development validation](docs/stage_2a_development_validation.md), [Stage 2B held-out validation](docs/stage_2b_held_out_validation.md), and [Stage 2 acceptance report](docs/stage_2_acceptance_report.md).

## Stage 1B audit utility

The deterministic PDF audit utility records file integrity, page counts, and screening-level text-density warnings during local corpus review. It is not the production ingestion parser and does not perform OCR, licence decisions, or semantic extraction evaluation.

~~~powershell
audit-pdfs --input-dir data/raw --output artifacts/audits/pdf_audit.csv
~~~

Source files under data/raw and generated audit artefacts under artifacts/audits remain local and ignored by Git. See the [pilot utility validation](docs/stage_1b_audit_utility_validation.md) for observed Stage 1B results and limitations.

## Synthetic challenge corpus

The deterministic generator creates the committed PPTX and EML fixtures from fixed project-authored data:

~~~powershell
python scripts/generate_synthetic_corpus.py --output-root data/synthetic --force
~~~

See the [synthetic challenge-set specification](docs/synthetic_challenge_set_spec.md) and [synthetic data policy](docs/synthetic_data_policy.md) for family definitions, provisional splits, redistribution rules, and leakage controls.

## Stage 1 contract and freeze

- [Product definition](docs/product_definition.md)
- [Evidence-linked extraction schema](docs/extraction_schema.md)
- [Evaluation plan](docs/evaluation_plan.md)
- [End-to-end product example](docs/end_to_end_example.md)
- [Stage 1 corpus freeze](docs/corpus_freeze.md)
- [Stage 1 completion report](docs/stage_1_completion_report.md)

## Planned stages

1. **Stage 0 — Project Charter and Repo Setup**: **Completed.** Define the scope, architecture, decisions, packaging, and evaluation intent.
2. **Stage 1 – Corpus Audit**: **Completed.** Audited and froze the versioned public and synthetic corpus, family splits, ground truth, product contract, and evaluation gates.
3. **Stage 2 — Document Ingestion**: **Completed.** The Common Document Object, PDF/PPTX/EML parsers, single-document and batch CLIs, and full frozen-corpus validation are implemented.
4. **Stage 3 — Baseline and Structured Extraction**: **In progress: Stage 3B.4B-D failed-observation diagnosis and v0.2 transition.** Candidate contracts, frozen owner-reviewed `public-gold-v0.1`, guarded development-label access, v0.1 deterministic rules, strict evaluation semantics and the execution/freeze workflow are implemented. The first v0.1 observation preserved four reproducible outputs and one reproducible source failure; no accepted metric or freeze exists. A separately frozen v0.2 plan, complete development execution, owner challenge decisions, held-out execution, LLM extraction, reconciliation, conflict checks and measured review-routing results remain incomplete or planned.
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
