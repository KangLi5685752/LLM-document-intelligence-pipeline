# Planned High-Level Architecture

## Current implementation status

Implemented repository, corpus-control, and Stage 2 ingestion layers:

- Stage 0 repository foundation;
- Stage 1 source strategy;
- public-PDF audit;
- deterministic PDF audit utility;
- synthetic PPTX and EML fixtures;
- synthetic ground truth;
- frozen corpus split;
- product and evaluation contracts;
- Common Document Object v0.1;
- PDF, PPTX, and EML parsers;
- single-document dispatch and JSON serialisation;
- manifest-driven batch ingestion with per-source failure isolation;
- development, held-out, and full frozen-corpus validation.

Stage 2 ingestion is complete for `stage1-corpus-v1.0`. No semantic segmentation, extraction, reconciliation, extraction evaluation, storage, retrieval, interface, or deployment layer exists.

Design contracts:

- [Product definition](product_definition.md)
- [Evidence-linked extraction schema](extraction_schema.md)
- [Evaluation plan](evaluation_plan.md)
- [Stage 1 corpus freeze](corpus_freeze.md)
- [Stage 2 ingestion design](stage_2_ingestion_design.md)
- [Stage 2A development validation](stage_2a_development_validation.md)
- [Stage 2B held-out validation](stage_2b_held_out_validation.md)
- [Stage 2 acceptance report](stage_2_acceptance_report.md)

## Ingestion and extraction boundary

- **Ingestion output:** implemented `ParsedDocument` and `DocumentBlock` records containing normalized source text, metadata, warnings, and provenance.
- **Extraction output:** future `FactRecord`, `ConflictRecord`, and `ReviewItem` records derived from ingestion output and evaluated separately.

## Planned flow

~~~text
[Implemented Stage 1 corpus] PDF / PPTX / EML documents
    -> [Implemented Stage 2] manifest-driven single/batch dispatch
    -> [Implemented Stage 2] format-specific parsing
    -> [Implemented Stage 2] Common Document Object v0.1 and JSON serialisation
    -> [Planned] preprocessing beyond basic text normalisation
    -> [Planned] semantic segmentation
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
| Batch ingestion | Join frozen manifests, resolve format paths, isolate failures, validate checksums, and produce machine-readable reports. | Stage 2 implemented and validated on 15 sources |
| Format-specific parsing | Preserve page, slide, shape, header, body, and quoted-history locations while reading content. | Stage 2 implemented and validated on 15 sources |
| Common Document Object | Provide the strict v0.1 `ParsedDocument` and `DocumentBlock` JSON contract. | Stage 2 implemented |
| Preprocessing and segmentation | Extend basic line-ending and trailing-space normalisation and divide content without losing provenance. | Planned |
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
