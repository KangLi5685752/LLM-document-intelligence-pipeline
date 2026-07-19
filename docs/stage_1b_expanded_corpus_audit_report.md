# Stage 1B Expanded Public-PDF Corpus Audit Report

## Scope

This review covered S004-S007 and expanded the previously audited S001-S003 public-PDF corpus. It reviewed verified official source files, file integrity, hashes, sizes, page counts, screening-level text density, document structure, licence evidence, third-party-material risks, and technical suitability.

The review did not implement Stage 2 ingestion, OCR, table reconstruction, image interpretation, semantic extraction, LLM extraction, extraction evaluation, retrieval, or RAG.

## Automated integrity results

The values below were read from the locally generated `artifacts/audits/stage_1b_expanded_pdf_audit.csv`. Empty screening fields mean that the deterministic audit recorded no matching pages; they are not substituted counts.

| source_id | filename | SHA-256 match | size match | expected page count | observed page count | total_text_chars | minimum_page_text_chars | maximum_page_text_chars | mean_page_text_chars | pages_with_no_text | near_empty_pages | probable_scanned_page_risk | audit status |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| S004 | `S004_ai_playbook_uk_government_2025.pdf` | yes | yes | 118 | 118 | 286788 | 69 | 3607 | 2430.41 | empty | empty | none_observed | completed |
| S005 | `S005_scotland_ai_strategy_2026_2031.pdf` | yes | yes | 58 | 58 | 102543 | 26 | 2978 | 1767.98 | empty | 1;57 | none_observed | completed |
| S006 | `S006_ai_adoption_research_2026.pdf` | yes | yes | 61 | 61 | 120136 | 32 | 3234 | 1969.44 | empty | 2 | none_observed | completed |
| S007 | `S007_ai_and_public_standards_report_2020.pdf` | yes | yes | 78 | 78 | 220130 | 157 | 4302 | 2822.18 | empty | empty | none_observed | completed |

All four files matched the expected SHA-256, byte-size, and page-count values. The seven-file batch covering S001-S007 completed successfully with no failed audits.

## Structural findings

- S004 is a long, primarily single-column playbook with diagrams, tables, structured risk scenarios, and case-study appendices.
- S005 is a highly visual and multi-column strategy with photographs, cards, and complex diagrams.
- S006 is a survey research report with many charts, percentages, tables, appendices, and anonymised quotations.
- S007 is a two-column governance report with recommendation blocks, long quotations, dense footnotes, and methodology tables.

## Licence and rights observations

- S004 has an explicit Open Government Licence v3.0 notice on PDF page 117.
- S005 has an explicit Open Government Licence v3.0 notice and third-party warning on PDF page 58.
- S005's official website excludes graphic assets from its general Open Government Licence statement.
- S006 relies on the official HTML publication and GOV.UK notice because no separate PDF licence notice was observed.
- S007 relies on the official GOV.UK landing-page notice because no separate PDF licence notice was observed.
- All original PDFs and visual assets remain local and uncommitted.
- Extensive third-party quotations must not be treated as unrestricted reusable material.

Approval means approval for documented local corpus and future evaluation use, not unrestricted redistribution. `approved_local_only` requires the original PDFs to remain under the ignored `data/raw` directory. Permission to derive text applies only with attribution and does not automatically extend to graphic assets, photographs, externally owned diagrams, or extensive third-party quotations. This portfolio review is not legal advice.

## Technical recommendations

S004, S005, S006, and S007 are each assessed as `suitable_with_caveats`. The caveats increase their evaluation value by adding realistic reading-order, visual-relationship, table, chart, footnote, and quotation-context challenges; they do not require rejection from the documented local corpus.

## Corpus diversity

S004-S007 add a long government guidance playbook, a highly visual devolved-government strategy, a quantitative and qualitative research report, and an older governance and public-standards report. Together they broaden publisher, publication-date, document-role, and layout coverage beyond S001-S003.

## Future split candidates

The final split is not yet frozen. The provisional recommendation is:

- Development candidates: S001-S004 and S006.
- Held-out candidates: S005 and S007.

S001-S003 belong to one related document family and must remain together in one split. S005 tests visual and multi-column generalisation. S007 tests a different publisher, date, governance role, and two-column reading order. Final split assignment must be frozen before extraction evaluation and after the synthetic challenge set is registered.

## Remaining Stage 1B work

Public-PDF source review for S001-S007 is complete, but Stage 1B is not complete. Remaining work comprises:

- Synthetic PPTX challenge documents.
- Synthetic email-style challenge documents.
- Synthetic-source manifest entries.
- A final document-family and split plan.
- Corpus freeze before Stage 2 implementation.
