# Stage 1B Pilot Source Audit Report

## Scope

The Stage 1B pilot covered S001–S003 only. It reviewed:

- source and direct-file verification;
- file integrity;
- expected and actual page counts;
- text selectability and searchability;
- document structure;
- document-level licence notices;
- visual and third-party-material caveats;
- technical extraction risks.

The pilot did not implement a parser, perform LLM extraction, add retrieval, or conduct extraction evaluation.

## Verified sources

| Source ID | Official direct PDF URL | Official host | Local filename | Page count | Corpus decision |
| --- | --- | --- | --- | ---: | --- |
| S001 | https://assets.publishing.service.gov.uk/media/67851771f0528401055d2329/ai_opportunities_action_plan.pdf | assets.publishing.service.gov.uk | S001_ai_opportunities_action_plan_2025.pdf | 26 | approved for documented local corpus and future evaluation use |
| S002 | https://assets.publishing.service.gov.uk/media/678639913a9388161c5d2376/ai_opportunities_action_plan_government_repsonse.pdf | assets.publishing.service.gov.uk | S002_ai_opportunities_action_plan_government_response_2025.pdf | 22 | approved for documented local corpus and future evaluation use |
| S003 | https://assets.publishing.service.gov.uk/media/697a36873c71d838df6bd400/ai_opportunities_action_plan-one-year-on.pdf | assets.publishing.service.gov.uk | S003_ai_opportunities_action_plan_one_year_on_2026.pdf | 16 | approved for documented local corpus and future evaluation use |

Original PDF redistribution is not approved. The files remain local under data/raw and must not be committed.

## Integrity results

| Source ID | Page count | File size bytes | SHA-256 | Text selectable/searchable | Result |
| --- | ---: | ---: | --- | --- | --- |
| S001 | 26 | 1564579 | DE68EED45514303E2E0E4280B5CDE8B7167AAA17D6F69E1B0716765AE4DE807D | yes / yes | Opened successfully; actual and expected page counts matched; searchable and selectable text was present; no scanned-page dependency was observed. |
| S002 | 22 | 259611 | BC586580B66B7E29B6AB824408055B168F83909D3CFECFDA085EBF1E418E5358 | yes / yes | Opened successfully; actual and expected page counts matched; searchable and selectable text was present; no scanned-page dependency was observed. |
| S003 | 16 | 442845 | ACC700C1D245171B413BE248E2D1B21C07666F6891AA273F271D19E64CE2AE6F | yes / yes | Opened successfully; actual and expected page counts matched; searchable and selectable text was present; no scanned-page dependency was observed. |

## Structural findings

- **S001:** medium-complexity single-column report with structured headings, numbered recommendations, bullet lists, footnotes, and a simple process diagram.
- **S002:** high-complexity, table-heavy government response. Pages 9–21 contain recommendation-response-timeline tables and present the main parser risk because plain text extraction may lose row and column relationships.
- **S003:** medium-complexity progress report with headings, bullet lists, and large official portrait photographs on pages 4 and 6. The photographs do not prevent extraction of surrounding text.

## Licence observations

- S001 and S002 contain Crown copyright 2025 and Open Government Licence v3.0 notices on PDF page 3.
- S003 contains a Crown copyright 2026 and Open Government Licence v3.0 notice on PDF page 2.
- All three notices include “except where otherwise stated”.
- Visual and third-party materials must not automatically be assumed to be covered by the document-level licence notice.
- Original PDFs and visual assets remain local and must not be committed.
- Text-based derived artefacts may be used with appropriate source attribution according to the recorded project decision; this does not extend automatically to photographs, logos, diagrams, or other visual assets.

This portfolio review is not legal advice.

## Technical recommendations

- **S001:** suitable_for_mvp.
- **S002:** suitable_with_caveats.
- **S003:** suitable_for_mvp.

S002 is retained as a table-heavy parser stress-test document rather than rejected. Its structured tables require layout-aware handling and targeted validation in a future ingestion stage.

## Evaluation leakage control

S001, S002, and S003 form one related document family: **ai_opportunities_action_plan_family**. All three must be assigned to the same future development or held-out split to reduce cross-document information leakage.

For this pilot, the entire family should be used as development material rather than held-out evaluation material because it informed the audit protocol and initial technical planning.

## Current limitations

- Only three related documents have completed Stage 1B review.
- The pilot is concentrated on one publisher and one policy family.
- No automated corpus-audit utility has yet been implemented.
- No parser, extraction model, retrieval capability, or evaluation result exists.
- Current licence decisions apply to documented local use and do not authorise unrestricted redistribution of original files or visual assets.
- No quantitative extraction performance has been measured or claimed.
