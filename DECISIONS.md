# Decision Log

DEC-001 to DEC-010 were accepted on 2026-07-16 for the Stage 0A foundation. Stage 1A decisions DEC-011 to DEC-015 were accepted on 2026-07-17. Stage 1B decisions DEC-016 and DEC-017 were accepted on 2026-07-18. Stage 1B synthetic-corpus decisions DEC-018 to DEC-020 and Stage 1 completion decisions DEC-021 to DEC-025 were accepted on 2026-07-20. Stage 2A ingestion decisions DEC-026 to DEC-030 and Stage 2B validation decisions DEC-031 to DEC-034 were accepted on 2026-07-21. They may be revisited when evidence from source review, implementation, or evaluation justifies a change.

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

## DEC-018: Commit project-created synthetic fixtures

- **Context:** The PPTX and EML challenge files are created specifically for this project and need to support reproducible tests and inspectable portfolio evidence.
- **Alternatives:** Generate fixtures only at test time; store fixtures outside the repository; commit the project-created synthetic files.
- **Chosen option:** Commit the project-created synthetic PPTX and EML fixtures.
- **Reason:** The fixtures are safe to redistribute, make tests reproducible, and allow portfolio reviewers to inspect the challenge documents directly.
- **Trade-off:** Binary PPTX files increase repository size slightly.

## DEC-019: Use family-level split assignments

- **Context:** Email threads, quoted history, repeated facts, and multiple documents from one scenario can leak information when related sources are separated.
- **Alternatives:** Split sources independently; assign complete document families to one split; omit held-out synthetic sources.
- **Chosen option:** Assign every member of a synthetic document family to the same development or held-out split.
- **Reason:** Family-level assignment prevents quoted-history, duplicated-fact, and same-scenario leakage.
- **Trade-off:** The held-out set is small.

## DEC-020: Use no external assets in synthetic PPTX

- **Context:** External images, logos, and templates would add rights uncertainty and could make deterministic regeneration dependent on unavailable files.
- **Alternatives:** Use downloaded corporate-style assets; embed third-party templates; build the fixtures only from project-authored text and vector objects.
- **Chosen option:** Use no external assets in synthetic PPTX files.
- **Reason:** This removes third-party rights uncertainty and keeps generation reproducible.
- **Trade-off:** Visual realism is lower than in externally designed corporate decks.

## DEC-021: Generic evidence-linked fact contract with derived initiative views

- **Context:** The frozen corpus contains project, policy, research, governance, guidance, and programme sources that must share an evaluable output contract.
- **Alternatives:** Use a project-only schema; define an unrestricted enterprise ontology; use a generic evidence-linked fact contract with bounded derived views.
- **Chosen option:** Use one generic evidence-linked `FactRecord` and `ConflictRecord` model for policy, research, governance, and project sources. Produce initiative summaries only as derived views.
- **Reason:** A project-only schema would not represent the public-PDF corpus, while a completely unrestricted ontology would make evaluation unmanageable.
- **Trade-off:** The generic fact model requires careful predicate and normalization rules.

## DEC-022: Freeze corpus v1.0 at 15 active sources

- **Context:** Stage 2 needs stable source membership, hashes, families, and splits before parser implementation begins.
- **Alternatives:** Keep adding sources during ingestion; freeze only the synthetic corpus; freeze the reviewed active corpus.
- **Chosen option:** Freeze S001-S007 and S010-S017 with the assignments in `corpus_split.csv`.
- **Reason:** The corpus now covers realistic PDFs, controlled PPTX and EML challenges, development and held-out cases, and exact synthetic ground truth.
- **Trade-off:** The corpus remains small and does not represent enterprise-scale diversity.

## DEC-023: Use family-level development and held-out splits

- **Context:** Related documents and complete email threads repeat language, facts, and quoted history.
- **Alternatives:** Split individual sources independently; use one development-only corpus; keep related documents and complete threads within one split.
- **Chosen option:** Keep related documents and complete email threads within one split.
- **Reason:** This prevents repeated text, quoted history, and related-document facts from leaking across development and held-out evaluation.
- **Trade-off:** The number of independent held-out families is small.

