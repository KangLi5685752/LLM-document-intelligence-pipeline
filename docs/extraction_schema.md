# Evidence-Linked Extraction Schema

- **Schema design version:** 0.1
- **Status:** Candidate extraction models implemented; final `KnowledgeExtractionResult` remains a planned design contract.

The candidate layer is implemented in Stage 3A. Final reconciliation models remain planned. The schema may evolve only through explicit versioning.

## Top-level result

The conceptual top-level object is `KnowledgeExtractionResult`.

| Field | Meaning |
| --- | --- |
| `schema_version` | Version of the extraction contract. |
| `batch_id` | Stable identifier for one related-document processing batch. |
| `source_documents` | Source-document metadata and parse outcomes. |
| `entities` | Canonical entities and their aliases. |
| `facts` | Fact records and the evidence-reference catalog addressed by their evidence IDs. |
| `conflicts` | Resolved or unresolved conflicts between supported facts. |
| `duplicate_groups` | Groups of semantically duplicated facts. |
| `review_items` | Items requiring human review. |
| `processing_summary` | Counts, warnings, failures, and outcome summary. |
| `run_metadata` | Planned extraction-run provenance. |

`run_metadata` is planned and may later contain:

- `extraction_run_id`;
- parser version;
- extraction method;
- prompt version;
- model version;
- processing timestamp.

No runtime implementation currently exists.

## SourceDocumentRecord

| Field | Meaning |
| --- | --- |
| `source_id` | Stable source-register identifier. |
| `document_family` | Family used for related-document processing and leakage control. |
| `source_format` | PDF, PPTX, or EML. |
| `filename` | Local filename or controlled source name. |
| `title` | Document or message title. |
| `document_date` | Publication, reporting, or message date when available. |
| `authors_or_senders` | Document authors or message senders. |
| `source_url` | Authoritative source URL when applicable. |
| `checksum` | SHA-256 for the exact source file. |
| `split` | Development or held-out assignment. |
| `parse_status` | Planned structured parse outcome. |

## EntityRecord

| Field | Meaning |
| --- | --- |
| `entity_id` | Stable entity identifier within the result. |
| `canonical_name` | Selected display name. |
| `entity_type` | Bounded entity category. |
| `aliases` | Alternative names observed in evidence. |
| `source_ids` | Sources supporting or mentioning the entity. |

Allowed entity types include:

- `initiative`;
- `programme`;
- `policy`;
- `organisation`;
- `recommendation`;
- `risk`;
- `decision`;
- `metric`;
- `other`.

This is not intended to define a complete enterprise ontology.

## EvidenceReference

| Field | Meaning |
| --- | --- |
| `evidence_id` | Stable evidence identifier within the result. |
| `source_id` | Existing source to which the evidence belongs. |
| `location_type` | Type of source location. |
| `location_value` | Page, slide, body, history, section, or metadata locator. |
| `block_id` | Planned parsed-block identifier. |
| `text_excerpt` | Short supporting excerpt. |
| `evidence_status` | Planned validation status for the reference. |

Allowed `location_type` values:

- `page`;
- `slide`;
- `email_body`;
- `quoted_history`;
- `section`;
- `document_metadata`.

Rules:

- Page and slide numbers are 1-based.
- Text excerpts must be short and must not replace source files.
- An evidence reference must point to an existing source.
- Unsupported facts cannot be marked `current`.
- Quoted history must be distinguishable from the latest message body.

## Candidate extraction layer

`CandidateExtractionResult` is the implemented Stage 3 pre-reconciliation contract. It accepts candidate entities, candidate evidence references, candidate facts, and warnings from a future deterministic extractor, future LLM extractor, or manual annotation process.

`CandidateFact` preserves the source, document family, source-stated subject, bounded predicate, raw and normalized values, qualifiers, evidence IDs, confidence, review status, extraction method, and warnings. It deliberately has no final `fact_state`.

Candidate evidence must point to an existing `ParsedDocument` block and preserve its source and location. Missing or cross-source evidence references are invalid. Page and slide locations remain positive and 1-based; email-body and quoted-history references preserve the existing ingestion block ID.

Current, superseded, duplicate, and unresolved-conflict states are assigned only by a later reconciliation layer. Candidate confidence or document order cannot assign those states implicitly. Candidate schema version `0.1` remains unchanged unless an incompatible contract change is made.

## FactRecord

| Field | Meaning |
| --- | --- |
| `fact_id` | Stable fact identifier within the result. |
| `subject_id` | Entity identifier when resolved. |
| `subject_text` | Subject as expressed in the source. |
| `subject_type` | Bounded subject category. |
| `predicate` | Versioned fact relationship or attribute. |
| `raw_value` | Original extracted value. |
| `normalized_value` | Normalized representation when successful. |
| `value_type` | Type used for normalization and matching. |
| `fact_state` | Current, superseded, duplicate, unresolved conflict, or unknown. |
| `effective_date` | Date on which the fact becomes effective, when supported. |
| `observed_date` | Date on which the source states or records the fact. |
| `qualifiers` | Structured contextual restrictions. |
| `evidence_ids` | Evidence references supporting the fact. |
| `confidence` | Planned bounded confidence value. |
| `review_status` | Planned review state. |
| `superseded_by_fact_id` | Current fact that explicitly replaces this fact. |
| `duplicate_of_fact_id` | Canonical fact when this fact is a duplicate. |

