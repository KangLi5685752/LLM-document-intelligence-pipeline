# Decision Log

DEC-001 to DEC-010 were accepted on 2026-07-16 for the Stage 0A foundation. Stage 1A decisions DEC-011 to DEC-015 were accepted on 2026-07-17. Stage 1B decisions DEC-016 and DEC-017 were accepted on 2026-07-18. Stage 1B synthetic-corpus decisions DEC-018 to DEC-020 and Stage 1 completion decisions DEC-021 to DEC-025 were accepted on 2026-07-20. Stage 2A ingestion decisions DEC-026 to DEC-030 and Stage 2B validation decisions DEC-031 to DEC-034 were accepted on 2026-07-21. Stage 3A decisions DEC-035 to DEC-048 were accepted on 2026-07-23. Stage 3B.1 deterministic-baseline planning decisions DEC-049 to DEC-054 and Stage 3B.2 access-control decisions DEC-055 to DEC-057 were accepted on 2026-07-24. Stage 3B.3 deterministic-rule decisions DEC-058 to DEC-061 and Stage 3B.4A evaluator decisions DEC-062 to DEC-065 were accepted on 2026-07-25. Stage 3B.4B execution and failed-observation decisions DEC-066 to DEC-072 and Stage 3B.4C v0.2 planning decisions DEC-073 to DEC-078 were accepted on 2026-07-26. Stage 3B continuation, owner review, finalization and closure decisions DEC-079 through DEC-095 were accepted through 2026-08-02. Stage 4A planning decisions DEC-096 through DEC-099 were accepted on 2026-08-03. They may be revisited when evidence from source review, implementation, or evaluation justifies a change.

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

## DEC-044: Freeze public-gold-v0.1 with content hashes

- **Context:** Stage 3B needs a stable evaluation asset whose exact annotation content can be verified before experiments.
- **Alternatives:** Rely on version control alone; record counts without content identity; freeze both JSONL files with SHA-256 hashes in a versioned manifest.
- **Chosen option:** Freeze `public-gold-v0.1` with uppercase SHA-256 hashes for the fact and challenge-case JSONL files.
- **Reason:** Content hashes make accidental or unversioned changes fail deterministically.
- **Trade-off:** Any permitted frozen-file change requires coordinated manifest and version maintenance.

## DEC-045: Require a new dataset version for semantic label changes

- **Context:** Silent changes to labels, evidence, review decisions, splits, or schema meaning would make experiment results incomparable.
- **Alternatives:** Edit the frozen version in place; track only major changes; require a new dataset version for semantic changes.
- **Chosen option:** Require a new dataset version for any semantic annotation, challenge-case, evidence, review, distribution, split, schema, or predicate-meaning change.
- **Reason:** Versioned changes preserve the interpretation and reproducibility of results produced against `public-gold-v0.1`.
- **Trade-off:** Even small semantic corrections require a deliberate versioning and revalidation cycle.

## DEC-046: Separate owner semantic verification from AI-assisted drafting

- **Context:** AI assistance produced the initial drafts, while semantic approval required project-owner comparison with original PDF pages and frozen parsed evidence.
- **Alternatives:** Treat drafting as verification; replace the original annotation method; record drafting method and owner review status separately.
- **Chosen option:** Preserve `annotation_method` and record project-owner semantic verification independently through `review_status` and owner notes.
- **Reason:** This distinguishes provenance from approval without implying independent double annotation or inter-annotator agreement.
- **Trade-off:** Consumers must interpret both annotation method and review status.

## DEC-047: Prohibit held-out label loading during deterministic rule design

- **Context:** Public held-out labels are visible in the repository, so programmatic access during rule design would weaken the procedural evaluation boundary.
- **Alternatives:** Load all labels during development; hide labels outside the repository; enforce development-only loading until code and rules are frozen.
- **Chosen option:** Prohibit loading held-out fact and challenge-case labels during deterministic rule design, rule tests, and tuning.
- **Reason:** Development-only access preserves the strongest practical held-out control available in a public single-developer project.
- **Trade-off:** The control is procedural and cannot eliminate prior familiarity with public labels.

## DEC-048: Freeze challenge cases with the evaluation asset

- **Context:** Ambiguous, unsupported, and missing-value cases define required abstention and review behavior alongside positive facts.
- **Alternatives:** Keep challenge cases as informal documentation; version them separately; include them in the same frozen evaluation asset.
- **Chosen option:** Treat the six owner-verified challenge cases as part of `public-gold-v0.1` and protect their JSONL content with the freeze manifest.
- **Reason:** Negative and ambiguous behavior is part of the evaluation contract and must remain reproducible with the fact labels.
- **Trade-off:** Challenge-case corrections follow the same dataset-version discipline as fact annotations.

## DEC-049: Freeze the deterministic baseline plan before implementation

- **Context:** Writing extraction rules before fixing the experiment inputs, metrics, matching rules and access boundary would allow the evaluation contract to drift in response to observed behaviour.
- **Alternatives:** Define the plan during implementation; document the experiment after development; freeze the complete experiment contract before writing extraction rules.
- **Chosen option:** Freeze `deterministic-baseline-v0.1`, its inputs, metrics, matching and access policy before writing extraction rules.
- **Reason:** A pre-implementation contract makes later development and evaluation reproducible and exposes deviations explicitly.
- **Trade-off:** Implementation must follow a deliberately bounded contract or declare a new experiment version.

## DEC-050: Score baseline v0.1 on owner-reviewed public PDF candidates

