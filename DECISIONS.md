# Decision Log

DEC-001 to DEC-010 were accepted on 2026-07-16 for the Stage 0A foundation. Stage 1A decisions DEC-011 to DEC-015 were accepted on 2026-07-17. Stage 1B decisions DEC-016 and DEC-017 were accepted on 2026-07-18. They may be revisited when evidence from source review, implementation, or evaluation justifies a change.

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

## DEC-011: Focus the corpus on UK public-sector AI

- **Context:** Stage 1 needs a coherent domain that contains strategies, programmes, governance, adoption research, and evaluations relevant to the planned extraction schema.
- **Alternatives:** Mix unrelated public-sector domains; use private enterprise documents; focus on UK public-sector AI initiatives, adoption, evaluation, and governance.
- **Chosen option:** Use UK public-sector AI as the primary corpus domain.
- **Reason:** It offers traceable public sources and recurring project-intelligence concepts while keeping the evaluation narrative coherent.
- **Trade-off:** Findings may reflect UK institutions and AI policy language rather than generalising to every sector or jurisdiction.

## DEC-012: Use public PDFs as the primary real-document source

- **Context:** The real corpus needs stable evidence locations and a format that is common across the selected domain.
- **Alternatives:** Give PDF, PPTX, email, and HTML equal priority; use HTML first; use public PDFs as the primary real source with controlled tests for other formats.
- **Chosen option:** Use public PDFs as the primary real-document source for the MVP.
- **Reason:** PDFs are common in official publication workflows and provide page-level evidence boundaries for later evaluation.
- **Trade-off:** PDF layout complexity remains significant, and the real corpus will initially underrepresent slide and message formats.

## DEC-013: Keep original public source files local by default

- **Context:** Public accessibility does not by itself settle redistribution rights, third-party content, personal-data risk, repository size, or source-version changes.
- **Alternatives:** Commit every public file; commit files unless a restriction is found; keep originals local unless redistribution is explicitly approved.
- **Chosen option:** Store original source files locally by default and commit only metadata and URLs until a source-specific redistribution review approves otherwise.
- **Reason:** This reduces legal and data-governance risk while preserving a traceable route back to the publisher.
- **Trade-off:** Contributors must acquire approved files independently, so reproducibility depends on stable sources, checksums, and clear acquisition records.

## DEC-014: Do not force inclusion of unrelated PPTX files

- **Context:** PPTX is a planned MVP format, but convenient public slide decks may not match the corpus domain or extraction schema.
- **Alternatives:** Include any available PPTX; omit PPTX entirely; use relevant public PPTX when reviewable and synthetic PPTX for controlled format testing.
- **Chosen option:** Do not add unrelated PPTX files solely to create format diversity; use relevant public or clearly labelled synthetic PPTX when justified.
- **Reason:** Domain coherence and controlled test design are more valuable than an arbitrary format quota.
- **Trade-off:** Real-world PPTX coverage may remain limited until suitable sources are found.

## DEC-015: Defer HTML sources until explicitly supported

- **Context:** Some relevant evaluations are available primarily as HTML, while the current MVP ingestion scope does not include HTML.
- **Alternatives:** Add HTML ingestion now; convert HTML manually and treat it as another format; record relevant HTML sources but defer their use.
- **Chosen option:** Register relevant HTML sources as deferred until HTML ingestion is explicitly added and evaluated.
- **Reason:** This preserves useful source leads without expanding implementation scope or implying unsupported ingestion capability.
- **Trade-off:** Relevant project-evaluation evidence may be absent from the initial corpus.

## DEC-016: Pilot S001–S003 before the remaining PDF candidates

- **Context:** The manual audit method should be tested on a bounded set before it is applied to all candidate PDFs, including substantially longer documents.
- **Alternatives:** Audit all PDF candidates together; start with the longest or most complex files; pilot S001–S003 as one related document family.
- **Chosen option:** Audit S001–S003 as the Stage 1B pilot before reviewing the remaining PDF candidates.
- **Reason:** The three-source pilot is a small, related document family that can validate the audit method before longer-file review and support later strategy, government-response, and progress-report comparisons.
- **Trade-off:** The first pilot is concentrated on one publisher and topic, so it will not expose the full range of corpus variation.

## DEC-017: Keep related document families in the same evaluation split

- **Context:** Closely related strategies, responses, updates, and progress reports may repeat facts or language across documents.
- **Alternatives:** Split documents independently at random; keep each related family in one split; exclude related documents from evaluation.
- **Chosen option:** Assign all members of a related document family to the same future development or held-out evaluation split.
- **Reason:** Family-level grouping reduces cross-document information leakage and makes held-out evaluation more credible.
- **Trade-off:** Fewer independent document groups may be available for each split, which can limit balancing options.