## DEC-024: Treat held-out evaluation as procedural rather than blind

- **Context:** The repository is public and the project uses a single-developer workflow, so a truly secret benchmark is not possible.
- **Alternatives:** Claim a blind benchmark; use no held-out set; document procedural held-out controls and prohibit source-specific tuning.
- **Chosen option:** Document that the public repository and single-developer workflow make a truly secret benchmark impossible, while prohibiting held-out-specific tuning.
- **Reason:** This is more honest than claiming blind evaluation.
- **Trade-off:** Results may still contain implicit familiarity bias.

## DEC-025: Fix evaluation gates before extraction experiments

- **Context:** Extraction metrics and thresholds chosen after experiments could reward observed behavior rather than test the intended product contract.
- **Alternatives:** Select metrics after implementation; report only qualitative examples; define acceptance gates before extraction experiments.
- **Chosen option:** Use `docs/evaluation_plan.md` as the pre-experiment acceptance contract.
- **Reason:** This prevents retrospective metric selection and unsupported claims.
- **Trade-off:** Thresholds may later require a versioned revision if the corpus proves materially harder than expected.

## DEC-026: Use Pydantic v2 for the Common Document Object

- **Context:** Format-specific parsers need one explicit, versioned, JSON-serialisable boundary that rejects invalid and unexpected data.
- **Alternatives:** Plain dictionaries; standard-library dataclasses with manual validation; Pydantic v2 models.
- **Chosen option:** Use Pydantic v2 for the Common Document Object.
- **Reason:** It provides strict field validation, an explicit JSON contract, nested model validation, and future schema generation.
- **Trade-off:** It adds a runtime dependency, and validation models require version discipline.

## DEC-027: Use page-level PDF blocks for the initial parser

- **Context:** PDF text extraction can expose uncertain reading order, columns, and tables that the initial ingestion layer cannot reliably reconstruct.
- **Alternatives:** One block per document; heuristic paragraph or table reconstruction; one ordered text block per page.
- **Chosen option:** Emit one page-text block per PDF page for Stage 2A.
- **Reason:** Page blocks provide stable provenance, avoid pretending to reconstruct columns or tables, and support later segmentation without losing page identity.
- **Trade-off:** Page blocks may be too coarse for extraction.

## DEC-028: Preserve PPTX shape and table blocks without semantic reconstruction

- **Context:** Slides combine positioned text, tables, charts, diagrams, pictures, and decorative objects whose semantic relationships are not always explicit.
- **Alternatives:** Flatten each slide to one text string; infer complete visual meaning; preserve supported shapes and tables with positions.
- **Chosen option:** Preserve slide titles, text shapes, and direct table structures with slide and element provenance, without interpreting unsupported visual objects.
- **Reason:** This retains visible structure and slide-level provenance without making unsupported chart or diagram claims.
- **Trade-off:** Reading order remains an approximation, and SmartArt and charts are not interpreted.

## DEC-029: Separate current EML body from quoted history

- **Context:** Replies and forwards commonly repeat earlier values that later processing must not mistake for the latest assertion.
- **Alternatives:** Treat the whole message as current content; discard all history; preserve current body and quoted history as separate blocks.
- **Chosen option:** Separate the current EML body from recognized quoted or forwarded history.
- **Reason:** Later reconciliation must not treat quoted stale values as latest assertions.
- **Trade-off:** Separator-based detection cannot cover every email client format.

## DEC-030: Keep Stage 2A content tests development-only

- **Context:** Frozen held-out sources must not shape content-specific parser behavior before the initial parser version is fixed.
- **Alternatives:** Assert content across all sources immediately; avoid committed-source tests; use development fixtures for Stage 2A content assertions.
- **Chosen option:** Limit Stage 2A content assertions to S010 and S012-S014, alongside temporary format fixtures.
- **Reason:** This prevents held-out values from shaping content-specific parser rules before the parser version is frozen.
- **Trade-off:** Some format-general failures will only appear in Stage 2B.