- **Context:** The project contains owner-reviewed public-PDF candidate labels and synthetic records intended to test later cross-document states, formats and conflicts.
- **Alternatives:** Score public and synthetic records together; use synthetic records as the primary baseline score; score public candidates and reserve synthetic records for bounded smoke tests until reconciliation evaluation is defined.
- **Chosen option:** Use the 25 development public facts as the primary scored baseline dataset. Use development synthetic documents only for non-scored format and contract smoke tests until candidate and reconciliation ground truth are evaluated separately.
- **Reason:** Public documents test realistic candidate extraction while keeping synthetic current, superseded and conflict semantics out of candidate-only F1.
- **Trade-off:** Initial scores cover a small PDF-focused development set and do not yet measure PPTX/EML reconciliation behaviour.

## DEC-051: Limit baseline v0.1 to eight development-supported predicates

- **Context:** The predicate registry is broader than the predicates supported by the frozen development annotations and the first deterministic rule families.
- **Alternatives:** Attempt all 20 predicates; allow rules to create new predicates; scope the first baseline to predicates supported by development evidence.
- **Chosen option:** Support `action_status`, `budget`, `commitment`, `decision`, `metric`, `recommendation`, `requirement` and `risk` in the first deterministic baseline. This does not change the 20-predicate vocabulary.
- **Reason:** A fixed supported subset prevents silent invention and makes false positives and omissions interpretable.
- **Trade-off:** Registered predicates outside the eight-predicate subset are not evaluated in baseline v0.1.

## DEC-052: Use strict reproducible matching before fuzzy matching

- **Context:** Semantic or fuzzy matching can grant useful credit but introduces thresholds, model dependencies and harder-to-audit pairings in a small first benchmark.
- **Alternatives:** Use embedding similarity; use fuzzy subject aliases and numeric tolerances; start with exact typed, normalized and source-bounded one-to-one matching.
- **Chosen option:** Use exact typed, normalized, source-bounded one-to-one matching in v0.1, with no embeddings, fuzzy subject matching or external entity resolution.
- **Reason:** Strict matching produces transparent counts, deterministic duplicate handling and reproducible failure analysis.
- **Trade-off:** Semantically equivalent wording may be under-credited until a separately versioned matching approach is justified.

## DEC-053: Treat deterministic confidence as a heuristic rule-strength band

- **Context:** Deterministic rules can express evidence strength, but the small development set cannot support probability calibration.
- **Alternatives:** Omit confidence; estimate calibrated probabilities; use fixed, explicitly heuristic strength bands.
- **Chosen option:** Use fixed `0.90`, `0.70` and `0.50` bands, explicitly not calibrated probabilities.
- **Reason:** Fixed bands distinguish explicit, bounded-context and ambiguous candidates without making a statistical calibration claim.
- **Trade-off:** Confidence values support routing and analysis only and must not be interpreted as empirical likelihoods.

## DEC-054: Fail closed on held-out access until baseline freeze

- **Context:** Held-out labels are committed in a public repository, so loader behaviour must provide the enforceable procedural boundary before the first evaluation.
- **Alternatives:** Trust callers not to load held-out records; remove held-out labels from the repository; block held-out semantics by default and require a frozen experiment record for later access.
- **Chosen option:** Development code must not return held-out fact or challenge-case semantics. Held-out access will later require an explicit flag and a valid baseline freeze manifest.
- **Reason:** A fail-closed loader reduces accidental leakage and makes the first held-out run contingent on recorded code, rules and development results.
- **Trade-off:** The control remains procedural and future evaluation requires additional manifest validation and explicit access handling.

## DEC-055: Use a dedicated baseline gold access boundary

- **Context:** The Stage 3A loaders intentionally deserialize the complete public-gold dataset for structural and freeze validation, while deterministic-baseline development must not receive held-out semantics.
- **Alternatives:** Reuse the complete loaders and filter after deserialization; add an optional bypass to the existing loaders; retain complete validation loaders and introduce a separate development-only API.
- **Chosen option:** Keep complete Stage 3A loaders for dataset validation, but require baseline evaluation code to use a separate development-only API.
- **Reason:** A dedicated API makes the narrower access policy explicit, testable and fail closed without weakening complete-dataset validation.
- **Trade-off:** Two loader purposes must remain clearly documented, and future extractor code must not import either gold-loading path.

## DEC-056: Route by metadata before semantic deserialisation

- **Context:** Integrity verification requires reading the frozen files, but constructing held-out semantic objects during development would violate the experiment access boundary.
- **Alternatives:** Deserialize every record and filter afterward; store a separate development copy; verify hashes, route on bounded metadata and deserialize development semantics only.
- **Chosen option:** Verify hashes, inspect ID/source/split metadata and semantically deserialize only development records. Held-out bytes are still read for integrity hashing and metadata routing.
- **Reason:** Metadata-first routing preserves one checksummed dataset while preventing held-out values, evidence and notes from entering semantic development objects.
- **Trade-off:** The control is procedural rather than secret, and the metadata scanner requires its own strict validation and regression tests.

## DEC-057: Deny held-out access before repository I/O

- **Context:** Stage 3B.2 has no implemented baseline freeze-manifest schema or validator that could authorize the first held-out run.
- **Alternatives:** Accept a placeholder manifest; rely on an environment variable or boolean flag; reject held-out mode before repository access until the authorization contract exists.
- **Chosen option:** Stage 3B.2 rejects held-out mode before opening files and provides no bypass until the versioned baseline freeze manifest and validator are implemented.
- **Reason:** Immediate denial avoids accidental reads through partially implemented authorization logic and makes the missing future gate explicit.
- **Trade-off:** Held-out evaluation is intentionally impossible through this API until a separate reviewed implementation is completed.

## DEC-058: Keep deterministic extraction as a pure ParsedDocument transform