Allowed value types:

- `string`;
- `date`;
- `money`;
- `number`;
- `percentage`;
- `status`;
- `person`;
- `organisation`;
- `boolean`;
- `list`;
- `other`.

Allowed fact states:

- `current`;
- `superseded`;
- `duplicate`;
- `unresolved_conflict`;
- `unknown`.

### current

The best-supported active value after reconciliation. A fact must not become current solely because it appears in the latest source.

### superseded

A previously supported value explicitly replaced, approved over, made ineffective, or invalidated by a later authoritative statement.

### duplicate

The same semantic fact repeated with a compatible subject, predicate, normalized value, and effective context. Duplicate evidence is preserved rather than discarded.

### unresolved_conflict

One of two or more incompatible supported values for which no authoritative final resolution exists. No single value may be emitted as current for that predicate.

### unknown

A candidate value that cannot be reliably classified and must be reviewed.

## ConflictRecord

| Field | Meaning |
| --- | --- |
| `conflict_id` | Stable conflict identifier. |
| `subject_id` | Entity to which the conflict applies. |
| `predicate` | Conflicting relationship or attribute. |
| `candidate_fact_ids` | Supported incompatible candidate facts. |
| `conflict_status` | `unresolved` or `resolved`. |
| `resolution_fact_id` | Explicitly supported resolution, otherwise null. |
| `evidence_ids` | Evidence supporting the candidates or resolution. |
| `review_required` | Whether human review is required. |

Rules:

- Unresolved conflicts must use `resolution_fact_id = null`.
- Unresolved conflicts must route to human review.
- The system must not select a candidate merely because it is later in file order.
- Resolution requires explicit supporting evidence.

## DuplicateGroup

| Field | Meaning |
| --- | --- |
| `duplicate_group_id` | Stable group identifier. |
| `canonical_fact_id` | Canonical representative fact. |
| `duplicate_fact_ids` | Other semantically equivalent facts. |
| `evidence_ids` | Evidence preserved across the group. |

## ReviewItem

| Field | Meaning |
| --- | --- |
| `review_id` | Stable review identifier. |
| `reason_code` | Defined reason for review. |
| `priority` | Planned review priority. |
| `related_source_ids` | Sources related to the review item. |
| `related_fact_ids` | Facts related to the review item. |
| `related_conflict_ids` | Conflicts related to the review item. |
| `description` | Concise human-readable explanation. |
| `review_status` | Planned review workflow state. |

Allowed reason codes:

- `unresolved_conflict`;
- `missing_evidence`;
- `unsupported_value`;
- `ambiguous_subject`;
- `normalization_failure`;
- `parser_warning`;
- `schema_failure`;
- `low_confidence`;
- `incomplete_document_family`.

## Derived InitiativeSummary

The application may derive an initiative summary when suitable facts exist.

Fields:

- `initiative_id`;
- `canonical_name`;
- `aliases`;
- `current_status`;
- `current_owner`;
- `approved_budget`;
- `target_date`;
- `reporting_date`;
- `open_risks`;
- `decisions`;
- `KPIs`;
- `unresolved_conflict_count`;
- `review_required`.

`InitiativeSummary` is derived from evidence-linked facts. It must not become a second unsupported source of truth.

## Normalisation rules

- Dates become ISO 8601 `YYYY-MM-DD` where possible.
- Money becomes a numeric amount plus an ISO-style currency code.
- Percentages become numeric percentages.
- Whitespace is normalized.
- The original raw value is preserved.
- Names preserve display casing.
- Status values may map to controlled values such as Green, Amber, Red, Open, Closed, and Unknown.
- Failed normalization preserves the raw value and creates a review item.

## Reconciliation precedence

The following order is evidence for reconciliation, not an unconditional algorithm:

1. Explicit approval, effective-date, final-position, or superseded language.
2. Explicit statements that a value remains current.
3. Document or message chronology within the same family.
4. Source role and authority.
5. Consistency across independent evidence.
6. An unresolved conflict when authoritative evidence does not select one value.

Rules:

- Approved overrides proposed or draft.
- Explicit final values override working values.
- Advisory values do not become approved values.
- Quoted history is historical evidence unless the latest body reaffirms it.
- Latest does not automatically mean authoritative.
- Incompatible unresolved values remain unresolved.

## Relationship to synthetic ground truth

`synthetic_ground_truth.jsonl` is evaluation metadata, not the exact system-output format. Future evaluation code will map system facts and conflicts to the ground-truth records. Ground truth must never be passed to the parser or extractor.