## DEC-031: Use manifest-driven batch ingestion

- **Context:** Full-corpus validation must use frozen membership, filenames, formats, families, splits, and checksums without embedding source-specific rules in code.
- **Alternatives:** Maintain a hard-coded source list; discover arbitrary files from directories; join the source register and corpus-split manifest.
- **Chosen option:** Drive batch ingestion from the joined frozen source register and corpus-split manifest, with caller-supplied raw, synthetic, and output roots.
- **Reason:** This preserves manifest order and corpus controls while keeping path resolution format-based and reproducible.
- **Trade-off:** Batch runs depend on consistent manifests and correctly prepared local source roots.

## DEC-032: Isolate failures per source

- **Context:** One malformed, missing, or checksum-mismatched source must not hide the outcomes for the rest of the frozen corpus.
- **Alternatives:** Abort on the first error; retry every error indefinitely; record each item independently and complete the report.
- **Chosen option:** Isolate parser, checksum, input, output, and validation failures per source and return a complete batch report.
- **Reason:** A complete report supports an explicit failure taxonomy and prevents one source from crashing the batch.
- **Trade-off:** Callers must inspect the batch exit code and item-level failures rather than assuming report creation means success.

## DEC-033: Preserve first held-out run evidence

- **Context:** Replacing the first held-out report after parser changes would conceal whether the frozen parser initially generalized.
- **Alternatives:** Keep only the latest run; overwrite failed runs after fixes; preserve the first report and write any later run separately.
- **Chosen option:** Preserve the first held-out report and use different output paths for any after-fix rerun.
- **Reason:** This keeps the sequence of evidence auditable and prevents retrospective presentation of a corrected run as the original result.
- **Trade-off:** Local validation artifacts require clearer naming and additional storage.

## DEC-034: Prohibit held-out-specific parser tuning

- **Context:** Held-out document values or filenames could otherwise influence rules and weaken the generalization claim.
- **Alternatives:** Tune directly to every held-out failure; prohibit all post-held-out fixes; allow only documented format-general fixes with temporary regression fixtures.
- **Chosen option:** Prohibit source-ID, filename, expected-value, and held-out-keyword rules; permit only documented format-general parser fixes.
- **Reason:** This preserves the purpose of the frozen held-out split while allowing legitimate general parser defects to be corrected transparently.
- **Trade-off:** Some unsupported held-out cases may remain documented limitations instead of being made to pass.

## DEC-035: Separate candidate extraction from final reconciliation

- **Context:** A source-level extraction can propose a fact without establishing whether it is current, superseded, duplicated, or in conflict with another source.
- **Alternatives:** Assign final states during extraction; represent all outputs as final facts; preserve candidates in a separate pre-reconciliation contract.
- **Chosen option:** Use `CandidateExtractionResult` for source-level candidates and reserve final states for a later reconciliation layer.
- **Reason:** This prevents extraction confidence, source order, or recency from silently deciding authority.
- **Trade-off:** Later processing must explicitly transform candidates into reconciled knowledge records.

## DEC-036: Use a bounded predicate vocabulary v0.1

- **Context:** Unrestricted predicate creation would make labels, deterministic rules, and future LLM outputs difficult to compare.
- **Alternatives:** Allow arbitrary strings; adopt a broad external ontology immediately; define a small versioned vocabulary with declared aliases and qualifiers.
- **Chosen option:** Use exactly 20 canonical predicates in vocabulary v0.1 and reject unknown names.
- **Reason:** A bounded registry makes annotation and later extraction evaluation reproducible without pretending to define a complete enterprise ontology.
- **Trade-off:** New relationships require an explicit versioned vocabulary change.

## DEC-037: Treat public annotations as AI-assisted drafts until owner review

- **Context:** Local source inspection and structural validation do not provide independent semantic approval.
- **Alternatives:** Label AI-assisted records as verified; omit review status; retain draft status until the project owner records a decision.
- **Chosen option:** Initialize every public fact and challenge case as `draft_ai_assisted` and require documented owner review before approval.
- **Reason:** This makes single-annotator and AI-assistance limitations visible and prevents fabricated verification claims.
- **Trade-off:** Public-gold extraction results cannot be claimed until review and correction are complete.