- **Context:** The deterministic baseline must be evaluated against labels without allowing those labels, raw source files or repository layout to influence runtime extraction.
- **Alternatives:** Let the extractor open parser outputs and labels itself; pass file paths plus optional evaluation context; accept one validated `ParsedDocument` and perform a pure in-memory transform.
- **Chosen option:** The rule engine accepts a `ParsedDocument` object and performs no file, network or gold-label access.
- **Reason:** A narrow typed boundary keeps extraction independent from evaluation data, prevents path and filename conditions, and makes I/O isolation directly testable.
- **Trade-off:** Callers must load and validate `ParsedDocument` data before invoking the API, and the extractor cannot recover information absent from that object.

## DEC-059: Prefer conservative bounded rules and explicit abstention

- **Context:** Page-level text and flattened layouts can make subject, value and evidence relationships uncertain, while unsupported extraction is more damaging than an explicit miss in this transparent baseline.
- **Alternatives:** Join nearby blocks heuristically; emit low-confidence candidates for every trigger; require subject, trigger, value and evidence to remain bounded and otherwise review or abstain.
- **Chosen option:** Emit only when subject, trigger, value and evidence are bounded within one block; otherwise route to review or abstain.
- **Reason:** Same-block boundaries and stable warning codes expose uncertainty without fabricating cross-page context, missing subjects, values or precision.
- **Trade-off:** Conservative rules may have lower recall and may over-abstain on layouts that a richer parser or language model could interpret.

## DEC-060: Use hash-derived IDs and canonical output

- **Context:** Baseline reproducibility requires identical source input to produce identical IDs, order and serialized bytes across runs and platforms.
- **Alternatives:** Use UUID4 identifiers; use process-local counters; derive identifiers from stable inputs and serialize a canonical model dump.
- **Chosen option:** Derive batch, evidence and candidate IDs from stable source and provenance content and serialize with sorted deterministic JSON.
- **Reason:** SHA-256 inputs, fixed ordering and canonical JSON make repeated output comparison transparent without timestamps, filesystem paths or process state.
- **Trade-off:** IDs are content-sensitive and change when bounded source text or provenance changes, even when a reader considers the semantic meaning similar.

## DEC-061: Defer standalone candidate-entity generation

- **Context:** Candidate facts already retain source-stated subjects, while a separate entity heuristic would introduce aliasing and consolidation decisions beyond the frozen deterministic candidate scope.
- **Alternatives:** Generate an entity for every subject string; add source-specific alias mappings; return no standalone entities and defer consolidation.
- **Chosen option:** Return an empty entity list in `deterministic-baseline-v0.1` and retain source-stated subject fields on `CandidateFact`. Entity consolidation remains future work.
- **Reason:** This preserves the candidate schema without pretending that lexical subject detection solves entity identity or cross-document resolution.
- **Trade-off:** Consumers cannot use standalone candidate entities from this baseline and must wait for later extraction or reconciliation work.

## DEC-062: Implement and review the evaluator before observing scores

- **Context:** Matching normalization, pairing and denominator choices can materially change a small development score, creating a risk that implementation is adjusted after seeing the result.
- **Alternatives:** Implement and tune the evaluator while viewing development scores; use a manual spreadsheet after extraction; merge a reviewed executable contract before running the real benchmark.
- **Chosen option:** Merge the executable matching and metric contract before running the real development benchmark.
- **Reason:** Pre-observation review makes the first score traceable to rules fixed independently of its outcome and exposes later semantic changes as explicit experiment changes.
- **Trade-off:** Defects found during the first execution require a documented pre-freeze correction or a new experiment version rather than an unrecorded matching adjustment.

## DEC-063: Use strict source-bounded one-to-one fact matching

- **Context:** Candidate and gold counts can contain repeated or similar facts, while fuzzy or many-to-one credit would make exact TP, FP and FN attribution difficult to audit.
- **Alternatives:** Allow one candidate to satisfy multiple annotations; use fuzzy semantic thresholds; require a strict source-bounded key and consume each candidate and annotation at most once.
- **Chosen option:** Require normalized subject, subject type, predicate, value type, typed value and all gold-material qualifiers, with deterministic one-to-one pairing.
- **Reason:** Source boundaries, exact typed semantics and lexical pairing make duplicate handling and unmatched records reproducible without source-specific judgment.
- **Trade-off:** Semantically equivalent wording and reasonable aliases may be under-credited as an FP/FN pair.

## DEC-064: Keep value normalization as a separate alignment metric

- **Context:** Strict fact matching includes normalized value, so a normalization error would otherwise prevent direct measurement of whether an otherwise compatible candidate normalized its value correctly.
- **Alternatives:** Report only strict fact F1; align from strict matches; align without normalized value and report typed-value equality separately.
- **Chosen option:** Align without normalized value and then report exact typed-value correctness.
- **Reason:** A distinct one-to-one alignment isolates value-normalization quality while retaining strict fact counts as the primary semantic result.
- **Trade-off:** The report contains a second pairing process whose deterministic tie-breakers must be reviewed and interpreted separately from strict matching.

## DEC-065: Require explicit owner assessment for challenge cases

- **Context:** The three development challenge cases test ambiguity, unsupported extraction and preservation of missing values, whose outcomes cannot be safely inferred from a generic fact-match count alone.
- **Alternatives:** Add source-specific automatic pass rules; omit challenge outcomes; require explicit case-level owner assessments against precomputed candidates and warnings.
- **Chosen option:** Do not add source-specific automatic challenge rules; require three case-level owner outcomes with traceable candidate/warning references.
- **Reason:** Explicit assessments preserve the generic evaluator boundary and keep context-dependent judgments visible without encoding known document answers into runtime rules.
- **Trade-off:** Completing a development report requires a separate owner-review step and cannot be fully automated.

## DEC-066: Split Stage 3B.4B at the owner-review boundary

