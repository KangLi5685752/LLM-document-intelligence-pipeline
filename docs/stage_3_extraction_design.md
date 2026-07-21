# Stage 3 Candidate-Extraction Design

## Status and scope

Stage 3A implements the candidate-extraction contract, bounded predicate vocabulary, public-PDF annotation models, and deterministic annotation validation. It does not implement an extractor, reconciliation, extraction metrics, an LLM call, or held-out extraction.

## Three distinct data layers

### ParsedDocument

`ParsedDocument` is the implemented Stage 2 format-level output. It contains normalized text blocks, document metadata, parsing warnings, and source provenance. It does not contain extracted entities or facts.

### CandidateExtractionResult

`CandidateExtractionResult` is the implemented Stage 3 pre-reconciliation contract. It contains:

- proposed entities;
- candidate facts;
- evidence references linked to existing `ParsedDocument` blocks;
- bounded extraction metadata and warnings.

A candidate fact is an observation proposed by a deterministic extractor, future LLM extractor, or manual annotation. It is not a current fact and has no final `fact_state`.

### KnowledgeExtractionResult

`KnowledgeExtractionResult` remains a planned reconciled output. A later stage may assign current, superseded, duplicate, and unresolved-conflict states only after comparing candidates and their evidence. No runtime model or reconciliation implementation exists yet.

## Why extraction and reconciliation are separate

Extraction answers: “What bounded statement and evidence did this source appear to contain?” Reconciliation answers: “How should candidates across related documents be combined, compared, or left unresolved?” Keeping these questions separate prevents an extractor from silently presenting a recent, repeated, or high-confidence candidate as authoritative.

This boundary also allows deterministic and future LLM approaches to emit the same candidate schema. Their candidate quality can later be compared before any shared reconciliation policy is applied.

## Candidate contract

Schema version `0.1` uses strict Pydantic v2 models with unknown fields forbidden. Candidate facts preserve:

- source and document-family identifiers;
- source-stated subject text and bounded subject type;
- one registered predicate;
- raw and bounded normalized values;
- qualifiers;
- evidence IDs;
- confidence, review status, method, and warnings.

Candidate evidence preserves a short excerpt plus the existing block ID, source ID, location type, and location value. Paths are not part of the contract. References to missing evidence or sources are invalid.

## Predicate vocabulary

Vocabulary v0.1 contains exactly 20 canonical predicates. It is intentionally bounded rather than a general ontology. Definitions constrain subject types, value types, aliases, and contextual qualifiers. Normalization handles spacing, hyphens, case, and documented legacy synthetic names; unknown predicates fail instead of extending the registry implicitly.

The vocabulary contains no source IDs, filenames, held-out values, or source-specific rules.

## Evidence and annotation requirements

Every public fact draft points to one existing Stage 2 `PAGE_TEXT` block, the correct 1-based PDF page, and a short excerpt that occurs in normalized block text. Structural validation also reconciles the source split and document family against the frozen manifest.

Ambiguous, unsupported, and missing-value examples are separate challenge cases. They specify review, rejection, or missing-value preservation without inventing an expected value.

## Stage 3A held-out control

The public benchmark is procedural because labels are visible in the repository. Stage 3A may create and structurally validate held-out labels, but it does not run extraction on held-out sources. Held-out values cannot influence predicate definitions, deterministic rules, prompt design, or development assertions. A future deterministic baseline must be designed using development sources only and frozen before held-out evaluation.

## Current limitations

- No deterministic or LLM extractor emits `CandidateExtractionResult` yet.
- Public annotations are AI-assisted drafts and owner verification is pending.
- Page-level blocks can preserve awkward PDF whitespace and coarse evidence spans.
- No public-gold extraction score exists.
- Final reconciliation, duplicate handling, conflict handling, and review workflow remain planned.