## DEC-038: Preserve procedural held-out labels but prohibit their use in tuning

- **Context:** The public repository cannot keep S005 and S007 labels secret, yet a held-out procedure is still useful for separating rule design from final evaluation.
- **Alternatives:** Omit held-out labels; claim a blind benchmark; publish labels while prohibiting their use in predicate, rule, or prompt tuning.
- **Chosen option:** Commit and structurally validate held-out labels, but exclude their values from extractor design and freeze development behavior before later held-out evaluation.
- **Reason:** This is transparent about visibility while preserving a reproducible procedural boundary.
- **Trade-off:** Familiarity bias cannot be eliminated in a public single-developer workflow.

## DEC-039: Require evidence block and page validation for every public fact

- **Context:** A page citation alone does not prove that an annotation points to the exact parsed evidence later extractors will receive.
- **Alternatives:** Store only page numbers; store free-text excerpts without referential checks; validate block ID, page, excerpt, source, family, and split.
- **Chosen option:** Require every public fact to reference an existing PDF `PAGE_TEXT` block whose page matches and whose normalized text contains the excerpt.
- **Reason:** This makes the annotation-to-ingestion boundary deterministic and catches stale or mistyped evidence links before experiments.
- **Trade-off:** Parser-version changes may require explicit annotation migration even when the source fact is unchanged.

## DEC-040: Enforce predicate usage in runtime models

- **Context:** Normalizing a registered predicate name did not prevent an incompatible subject type, value type, missing required qualifier, or undeclared qualifier from entering a candidate or gold annotation.
- **Alternatives:** Validate only during dataset reporting; duplicate checks in each model; centralize the vocabulary constraints in one runtime function used by both models.
- **Chosen option:** Use `validate_predicate_usage` from both `CandidateFact` and `GoldFactAnnotation`.
- **Reason:** One source-independent contract prevents production candidates and evaluation labels from accepting different predicate semantics.
- **Trade-off:** Existing records must satisfy newly enforced qualifier and type constraints when loaded.

## DEC-041: Require structured qualifiers for metrics

- **Context:** A numeric value without its measure, unit, population, or period can compare unlike observations and obscure the source denominator.
- **Alternatives:** Encode context in subject text only; allow unstructured notes; require a stable metric name and retain other source-supported context in predicate-scoped qualifiers.
- **Chosen option:** Require `metric_name` for every metric and use `unit`, `population`, and `period` when supported by the source.
- **Reason:** Structured context makes later matching and evaluation explicit without inventing a broader ontology.
- **Trade-off:** Annotation review must verify both the numeric normalization and its qualifiers.

## DEC-042: Reject false day-level precision from month-level deadlines

- **Context:** A phrase bounded to the end of a month does not state a specific calendar day, even when that month's last day can be calculated.
- **Alternatives:** Normalize to the final calendar day; store an exact date with a warning; preserve only the precision supported by the source or exclude the ambiguous normalization.
- **Chosen option:** Do not create an exact `YYYY-MM-DD` value from month-level deadline wording unless the source states the day.
- **Reason:** Computable calendar detail is not source evidence and would create false precision in the gold set.
- **Trade-off:** Some date-like phrases cannot participate in exact-date matching without a precision-aware future model.

## DEC-043: Expand owner review from the sample to all 35 facts

- **Context:** Review of the ten-record sample exposed subject-attribution and date-normalization defects that structural checks could not detect.
- **Alternatives:** Retain sample-only review; treat corrected samples as sufficient; provide a deterministic checklist for every annotation.
- **Chosen option:** Keep the sample for convenience and require owner review through a full 35-record worksheet before approval.
- **Reason:** Every draft needs semantic scrutiny before the dataset can be frozen as public gold.
- **Trade-off:** Approval requires more manual review effort before extraction experiments begin.