- **Context:** The frozen evaluator requires explicit outcomes for three development challenge cases, but those contextual judgments cannot be delegated to the extraction implementation or inferred safely from strict fact counts.
- **Alternatives:** Let the workflow assign challenge outcomes automatically; delay all reproducibility evidence until owner review finishes; split execution into preparation and finalization checkpoints.
- **Chosen option:** Use `prepare` to run and lock development extraction and create an incomplete owner-review template, then permit `finalize` only after the project owner supplies all three outcomes and rationales.
- **Reason:** The split preserves an auditable boundary between deterministic execution evidence and human semantic judgment.
- **Trade-off:** The development evaluation requires a deliberate manual handoff and cannot complete in one unattended command.

## DEC-067: Create an immutable observation lock at first score visibility

- **Context:** Once TP, FP, FN or derived metrics are visible, changing deterministic rules, matching normalization or evaluator denominators could tune the experiment retrospectively.
- **Alternatives:** Record only the later final report; rely on commit history without a dedicated artifact; write a lock immediately after the first strict development result.
- **Chosen option:** Create `observation_lock.json` during `prepare`, before owner review, with the preparation commit, immutable hashes, input and output hashes, exact preliminary metrics and unmatched IDs.
- **Reason:** The lock makes the first observed result durable and freezes `deterministic-baseline-v0.1` semantics at the moment post-observation tuning becomes possible.
- **Trade-off:** Any later semantic tuning requires a declared `deterministic-baseline-v0.2` experiment rather than editing v0.1 in place.

## DEC-068: Preserve canonical primary outputs and repeat hashes

- **Context:** Reproducibility requires evidence that identical parsed inputs produce identical candidate bytes without unnecessarily committing duplicate files.
- **Alternatives:** Preserve only aggregate metrics; commit both identical output copies; preserve canonical primary files and record independently generated repeat hashes.
- **Chosen option:** Keep primary and repeat canonical files under the ignored working root, publish the five primary outputs, and record both hash inventories in the run manifest and observation lock.
- **Reason:** Canonical outputs and independently observed repeat hashes provide compact, inspectable reproducibility evidence.
- **Trade-off:** A reviewer can inspect published primary bytes directly, while reproducing the second byte stream requires rerunning the fixed preparation workflow.

## DEC-069: Treat the baseline freeze manifest as necessary but not sufficient for held-out access

- **Context:** A development freeze proves that code, outputs, metrics and owner assessments were preserved, but automatically treating its existence as held-out authorization would weaken the separate execution guard.
- **Alternatives:** Enable held-out loading whenever a manifest file exists; add a boolean bypass to the development CLI; require both a valid freeze and a separately reviewed guarded execution path.
- **Chosen option:** The manifest must retain `held_out_access_status=still_blocked_pending_separate_guarded_execution`; held-out access requires a later explicit guard and invocation.
- **Reason:** Separating reproducibility evidence from authorization prevents accidental held-out reads and keeps the first held-out run reviewable.
- **Trade-off:** Stage 3B.5 requires another implementation and review step after the development baseline is frozen.

## DEC-070: Preserve the failed v0.1 observation

- **Context:** The first real development execution preserved four repeat-identical candidate outputs, while S004 failed identically on both attempts and prevented five-source baseline acceptance.
- **Alternatives:** Delete the failed run; overwrite it after changing v0.1; retain the lock, four outputs, structural inventory and failed attempt as immutable evidence.
- **Chosen option:** Keep the observation lock, four candidate outputs, structural inventory and failed S004 attempt as immutable evidence rather than overwriting or deleting them.
- **Reason:** Preserving an unsuccessful first observation makes the execution history auditable and prevents post-observation changes from being presented as the original result.
- **Trade-off:** The repository permanently records an incomplete, unsuccessful baseline that requires careful claim boundaries.

## DEC-071: Defer formal challenge outcomes until a complete versioned run

- **Context:** One development challenge source failed before candidate generation, so its expected do-not-extract behaviour cannot be assessed as a successful extractor outcome.
- **Alternatives:** Infer a passing outcome from the absence of candidates; assess only the two successful-source cases; defer all formal outcomes until every scored source completes.
- **Chosen option:** Do not complete formal owner assessments on a run where one challenge source failed before candidate generation.
- **Reason:** A crash is not evidence of correct abstention, and partial assessment would leave the v0.1 result open to misleading interpretation.
- **Trade-off:** Existing S001 and S006 review material remains unused until a complete later run is available.

## DEC-072: Require deterministic-baseline-v0.2 for corrections

- **Context:** Read-only diagnosis found a source-independent extractor defect after the first v0.1 observation, and any correction must change how an incompatible candidate is typed or abstained.
- **Alternatives:** Patch v0.1 in place; suppress the exception without a new plan; preserve v0.1 and freeze a separate corrected experiment version.
- **Chosen option:** Diagnose v0.1 without semantic modification, then freeze a separate v0.2 plan before correcting the extractor or tuning source-independent rules.
- **Reason:** Versioning keeps the original code and observation immutable while allowing a reviewed, neutral correction to be evaluated transparently.
- **Trade-off:** A new planning and review cycle is required before the complete five-source run can be attempted again.

## DEC-073: Preserve v0.1 implementation files and add v0.2 modules

- **Context:** The v0.1 observation is immutable, and its report, run, observation, review, inventory and freeze contracts hard-code the v0.1 experiment identity.
- **Alternatives:** Patch v0.1 modules in place; parameterize and rewrite the observed v0.1 stack; add versioned v0.2 modules while reusing only unchanged shared contracts.
- **Chosen option:** Preserve v0.1 implementation files byte-identically and add versioned v0.2 extractor, rule, CLI, report, run and freeze modules.
- **Reason:** Additive modules keep the observed v0.1 code reconstructable and prevent v0.2 evidence from serializing a v0.1 identity.
- **Trade-off:** Some orchestration and model logic is duplicated and must be kept deliberately version-scoped.

## DEC-074: Abstain at candidate level on incompatible predicate contracts

