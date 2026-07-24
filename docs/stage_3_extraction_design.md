# Stage 3 Candidate-Extraction Design

## Status and scope

Stage 3A, Stage 3B.1 planning and the Stage 3B.2 development-only gold access boundary are complete. The repository implements the candidate-extraction contract, bounded predicate vocabulary, public-PDF annotation models, freeze-level validation, frozen `public-gold-v0.1` and guarded development-label loading. It does not implement an extractor, reconciliation, extraction metrics, an LLM call or held-out extraction.

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

Candidate evidence preserves a short excerpt plus the existing block ID, source ID, location type, and location value. Paths are not part of the contract. References to missing evidence or sources are invalid. `CandidateFact` and `GoldFactAnnotation` call the same runtime predicate-use validator, so registered subject types, value types, required qualifiers, and declared qualifier names cannot diverge between production candidates and evaluation labels.

## Predicate vocabulary

Vocabulary v0.1 contains exactly 20 canonical predicates. It is intentionally bounded rather than a general ontology. Definitions constrain subject types, value types, aliases, and contextual qualifiers. Normalization handles spacing, hyphens, case, and documented legacy synthetic names; unknown predicates fail instead of extending the registry implicitly. Runtime validation also rejects incompatible subject or value types, missing or empty required qualifiers, and qualifiers not declared for the canonical predicate.

The vocabulary contains no source IDs, filenames, held-out values, or source-specific rules.

## Evidence and annotation requirements

Every frozen public fact points to one existing Stage 2 `PAGE_TEXT` block, the correct 1-based PDF page, and a short excerpt that occurs in normalized block text. Structural validation also reconciles the source split and document family. Project-owner semantic review is complete for all 35 facts and six challenge cases, and the manifest protects both JSONL files with SHA-256 hashes.

Ambiguous, unsupported, and missing-value examples are separate challenge cases. They specify review, rejection, or missing-value preservation without inventing an expected value.

## Stage 3A held-out control

The public benchmark is procedural because labels are visible in the repository. Stage 3B may load development labels during deterministic-baseline design and development evaluation. Held-out facts and cases cannot be loaded by rule-design code, tests or tuning; the experiment version, rules and code must be frozen before held-out evaluation.

## Stage 3B.1 deterministic-baseline plan

The baseline contract was frozen before implementation in the [Stage 3B deterministic baseline plan](stage_3b_deterministic_baseline_plan.md), [machine-readable experiment configuration](../configs/experiments/deterministic_baseline_v0.1.json), and [matching protocol v0.1](stage_3b_matching_protocol.md).

Baseline v0.1 scores candidate extraction for eight predicates: `action_status`, `budget`, `commitment`, `decision`, `metric`, `recommendation`, `requirement` and `risk`. Its primary scored scope is development-only public-PDF data. Development synthetic documents may later provide non-scored format and contract smoke tests, while reconciliation and synthetic final-state evaluation remain separate future work.

Stage 3B.2 development-only annotation loading and its fail-closed held-out access guard are implemented. No extractor or metric result exists yet.

## Stage 3B.2 development-only gold access

The [development-only public-gold loader](stage_3b_development_gold_loader.md) validates the frozen experiment configuration, public-gold manifest, repository-relative paths, corpus split and binary content hashes before returning labels. It metadata-scans ID, source and split fields from bounded binary JSONL lines, semantically validates only the 25 development facts and three development challenge cases, and returns them in deterministic experiment-source order.

Held-out or unknown access modes fail before repository-root resolution or file I/O. Held-out lines are read only for content hashing and metadata routing; no held-out semantic model is constructed. The generic complete-dataset loaders remain available for Stage 3A validation only. Baseline implementation and evaluation code must use the guarded API, while the future extractor must receive only `ParsedDocument` and must not import any gold loader.

No extractor or metric exists. Stage 3B.3 source-independent deterministic rule implementation is next.

## Current limitations

- No deterministic or LLM extractor emits `CandidateExtractionResult` yet.
- Frozen `public-gold-v0.1` has 35 owner-verified facts and six owner-verified challenge cases, but only one project-owner reviewer and no inter-annotator agreement.
- Page-level blocks can preserve awkward PDF whitespace and coarse evidence spans.
- No public-gold extraction score exists.
- Final reconciliation, duplicate handling, conflict handling, and review workflow remain planned.
