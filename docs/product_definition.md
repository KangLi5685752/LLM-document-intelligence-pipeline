# Product Definition

**Project:** LLM Document Intelligence & Knowledge Extraction Pipeline
**Repository:** LLM-document-intelligence-pipeline

## Product statement

An evaluated portfolio prototype that accepts related PDF, PPTX, and EML documents and converts them into evidence-linked structured knowledge, while distinguishing current facts, superseded facts, duplicated facts, unresolved conflicts, and items requiring human review.

This is not merely a document-chat or generic RAG application. Extraction quality, provenance, reconciliation, and review behavior must be evaluated before retrieval is added.

## Primary business scenario

An AI, digital-transformation, project, portfolio, knowledge-management, or governance analyst receives related documents describing policies, programmes, projects, decisions, risks, metrics, owners, budgets, and dates.

The analyst needs to determine:

- what the documents state;
- which facts are current;
- which facts have been superseded;
- which facts are duplicates;
- which values remain in conflict;
- where each conclusion is supported;
- which items require human review.

## Target users

- AI / Digital Transformation Analyst
- Project or Portfolio Manager
- Knowledge Management / Research Analyst
- AI Governance Reviewer

## Inputs

The MVP supports:

- text-based PDF;
- PPTX;
- plain-text EML.

A processing batch may contain one document or a related document family. OCR and scanned-image extraction are excluded from the MVP.

## Core output

The product is designed to produce one format-neutral knowledge result containing:

- source-document records;
- entities;
- evidence-linked fact records;
- current facts;
- superseded facts;
- duplicate groups;
- unresolved conflicts;
- review items;
- a processing summary.

The generic evidence-linked fact layer supports both project and programme documents and policy, guidance, governance, and research documents. A portfolio-style initiative summary is a derived view over relevant facts, not the only supported output.

## User-visible output

A future interface may show:

- documents processed;
- entities or initiatives identified;
- current facts;
- superseded facts;
- unresolved conflicts;
- pending review items;
- source evidence;
- derived initiative summaries.

This interface does not currently exist.

## End-to-end business flow

~~~text
PDF / PPTX / EML
    -> format-specific parsing
    -> common Document Object
    -> segmentation with provenance
    -> candidate fact extraction
    -> value normalisation
    -> evidence linking
    -> duplicate and temporal reconciliation
    -> conflict detection
    -> human-review routing
    -> evaluation
    -> validated knowledge storage
    -> later structured search and grounded RAG
~~~

Every stage in this flow after corpus preparation is planned. No parser or extraction system is implemented yet.

## Core user stories

1. Upload a related document batch and receive structured records.
2. Identify the current project owner, status, approved budget, target date, risks, and decisions.
3. See previous values marked as superseded.
4. See unresolved conflicts without a fabricated resolution.
5. Open the source page, slide, email body, or quoted history supporting a fact.
6. Review low-confidence, unsupported, or conflicting results.
7. Later query validated knowledge through structured search or grounded RAG.

## MVP boundaries

- Three supported formats only.
- Local-first processing.
- Public and synthetic data only.
- No OCR.
- No confidential mailboxes.
- No production records management.
- No automated high-stakes decisions.
- No RAG before extraction evaluation.
- No cloud work before local evaluation.

## Business value

The intended value is:

- reducing manual document consolidation;
- separating current information from stale information;
- making disagreement visible;
- preserving provenance;
- creating reusable structured knowledge;
- reducing unsupported summarisation.

No measured time saving or production impact is claimed.
