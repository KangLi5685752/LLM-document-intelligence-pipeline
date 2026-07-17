# Decision Log

All decisions below were accepted on 2026-07-16 for the Stage 0A foundation. They may be revisited when evidence from implementation or evaluation justifies a change.

## DEC-001: Final project title

- **Context:** The portfolio needs a title that communicates both document processing and trustworthy knowledge extraction.
- **Alternatives:** Document AI Pipeline; Enterprise Knowledge RAG; LLM Document Intelligence & Knowledge Extraction Pipeline.
- **Chosen option:** LLM Document Intelligence & Knowledge Extraction Pipeline.
- **Reason:** It describes the core extraction problem without reducing the project to retrieval or implying a production product.
- **Trade-off:** The title is long and includes LLM even though a non-LLM baseline will also be evaluated.

## DEC-002: Repository name

- **Context:** The GitHub repository and portfolio need a stable display convention that remains distinct from Python packaging and import conventions.
- **Alternatives:** document-ai-pipeline; llm-document-intelligence-pipeline; LLM-document-intelligence-pipeline.
- **Chosen option:** Use LLM-document-intelligence-pipeline as the exact GitHub repository and portfolio display name. Keep llm-document-intelligence-pipeline as the Python distribution name and document_intelligence as the Python import package.
- **Reason:** Uppercase “LLM” is the chosen GitHub and portfolio display convention, while the lowercase distribution and snake-case import names follow their respective Python conventions.
- **Trade-off:** Contributors must preserve three related naming forms and use the correct form for each context.

## DEC-003: Replace the standalone RAG project

- **Context:** A standalone RAG project would overlap with common portfolio examples and could overemphasise retrieval before document quality is established.
- **Alternatives:** Keep both projects; retain only standalone RAG; replace standalone RAG with document intelligence.
- **Chosen option:** This project replaces the previously planned standalone RAG project.
- **Reason:** The broader document-intelligence scope demonstrates parsing, structured extraction, validation, evidence, review routing, and evaluation before retrieval.
- **Trade-off:** A dedicated RAG demonstration is deferred and may only appear as a later, grounded extension.

## DEC-004: Separate the project from the recommendation dissertation

- **Context:** The portfolio includes a recommendation-system dissertation with a different research question and evaluation target.
- **Alternatives:** Merge document features into the recommender; share one end-to-end product; maintain separate projects.
- **Chosen option:** Maintain this project independently from the recommendation dissertation.
- **Reason:** The recommender asks what products should be recommended and why; this project asks how heterogeneous documents become validated, traceable, queryable knowledge.
- **Trade-off:** Separate repositories require separate narratives, datasets, and maintenance.

## DEC-005: Develop local-first

- **Context:** Early work needs fast iteration, inspectable outputs, low cost, and reproducible evaluation.
- **Alternatives:** Cloud-first; managed-platform prototype; local-first with later deployment decisions.
- **Chosen option:** Use local-first development.
- **Reason:** It keeps Stage 1-3 work focused on data contracts, extraction quality, and evidence rather than infrastructure.
- **Trade-off:** Cloud-specific integration and scalability risks will be tested later.

## DEC-006: Evaluate before RAG and cloud work

- **Context:** Retrieval and deployment can make a prototype look complete without demonstrating that extracted knowledge is accurate or supported.
- **Alternatives:** Build an end-to-end demo first; develop all layers in parallel; complete extraction evaluation before RAG and cloud.
- **Chosen option:** Prioritise evaluation before grounded RAG, BigQuery, or Cloud Run implementation.
- **Reason:** Downstream features should consume validated, evidence-linked data and be justified by measured needs.
- **Trade-off:** The project will have a less visually complete demo during its early stages.

## DEC-007: Choose PDF, PPTX, and email-style text as MVP formats

- **Context:** The project needs heterogeneous formats that expose page, slide, and section-level evidence challenges while remaining achievable.
- **Alternatives:** PDF only; office formats broadly; PDF, PPTX, and email-style text.
- **Chosen option:** Use PDF, PPTX, and email-style text for the MVP.
- **Reason:** These formats are common in project work and provide meaningful structural variation without requiring every document type.
- **Trade-off:** Supporting three formats increases parser and evaluation complexity compared with a PDF-only MVP.

## DEC-008: Exclude OCR from the MVP

- **Context:** Scanned documents introduce image processing, OCR quality, layout recovery, and additional evaluation requirements.
- **Alternatives:** Require OCR from the start; use a managed OCR service; limit the MVP to digitally extractable content.
- **Chosen option:** Exclude OCR and scanned-document support from the MVP.
- **Reason:** This keeps the first evaluation focused on extraction, validation, evidence alignment, and ambiguity handling.
- **Trade-off:** The MVP will not cover an important class of real-world documents.

## DEC-009: Use one future LLM provider

- **Context:** Provider abstraction and multi-model comparisons add integration effort before the core evaluation design is proven.
- **Alternatives:** Provider-agnostic framework; multiple-provider benchmark; one provider behind a narrow future interface.
- **Chosen option:** Integrate at most one LLM provider in a future stage, while retaining a separate mock mode for local tests.
- **Reason:** It limits cost and configuration complexity and keeps evaluation centred on the document-intelligence workflow.
- **Trade-off:** Results may be provider-specific and portability will remain unproven.

## DEC-010: Use public and synthetic data only

- **Context:** Portfolio work must be reproducible and must not expose private, client, employer, or dissertation data.
- **Alternatives:** Private operational documents; proprietary benchmark data; public documents plus synthetic edge cases.
- **Chosen option:** Use appropriately licensed public documents and clearly labelled synthetic edge cases only.
- **Reason:** This supports safe sharing, reproducibility, and deliberate testing of ambiguity, conflicts, and unsupported claims.
- **Trade-off:** Synthetic cases may not capture the full messiness of confidential enterprise collections, and public data may introduce domain bias.
