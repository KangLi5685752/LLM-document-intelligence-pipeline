# Stage 2B Held-Out Ingestion Validation

## Scope

Stage 2B performed the first format- and provenance-level ingestion run over the six frozen held-out sources:

- S005 and S007 public PDFs;
- S011 synthetic PPTX;
- S015, S016, and S017 synthetic EML messages.

The run evaluated parser structure, checksums, schema validity, page and slide preservation, supported message headers, and quoted-history separation. It did not evaluate extracted business facts.

## Frozen parser version

- Parser commit: `71148262f094d54ec7d95e45958bd1aaefc64793`
- Common Document Object schema: `0.1`
- Corpus version: `stage1-corpus-v1.0`

This parser commit was frozen before any held-out source was processed.

## First-run protocol

The first run used:

~~~powershell
python -m document_intelligence.ingestion.batch_cli --output-root artifacts/ingestion/stage_2b_held_out --split held_out --parser-commit 71148262f094d54ec7d95e45958bd1aaefc64793 --run-type held_out_first_run --report artifacts/ingestion/stage_2b_held_out_report.json
~~~

The generated report and six parsed documents remain local under ignored `artifacts/ingestion/` paths. The first-run report was preserved and was not overwritten by later validation.

## Held-out inventory

| Source | Format | Family | Split |
| --- | --- | --- | --- |
| S005 | PDF | F-PUB-003 | held_out |
| S007 | PDF | F-PUB-005 | held_out |
| S011 | PPTX | F-SYN-002 | held_out |
| S015 | EML | F-SYN-004 | held_out |
| S016 | EML | F-SYN-004 | held_out |
| S017 | EML | F-SYN-004 | held_out |

## First-run results table

| Source | Format | Status | Blocks | Warnings | Pages/slides | Key provenance checks | Checksum |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| S005 | PDF | success | 58 | 0 | 58 pages | Page blocks and locators exactly 1-58 | matched |
| S007 | PDF | success | 78 | 0 | 78 pages | Page blocks and locators exactly 1-78 | matched |
| S011 | PPTX | success_with_warnings | 46 | 1 | 8 slides | At least one block retained on every slide 1-8 | matched |
| S015 | EML | success | 6 | 0 | n/a | Message-ID retained; no quoted-history block expected | matched |
| S016 | EML | success | 9 | 0 | n/a | Message-ID, In-Reply-To, References, and quoted history retained | matched |
| S017 | EML | success | 9 | 0 | n/a | Message-ID, In-Reply-To, ordered References, and quoted history retained | matched |

All six output JSON documents passed `ParsedDocument.model_validate_json(...)`.

## Warning summary

S011 produced one document warning: 11 unsupported or non-text slide objects were skipped and summarised. The count comprised five empty or decorative auto-shapes and six lines. The parser retained supported title, text, and table blocks and did not attempt to interpret the skipped visuals.

No blank-page, attachment, metadata, parser, or checksum warning occurred in the held-out run.

## Failures observed

None. All six sources parsed successfully on the first run, so there was no original failure to classify or repair.

## Parser changes after first run

None. No format-general parser defect was observed, and no parser file was changed after the first held-out run.

## Rerun results if applicable

Not applicable. Because the first run passed and the parser remained unchanged, no after-fix held-out rerun was required. The same six sources were subsequently included in the separate full-corpus validation run.

## Leakage-control statement

- `synthetic_ground_truth.jsonl` was not loaded.
- No extracted business-value assertion was used.
- No source-ID, filename, held-out keyword, or expected-value rule was introduced.
- Checks were limited to format, provenance, checksum, schema, warning, and thread-structure behavior.
- The first-run evidence was preserved before full-corpus validation.

## Limitations

- The held-out set contains only six sources and is procedural rather than blind.
- PDF reading order remains dependent on `pypdf`.
- PPTX reading order remains a spatial approximation, and unsupported visuals are not interpreted.
- EML quoted-history separation remains separator-based and plain-text only.
- The validation establishes ingestion behavior, not fact extraction quality.

## Acceptance decision

Held-out Stage 2B ingestion passed: 6/6 sources parsed, 6/6 outputs revalidated, 6/6 checksums matched, required provenance checks passed, and no parser-specific correction was needed.

## Claim boundary

The project may claim format-general held-out ingestion validation for the six frozen sources using the pre-held-out parser. It may not claim fact extraction, current/superseded classification, conflict detection, evidence alignment of extracted facts, LLM performance, RAG, or production readiness.
