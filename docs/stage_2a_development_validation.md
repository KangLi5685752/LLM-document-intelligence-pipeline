# Stage 2A Development-Source Validation

## Scope

Validation covered the nine frozen development sources only:

- S001, S002, S003, S004, and S006 public PDFs;
- S010 synthetic PPTX;
- S012, S013, and S014 synthetic EML messages.

Each source was processed separately through the module CLI. JSON outputs were written under the ignored `artifacts/ingestion/stage_2a_development/` directory and revalidated with `ParsedDocument.model_validate_json(...)`.

## Parser version or commit placeholder

- Common Document Object schema: `0.1`
- Parser commit: `71148262f094d54ec7d95e45958bd1aaefc64793`
- Corpus version: `stage1-corpus-v1.0`
- Validation date: 2026-07-21

## Development source inventory

| Source | Format | Corpus role |
| --- | --- | --- |
| S001 | PDF | Development public realism |
| S002 | PDF | Development public realism |
| S003 | PDF | Development public realism |
| S004 | PDF | Development public realism |
| S006 | PDF | Development public realism |
| S010 | PPTX | Development synthetic benchmark |
| S012 | EML | Development synthetic benchmark |
| S013 | EML | Development synthetic benchmark |
| S014 | EML | Development synthetic benchmark |

## Results table

| Source | Format | Parse status | Blocks | Warnings | Pages/slides | Required provenance check |
| --- | --- | --- | ---: | ---: | ---: | --- |
| S001 | PDF | success | 26 | 0 | 26 pages | 1-based page blocks retained |
| S002 | PDF | success | 22 | 0 | 22 pages | 1-based page blocks retained |
| S003 | PDF | success | 16 | 0 | 16 pages | 1-based page blocks retained |
| S004 | PDF | success | 118 | 0 | 118 pages | 1-based page blocks retained |
| S006 | PDF | success | 61 | 0 | 61 pages | 1-based page blocks retained |
| S010 | PPTX | success_with_warnings | 36 | 1 | 7 slides | Blocks cover slides 1-7 |
| S012 | EML | success | 6 | 0 | n/a | Message-ID retained; no quoted-history block expected |
| S013 | EML | success | 10 | 0 | n/a | Message-ID, In-Reply-To, References, and quoted history retained |
| S014 | EML | success | 9 | 0 | n/a | Message-ID, In-Reply-To, ordered References, and quoted history retained |

Observed aggregate checks:

- 9 of 9 sources parsed without a batch crash;
- 9 of 9 JSON documents passed model revalidation;
- 9 of 9 uppercase SHA-256 values matched `source_register.csv`;
- all five PDFs retained exactly one 1-based block per page;
- S010 retained blocks on all seven 1-based slides;
- S012-S014 retained their present supported headers;
- S013-S014 separated quoted history from the current body;
- no held-out source was processed.

## Warning summary

S010 produced one document-level warning summarising seven skipped non-text slide objects: three empty or decorative auto-shapes and four lines. The parser did not interpret these objects and did not emit one warning per object. No other development source produced a parser warning.

## Known parser limitations

- PDF output follows `pypdf` page text and reading order; it does not perform OCR, column reconstruction, or semantic table recovery.
- PPTX reading order is a top-left spatial approximation. Charts, images, SmartArt, diagrams, and decorative objects are not interpreted.
- EML support is plain-text only. Quoted-history detection uses documented separators and cannot cover every email client convention.
- Attachment content is not ingested.
- Ingestion blocks are not facts and carry no current, superseded, duplicate, entity, or conflict classifications.

## Acceptance decision

Stage 2A development-source acceptance passed: 9/9 sources parsed, all outputs revalidated, all checksums matched, and the required page, slide, header, and quoted-history provenance checks passed.

This does not complete Stage 2. Held-out and full frozen-corpus validation remain pending.

## Held-out sources not yet evaluated

S005, S007, S011, and S015-S017 were not parsed or inspected for Stage 2A validation. They remain reserved for Stage 2B format-general validation after the parser commit is frozen.

## Claim boundary

The project may claim an initial, validated development-source ingestion boundary for PDF, PPTX, and plain-text EML. It may not claim complete frozen-corpus parser coverage, fact extraction, extraction accuracy, reconciliation, conflict detection, LLM performance, retrieval, RAG, or production readiness.
