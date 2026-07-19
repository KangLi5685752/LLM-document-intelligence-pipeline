# Stage 1B PDF Audit Utility Validation

## Purpose

The utility automates deterministic technical checks during corpus audit. It is a local screening and evidence-reconciliation tool, not the Stage 2 production ingestion parser.

## Utility scope

The utility automates:

- SHA-256 calculation;
- file-size recording;
- PDF page counting;
- per-page extracted-text character counts without saving page text;
- zero-text page warnings;
- near-empty page warnings;
- deterministic first, middle, and final sample-page selection;
- screening-level probable scanned-page risk based on zero-text pages.

The utility does not automate:

- official-source verification;
- licence interpretation;
- third-party-rights decisions;
- table reconstruction;
- image interpretation;
- OCR;
- semantic extraction-quality assessment;
- corpus approval.

## Pilot validation

The observed values below were read from the locally generated, Git-ignored audit CSV after running the utility over the three pilot files.

| source_id | filename | expected_sha256 | observed_sha256 | expected_file_size_bytes | observed_file_size_bytes | expected_page_count | observed_page_count | match_status |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| S001 | S001_ai_opportunities_action_plan_2025.pdf | DE68EED45514303E2E0E4280B5CDE8B7167AAA17D6F69E1B0716765AE4DE807D | DE68EED45514303E2E0E4280B5CDE8B7167AAA17D6F69E1B0716765AE4DE807D | 1564579 | 1564579 | 26 | 26 | match |
| S002 | S002_ai_opportunities_action_plan_government_response_2025.pdf | BC586580B66B7E29B6AB824408055B168F83909D3CFECFDA085EBF1E418E5358 | BC586580B66B7E29B6AB824408055B168F83909D3CFECFDA085EBF1E418E5358 | 259611 | 259611 | 22 | 22 | match |
| S003 | S003_ai_opportunities_action_plan_one_year_on_2026.pdf | ACC700C1D245171B413BE248E2D1B21C07666F6891AA273F271D19E64CE2AE6F | ACC700C1D245171B413BE248E2D1B21C07666F6891AA273F271D19E64CE2AE6F | 442845 | 442845 | 16 | 16 | match |

## Text-density observations

Empty cells represent empty fields in the generated CSV.

| source_id | total_text_chars | minimum_page_text_chars | maximum_page_text_chars | mean_page_text_chars | pages_with_no_text | near_empty_pages | probable_scanned_page_risk | warnings |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| S001 | 57729 | 7 | 3363 | 2220.35 |  | 1 | none_observed | Near-empty pages (<50 chars): 1 |
| S002 | 36417 | 57 | 3173 | 1655.32 |  |  | none_observed |  |
| S003 | 28680 | 73 | 3177 | 1792.50 |  |  | none_observed |  |

S001's low-density cover page generated a warning but did not cause audit failure. A near-empty page is a review prompt, not evidence of parser failure.

## Result

- All three SHA-256 values matched the recorded evidence.
- All three file sizes matched the recorded evidence.
- All three page counts matched the recorded evidence.
- All three documents were processed successfully.

The generated audit contained three unique rows in deterministic filename order and no extracted full-text field.

## Limitations

- Extracted character counts are not extraction-accuracy evaluation.
- Zero extracted text is only a scan-risk indicator, not definitive scan detection.
- Tables, diagrams, layout, and reading order require later parser-specific evaluation.
- The utility does not replace manual source verification or licence and rights review.
- The pilot covers three related documents and does not establish production readiness or general corpus performance.