- **Context:** One v0.1 commitment draft used an incompatible `metric` subject and caused all S004 candidate output construction to fail.
- **Alternatives:** Weaken the predicate schema; coerce the subject type; silently drop invalid drafts; validate each draft and preserve an explicit abstention warning.
- **Chosen option:** Validate predicate, subject type, value type and qualifiers before `CandidateFact` construction, omit only an incompatible draft and emit `abstained_incompatible_predicate_contract`.
- **Reason:** Candidate-level abstention preserves the unchanged schema and other valid document candidates while making the loss observable.
- **Trade-off:** A recoverable but incompatible draft is not emitted, and warning handling becomes part of the deterministic contract.

## DEC-075: Permit only development-evidence-backed source-independent tuning

- **Context:** The failed v0.1 observation exposes large commitment over-triggering and bounded gaps, but post-observation tuning creates a leakage risk.
- **Alternatives:** Make broad heuristic improvements; tune per source; permit only families supported by aggregate development diagnostics and neutral tests.
- **Chosen option:** Restrict v0.2 tuning to the required corrections and optional families explicitly included in the frozen error matrix, with source-independent behavior and neutral positive and negative tests.
- **Reason:** The restriction permits a transparent correction cycle without encoding document identity, expected answers or speculative coverage.
- **Trade-off:** Known misses remain where the development evidence does not establish a safe generic rule.

## DEC-076: Keep matching protocol, gold and candidate schema unchanged

- **Context:** The v0.1 nearest pairs fail semantic subject and value fields, and no candidate is hidden by a single matching-normalization defect.
- **Alternatives:** Relax strict matching; revise annotations; change candidate schema; improve only the versioned extractor and retain evaluation contracts.
- **Chosen option:** Keep matching protocol `0.1`, strict normalization, metric denominators, `public-gold-v0.1`, predicate vocabulary `0.1` and `CandidateExtractionResult` schema `0.1` unchanged for v0.2.
- **Reason:** Stable evaluation contracts make v0.1 and v0.2 comparable and prevent apparent gains from relabeling or weaker credit.
- **Trade-off:** Strict matching may continue to under-credit some semantic near-equivalents, which must be reported through structural diagnostics rather than rescored.

## DEC-077: Separate process acceptance from non-binding quality targets

- **Context:** A deterministic baseline must be reproducible and fully reported even if its development accuracy is weak, while observed quality still needs explicit diagnostics.
- **Alternatives:** Require a minimum F1; omit quality expectations; use mandatory process gates plus separate non-binding quality targets.
- **Chosen option:** Freeze twelve process acceptance gates with no minimum F1 and report seven non-binding quality targets independently.
- **Reason:** This permits an honest weak baseline to be frozen for later comparison while keeping over-triggering, review routing and duplicate behavior visible.
- **Trade-off:** A process-valid baseline may still perform poorly and must be described carefully.

## DEC-078: Require v0.3 after any post-observation v0.2 semantic change

- **Context:** Once the first v0.2 diagnostics are visible, changing extraction or evaluation behavior under the same identity would repeat the provenance problem the v0.2 boundary prevents.
- **Alternatives:** Allow bounded fixes within v0.2; overwrite a failed observation; preserve v0.2 and create v0.3 for every later semantic change.
- **Chosen option:** Require `deterministic-baseline-v0.3` after any post-observation change to triggers, candidates, qualifiers, confidence, review routing, duplicate policy, schema use, matching or metrics.
- **Reason:** A new experiment identity keeps first observations and their implementation commits auditable.
- **Trade-off:** Even a small semantic fix requires another plan, versioned implementation and execution cycle.

## DEC-079: Preserve the implementation chain and merge-commit execution boundary

- **Context:** The deterministic-baseline-v0.2 evidence contract depends on the reviewed planning and D-1 ancestry, while the first real prepare run must identify an immutable implementation whose exact implementation and test blobs were audited before observation.
- **Alternatives:** Squash or rebase the implementation chain; rewrite the branch before execution; preserve the five implementation commits, freeze their 14-file blob inventory and merge only with an explicit merge commit.
- **Chosen option:** Preserve the five implementation commits without squash, rebase or history rewrite; freeze the implementation/test blob inventory before observation; require **Create a merge commit**; and use the final PR merge commit as the implementation commit for the first real prepare run.
- **Reason:** Keeping ancestry and blob identity intact makes the planning boundary, D-1 boundary and reviewed implementation independently verifiable before any real score becomes visible.
- **Trade-off:** Real execution remains blocked until PR review, Python 3.10–3.12 CI, merge-commit integration and post-merge validation have all completed.

## DEC-080: Use additive v0.3 for development quality recovery

