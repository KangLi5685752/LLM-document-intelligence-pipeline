# Planned High-Level Architecture

## Current implementation status

Implemented repository and corpus-control layers:

- Stage 0 repository foundation;
- Stage 1 source strategy;
- public-PDF audit;
- deterministic PDF audit utility;
- synthetic PPTX and EML fixtures;
- synthetic ground truth;
- frozen corpus split;
- product and evaluation contracts.

Stage 2 and every later pipeline component remain planned. No parser, common Document Object, extraction system, or evaluation result currently exists.

Design contracts:

- [Product definition](product_definition.md)
- [Evidence-linked extraction schema](extraction_schema.md)
- [Evaluation plan](evaluation_plan.md)
- [Stage 1 corpus freeze](corpus_freeze.md)

## Planned flow

~~~text
[Implemented Stage 1 corpus] PDF / PPTX / EML documents
    -> [Planned] format-specific parsing
    -> [Planned] common Document Object
    -> [Planned] preprocessing and segmentation
    -> [Planned] baseline extraction
    -> [Planned] LLM structured extraction
    -> [Planned] schema validation
    -> [Planned] source evidence alignment
    -> [Planned] unsupported/conflict checks
    -> [Planned] human-review routing
    -> [Planned] evaluation
    -> [Planned] local storage
    -> [Planned] BigQuery
    -> [Planned] query/retrieval
    -> [Planned] grounded RAG
    -> [Planned] API/interface
    -> [Planned] Docker/Cloud Run
~~~

## Planned component responsibilities

| Component | Planned responsibility | Status |
| --- | --- | --- |
| Documents | Supply frozen PDF, PPTX, and EML corpus inputs. | Stage 1 corpus implemented |
| Format-specific parsing | Preserve format structure and source locations while reading content. | Planned |
| Common Document Object | Provide one format-neutral contract with evidence-location metadata. | Planned |
| Preprocessing and segmentation | Normalise and divide content without losing provenance. | Planned |
| Baseline extraction | Supply a deterministic comparison point for defined fields. | Planned |
| LLM structured extraction | Produce schema-targeted candidate records through one future provider. | Planned |
| Schema validation | Reject or report structurally invalid candidate records. | Planned |
| Source evidence alignment | Connect extracted claims to page, slide, or section-level evidence. | Planned |
| Unsupported/conflict checks | Detect missing support, contradictions, and ambiguous claims. | Planned |
| Human-review routing | Send defined uncertain cases to an inspectable review queue. | Planned |
| Evaluation | Compare extraction, validity, evidence, and routing behaviour on labelled data. | Planned |
| Local storage | Persist prototype inputs and validated outputs locally. | Planned |
| BigQuery | Provide a later analytical store only after local evaluation. | Planned |
| Query/retrieval | Support structured search over validated knowledge. | Planned |
| Grounded RAG | Generate answers grounded in validated records and cited evidence. | Planned |
| API/interface | Expose evaluated capabilities through a later user-facing boundary. | Planned |
| Docker/Cloud Run | Package and deploy only after local behaviour is justified. | Planned |
