# Stage 2 Ingestion Acceptance Report

## Scope

Stage 2 delivered and validated:

- Common Document Object v0.1;
- PDF, PPTX, and plain-text EML parsers;
- single-document ingestion CLI;
- manifest-driven batch ingestion and machine-readable reports;
- nine-source development validation;
- six-source first held-out validation;
- full 15-source frozen-corpus validation.

No extraction or downstream product layer is included in this decision.

## Frozen corpus results

The full validation used parser commit `71148262f094d54ec7d95e45958bd1aaefc64793` and corpus version `stage1-corpus-v1.0`.

- Total sources: 15
- Successful sources: 15
- `success`: 13
- `success_with_warnings`: 2
- Failed: 0
- Checksum matches: 15/15
- JSON model revalidation: 15/15
- Correct source-format classification: 15/15
- Warning sources: S010 and S011

| Format | Sources | Blocks |
| --- | ---: | ---: |
| PDF | 7 | 379 |
| PPTX | 2 | 82 |
| EML | 6 | 49 |
| **Total** | **15** | **510** |

All generated documents and reports remain under ignored `artifacts/ingestion/` paths and are untracked.

## Acceptance gates

| Stage 2 gate | Result | Evidence |
| --- | --- | --- |
| 15/15 frozen sources ingested successfully | passed | 15 successful, 0 failed |
| 100% schema-valid Common Document Objects | passed | 15/15 JSON outputs revalidated |
| 100% correct source-format classification | passed | 15/15 outputs matched the frozen manifests |
| 100% PPTX slide-number preservation | passed | S010 retained slides 1-7; S011 retained slides 1-8, with blocks on every slide |
| 100% EML supported-header preservation | passed | All six EML sources retained every present supported header; Message-ID, date, and sender were retained for 6/6, with reply/reference headers retained when present |
| Explicit structured errors | passed | Unit tests cover manifest errors, unsupported inputs, parser failures, checksum mismatch, and CLI exit codes |
| No batch crash | passed | Per-source failure-isolation tests passed; production validation completed all 15 items |

Every required Stage 2 acceptance gate passed.

## Warning and failure taxonomy

| Category | Source count | Observed result |
| --- | ---: | --- |
| Blank page | 0 | No frozen source produced a blank-page warning |
| Skipped PPTX object | 2 | S010 summarised 7 objects; S011 summarised 11 objects |
| Attachment skipped | 0 | No frozen EML attachment warning |
| Metadata issue | 0 | None observed |
| Parser error | 0 | None observed |
| Checksum mismatch | 0 | All 15 matched |
| Other | 0 | None observed |

The two PPTX warnings reflect documented non-goals rather than parse failures. The skipped objects were empty or decorative auto-shapes and lines; no chart, image, SmartArt, or diagram interpretation was claimed.

## Limitations

- `pypdf` reading order may not represent intended multi-column or visual reading order.
- OCR is not implemented.
- PDF tables are not semantically reconstructed.
- PPTX order is a top-left spatial approximation.
- Charts, SmartArt, images, diagrams, and embedded objects are not interpreted.
- EML quoted-history detection is separator-based.
- Only plain-text EML bodies are supported.
- Attachments are not ingested.
- The corpus is small and cannot represent enterprise-scale format diversity.

## Stage 2 decision

Stage 2 is complete because every required ingestion acceptance gate passed on `stage1-corpus-v1.0`.

The next stage is Stage 3 baseline and structured extraction. No fact extraction implementation or extraction result exists yet.

## Claim boundary

The project may now claim:

- all 15 frozen sources parsed into schema-valid, provenance-preserving JSON;
- format-general development and held-out ingestion validation;
- deterministic manifest-driven batch reporting with per-source failure isolation.

It may not claim:

- extraction accuracy;
- current/superseded classification;
- conflict detection;
- evidence alignment of extracted facts;
- LLM performance;
- RAG;
- production readiness.