- **Context:** Frozen deterministic-baseline-v0.2 completed reproducibly but recovered no strict development gold facts, while its 321 candidates and selected 25-fact gold set exposed both generic coverage gaps and broad weak-commitment triggering.
- **Alternatives:** Modify v0.2 evidence or rules; relax matching protocol `0.1`; tune source-specific exceptions; preserve v0.2 and implement a development-only additive v0.3 with generic rules.
- **Chosen option:** Keep v0.2 immutable and implement additive `deterministic-baseline-v0.3` using source-independent generic rules only. Retain candidate schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1` and the unchanged `match_strict_facts` implementation for comparability. Calculate aggregate comparison metrics through an additive deterministic v0.3 report calculator that explicitly reconciles TP, FP and FN with matcher output; do not claim reuse of the complete frozen v0.2 evaluator. Separate neutral source-independent extractor unit tests from intentionally development-evidence-specific report regression tests. Treat official strict FP and precision as comparison metrics while explicitly stating that sparse gold cannot independently establish exhaustive candidate precision.
- **Reason:** Version isolation preserves the observed v0.2 evidence, unchanged matching prevents apparent gains through weaker credit, explicit reconciliation keeps the additive calculator auditable, and neutral production-rule tests remain distinct from development-observation assertions.
- **Trade-off:** Strict matching continues to under-credit plausible semantic near-equivalents, unmatched candidates remain unreviewed outside sparse-gold coverage, formal v0.3 owner assessment has not been performed and held-out performance remains unknown. During v0.3 tuning, the guarded loader may scan held-out raw JSONL bytes and row metadata for integrity and split routing, but it does not deserialize held-out semantic annotation models and no S005 or S007 ParsedDocument is opened or executed.

## DEC-081: Add v0.4 without changing the v0.3 or evaluation contracts

- **Context:** Integrated v0.3 preserved five strict development matches but left commitment actor and value representation gaps, while its implementation and reports now form the comparison parent.
- **Alternatives:** Modify v0.3; relax matching protocol `0.1`; add source-specific corrections; create an additive development-only v0.4 over immutable v0.3.
- **Chosen option:** Add separate `deterministic-baseline-v0.4` modules and reports while preserving v0.3, candidate schema `0.1`, predicate vocabulary `0.1`, public gold, matching protocol `0.1` and `match_strict_facts`. Keep neutral production-rule tests separate from intentionally development-evidence-specific report regression tests, and record candidate-level parent, actor and value transformations. Reject the first v0.4 attempt rather than retain strict matches produced by indirect actor inference.
- **Reason:** The version boundary, unchanged matcher and explicit transformation trace make the corrected actor/value change auditable without presenting weaker credit or unsafe inference as quality improvement.
- **Trade-off:** Corrected v0.4 preserves the five v0.3 strict matches but does not recover an S002 strict match; it duplicates some orchestration, formal v0.4 owner assessment remains outstanding and held-out extraction remains blocked.

## DEC-082: Resolve commitment actors only from explicit or unique trusted evidence

- **Context:** First-person and generic-government subjects can conceal an accountable document actor, but source identity, acronyms, titles, generic publication metadata and printing location do not establish that actor safely. The rejected first v0.4 attempt used indirect official-publication and UK print-location cues to synthesize a government actor.
- **Alternatives:** Preserve every pronoun; infer identity from document and publication context; resolve only from explicit statement actors or one directly evidenced role-aware authoring actor and otherwise abstain.
- **Chosen option:** Apply bounded quotation and reported-speech checks before every actor decision. Preserve an explicit statement actor only when the complete subject satisfies bounded actor eligibility. Resolve institutional first person or a generic government subject only when exactly one complete eligible organisation is supplied through author/sender fields, explicitly authoring metadata, or bounded front matter with explicit issued, published, authored, prepared or presented-by grammar. Preserve an unchanged v0.3 non-actor subject under `preserved_parent_subject` rather than calling it explicit or rewriting it. Never resolve from source ID, filename, page, checksum, document family, annotations, source-specific aliases, a document-title subject, generic publisher/creator metadata, licence or parliamentary boilerplate, or printing/publication location.
- **Reason:** Classification order, explicit eligibility and direct role-aware evidence prevent document-specific leakage, speaker substitution, fabricated jurisdiction and misleading actor-provenance labels while preserving parent semantics.
- **Trade-off:** Acronym-only, multi-actor, quoted and otherwise ambiguous documents remain blocked, unresolved or explicitly preserved even when a human reader could infer an actor; the corrected v0.4 therefore has no strict S002 commitment match.

## DEC-083: Keep v0.4 commitment value normalisation structural and non-generative

- **Context:** Strict commitment comparison is affected by structural future auxiliaries, possessives, semantic modifiers and truncated parent spans, but deleting ownership or emphasis and unrestricted paraphrasing would introduce semantic rewriting.
- **Alternatives:** Preserve every parent string; paraphrase values for semantic similarity; allow only declared structural normalization over a complete bounded source span while preserving source semantics.
- **Chosen option:** Remove only leading affirmative `will`, preserve semantic modifiers such as `now`, `also`, `immediately`, `still` and `only`, and preserve possessives. Allow one narrow recommendation-wrapper collapse only around a complete eligible action. Parent recovery may extend a source span to a safe same-statement boundary but must contain the complete normalized parent raw value and never shorten it. Preserve negation, intent, planning, explicit commitment modality, objects, quantities, dates, conditions and subordinate clauses; reject incomplete or unsafe wrappers and ambiguous boundaries.
- **Reason:** Lossless, bounded and non-generative operations improve canonical representation while retaining source evidence, ownership, emphasis and material meaning needed for strict audit.
- **Trade-off:** Anaphora, semantic compression, broad paraphrase and incomplete or ambiguous parent spans remain unmatched even when they are plausibly equivalent.

## DEC-084: Keep formal v0.4 challenge assessment as a separate human checkpoint

- **Context:** The corrected v0.4 comparison records three automated structural challenge passes, but predefined structural conditions cannot determine whether the actual evidence satisfies each frozen qualitative behavior.
- **Alternatives:** Treat 3/3 automated diagnostics as formal outcomes; let Codex infer outcomes and rationales; require the project owner to assess all three cases independently.
- **Chosen option:** Treat automated diagnostics only as machine evidence. Codex may prepare the evidence packet and blank template, but only the project owner may populate a `passed` or `failed` outcome and an evidence-based rationale for each case.
- **Reason:** Separating machine checks from qualitative judgment keeps authorship of the decisions explicit and prevents structural proxies from being presented as owner approval.
- **Trade-off:** v0.4 cannot be finalized through an unattended workflow and remains pending until three human decisions are completed and independently validated.

## DEC-085: Include every challenge-block candidate without tuning during review preparation

- **Context:** Selecting only candidates that support a favorable result would bias the review, while changing extraction after the merged comparison would invalidate the evidence being assessed.
- **Alternatives:** Include only machine-diagnostic candidate IDs; summarize favorable candidates manually; include every candidate whose resolved evidence references a frozen challenge block and preserve merged v0.4 semantics.
- **Chosen option:** Build the packet from all evidence-linked candidates, including ambiguous, unrelated, `not_required` and potentially adverse candidates, with complete candidate fields, resolved evidence and warning codes. Make no extraction, matching, evaluation or gold change during preparation.
- **Reason:** Complete deterministic inclusion makes omissions detectable and gives the owner the same bounded evidence regardless of the eventual decision.
- **Trade-off:** The packet may contain candidates that are not decisive and requires deliberate owner inspection rather than a pre-filtered answer.

## DEC-086: Preparation neither finalizes v0.4 nor authorizes held-out access

- **Context:** A blank owner template and integrity manifest establish review provenance but contain no completed assessment and cannot serve as a baseline freeze or execution authorization.
- **Alternatives:** Treat preparation as an implicit freeze; enable held-out execution after packet generation; retain separate assessment, finalization and held-out authorization gates.
- **Chosen option:** Keep all three owner outcomes and rationales null in the tracked preparation package. Require a later validated owner assessment and separate finalization transaction before any v0.4 freeze; keep held-out access blocked. Any later extraction or evaluation semantic change must use a new baseline version rather than editing v0.4.
- **Reason:** Distinct gates preserve the merged evidence, prevent premature performance claims and keep the first held-out execution separately reviewable.
- **Trade-off:** Additional reviewed milestones are required before v0.4 can be frozen or evaluated beyond development data.

## DEC-087: Record owner-supplied v0.4 judgments separately from machine evidence

- **Context:** After PR #20 merged the immutable blank template and evidence-complete review packet, project owner Kang Li explicitly supplied three outcomes and exact rationales. Automated diagnostics can validate predefined structural conditions but cannot author or replace qualitative owner judgment.
- **Alternatives:** Infer formal outcomes from the 3/3 automated diagnostics; edit the tracked blank template; store a separate completed record that preserves the supplied owner text and all fixed preparation references.
- **Chosen option:** Store the completed assessments separately from the unchanged blank template with assessment method `project_owner_review`, exact owner identity, exact rationales and unchanged case, experiment, candidate and warning metadata. Validate candidate and warning reconciliation and evidence consistency without replacing qualitative judgment. Require independent read-only review before commit; completion alone does not freeze or finalize v0.4, authorize held-out access or imply strong overall precision. Any later semantic extraction change requires a new baseline version.
- **Reason:** Explicit provenance and immutable preparation evidence prevent machine diagnostics from masquerading as human approval, make exact owner wording auditable and preserve the sparse-gold claim boundary.
- **Trade-off:** The separate completed record and validator add another controlled artifact set, and v0.4 still requires independent review and a later finalization transaction before any freeze or held-out authorization.

## DEC-088: Store independent review evidence separately from owner judgment

- **Context:** The completed assessment contains project-owner judgments, while the later independent audit is machine review evidence about provenance, validation and file boundaries.
- **Chosen option:** Add a strict independent-review record without changing the completed assessment, its rationales, the blank template or the historical validation report whose review status was still pending when written.
- **Reason:** Separate artifacts prevent an automated reviewer from being represented as the author of an owner outcome.
- **Trade-off:** Finalization must validate one additional evidence identity.

## DEC-089: Merge the finalization implementation before real execution

- **Context:** A real finalization would reproduce development candidates and create the canonical report, error analysis, finalization record and freeze manifest.
- **Chosen option:** Implement and test the transaction with fictional inputs, obtain independent read-only review and merge the implementation before any real five-source execution.
- **Reason:** The first real finalization must run against an immutable reviewed implementation commit rather than uncommitted workflow code.
- **Trade-off:** v0.4 remains unfrozen for an additional reviewed milestone.

## DEC-090: Require exact v0.4 reproduction before finalization

- **Context:** The authoritative comparison already fixes five ParsedDocument hashes, five candidate-output hashes, source and predicate counts, strict matches and exact metric fractions.
- **Chosen option:** Run the unchanged v0.4 extractor twice, require byte-identical primary and repeat outputs, verify every fixed hash and count, and reconcile through unchanged `match_strict_facts` before writing anything.
- **Reason:** Exact reproduction detects implementation, input, schema or matching drift instead of silently creating a different v0.4 observation.
- **Trade-off:** Any legitimate semantic correction must use a later baseline version.

## DEC-091: Separate process acceptance from quality observations

- **Context:** The weak strict score is an observed development result, while reproducibility, complete provenance and transactional integrity determine whether the observation can be frozen honestly.
- **Chosen option:** Use a fixed ordered inventory of 28 mandatory process gates and record nine quality observations separately as explicit non-binding evidence. No minimum-F1 gate applies.
- **Reason:** A weak but process-valid baseline remains a useful, auditable comparison point without presenting the score as strong performance.
- **Trade-off:** Readers must interpret process acceptance and model quality as different dimensions.

## DEC-092: Preserve the sparse-gold claim boundary in final error analysis

- **Context:** The selected development gold contains 25 facts and is not proven exhaustive, so strict unmatched candidates are not automatically confirmed semantic errors.
- **Chosen option:** Retain official TP, FP and FN for strict comparison, but label non-match diagnostics as structural and prohibit exhaustive-precision or universal-error claims.
- **Reason:** This reports the fixed matcher result without overstating what the annotations establish.
- **Trade-off:** Candidate-level semantic precision remains unknown without a separate exhaustive review.

## DEC-093: Keep baseline freeze separate from held-out authorization

- **Context:** A development freeze preserves process evidence but does not establish held-out generalization or approve the first held-out execution.
- **Chosen option:** Fix held-out authorization to false in finalization evidence and require a later separately reviewed guard and explicit authorization even after a valid v0.4 freeze.
- **Reason:** Reproducibility evidence must not become an implicit data-access bypass.
- **Trade-off:** Another controlled milestone is required before held-out evaluation.

## DEC-094: Require v0.5 for any post-v0.4 semantic change

- **Context:** Finalization must reproduce the already observed v0.4 candidates and metrics without changing extraction, matching, gold, owner judgment or candidate normalization.
- **Chosen option:** Treat any later change to candidate semantics, rules, matching, annotations, review routing or metric meaning as `deterministic-baseline-v0.5` rather than updating v0.4.
- **Reason:** The v0.4 identity remains tied to one exact semantic implementation and observation.
- **Trade-off:** Even bounded semantic corrections require another versioned plan, implementation and evidence cycle.

## DEC-095: Close Stage 3B at the committed v0.4 development freeze

- **Context:** PR #25 merged exactly fourteen finalized `deterministic-baseline-v0.4` development artifacts at `3d16248` after controlled finalization with implementation commit `d798868bd8b66a30babfc1b14450fb253f2dbc63` and freeze date `2026-08-02`. The five primary/repeat output pairs are byte-identical, all 28 process gates passed, and the evidence records a weak development score under sparse gold.
- **Alternatives:** Keep Stage 3B open after the committed freeze; treat the reproducible freeze as evidence of strong quality or production readiness; close Stage 3B while preserving the development-only claim and access boundaries.
- **Chosen option:** Close Stage 3B at the committed v0.4 development freeze. Keep `deterministic-baseline-v0.4` immutable, keep held-out execution unauthorized, make no production-readiness or exhaustive-precision claim, require `deterministic-baseline-v0.5` for any semantic change, and require a separate decision before defining the next-stage scope.
- **Reason:** The committed artifacts establish a reproducible engineering and evaluation milestone with fixed provenance, deterministic outputs and explicit limitations, which is sufficient to close Stage 3B without overstating model quality or generalization.
- **Trade-off:** Stage 3B closes with weak development quality and no held-out result; any semantic improvement, held-out authorization or next-stage architecture requires a new separately reviewed decision.

## DEC-096: Build a development-only LLM extraction comparator before RAG

- **Context:** Stage 3B closed with a reproducible but weak deterministic development baseline, while the portfolio still lacks an LLM-assisted extraction comparison. Building retrieval first would not establish whether candidate knowledge is extracted accurately or with valid evidence.
- **Alternatives:** Begin RAG and retrieval immediately; stop after the deterministic baseline; build a controlled development-only LLM extraction comparator before downstream architecture.
- **Chosen option:** Plan and implement `llm-extraction-baseline-v0.1` as a development-only, evidence-linked candidate extraction comparator before any RAG, reconciliation, cloud or user-interface work.
- **Reason:** A bounded comparator demonstrates prompt, schema, evidence, provenance, cost, cache and evaluation engineering while preserving the project's evaluate-before-RAG principle.
- **Trade-off:** Retrieval and presentation work remain deferred, and the LLM comparator may not outperform the deterministic baseline.

## DEC-097: Preserve existing candidate and matching contracts for fair comparison

- **Context:** Changing the candidate schema, predicate vocabulary, public gold or matcher while introducing an LLM would make any observed difference difficult to attribute.
- **Alternatives:** Design an LLM-specific schema and matcher; relax strict credit for generated candidates; preserve the existing contracts unless a later reviewed schema decision is necessary.
- **Chosen option:** Preserve the Common Document Object input, `CandidateExtractionResult` schema `0.1`, predicate vocabulary `0.1`, `public-gold-v0.1`, matching protocol `0.1`, unchanged strict matcher and development sources S001, S002, S003, S004 and S006 for `llm-extraction-baseline-v0.1`.
- **Reason:** Fixed inputs and scoring provide the clearest comparison with immutable `deterministic-baseline-v0.4` and prevent apparent gains through changed evaluation semantics.
- **Trade-off:** The existing strict contracts may under-credit plausible LLM outputs and may require abstention where a future separately versioned schema could represent nuance better.

## DEC-098: Use one provider behind a narrow interface with mock mode

- **Context:** Direct provider coupling, multiple providers and networked unit tests would increase cost, secret exposure, nondeterminism and provenance complexity before the extraction contract is established.
- **Alternatives:** Call multiple providers directly from extraction code; choose and embed one provider in this planning PR; define one provider-neutral interface with a deterministic mock and defer the real provider/model choice to a separate gate.
- **Chosen option:** Permit at most one real provider behind a narrow provider-neutral interface and require a deterministic mock for tests. Unit tests make no network calls, credentials come only from environment configuration, and a separate reviewed decision must select the provider and model before a real adapter is implemented or invoked.
- **Reason:** The interface isolates transport from extraction semantics, mock mode supports deterministic failure testing, and the later decision gate can assess model identity, data terms, cost and operational limits without prematurely coupling the plan.
- **Trade-off:** Stage 4 v0.1 will not compare providers, and real execution remains blocked until the provider/model gate is accepted.

## DEC-099: Keep held-out authorization separate from LLM development and freeze

- **Context:** Sending a held-out document to an LLM is an execution event that could disclose source content and reveal performance, while a development freeze establishes only reproducibility on approved development sources.
- **Alternatives:** Treat LLM development or a valid development freeze as implicit held-out authorization; permit exploratory held-out calls; retain a separate reviewed guard and explicit project-owner authorization.
- **Chosen option:** Keep Stage 4A-E development only. No held-out source, `ParsedDocument` or semantic annotation may be opened or executed, a development freeze does not authorize held-out access, and any later held-out invocation requires a separately reviewed guard plus explicit project-owner authorization.
- **Reason:** Separating access from implementation and freeze prevents accidental leakage, preserves the evaluation boundary and stops development evidence from being presented as held-out generalization.
- **Trade-off:** Stage 4 cannot report held-out results, and a later controlled milestone is required before any generalization assessment.
