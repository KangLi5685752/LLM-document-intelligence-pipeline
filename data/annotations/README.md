# Public-PDF Annotations

This directory contains the versioned Stage 3A public-PDF annotation draft:

- `public_gold_facts_v0.1.jsonl`: exactly 35 evidence-linked candidate-fact labels for S001-S007;
- `public_gold_cases_v0.1.jsonl`: ambiguous, unsupported, and missing-value challenge cases.

Every record is an AI-assisted draft created through local source review. The files are structurally validated, but they are not approved public gold until the project owner records review decisions and updates accepted fact records to `owner_verified`.

## Validation inputs

Validation requires fresh Stage 2 `ParsedDocument` JSON. Generate it under the ignored artifacts directory with the frozen parser:

~~~powershell
python -m document_intelligence.ingestion.batch_cli --output-root artifacts/annotations/public_gold_parsed --split all --parser-commit 71148262f094d54ec7d95e45958bd1aaefc64793 --run-type full_corpus_validation --report artifacts/annotations/public_gold_ingestion_report.json
~~~

The batch processes the complete frozen corpus, but annotation validation reads only S001-S007.

~~~powershell
python -m document_intelligence.extraction.annotation_cli --parsed-root artifacts/annotations/public_gold_parsed --report artifacts/annotations/public_gold_validation_report.json
~~~

Generated `ParsedDocument` files and validation reports remain ignored and must not be committed. The validator uses `corpus_split.csv`, the two public annotation JSONL files, and S001-S007 parsed outputs. It does not read `synthetic_ground_truth.jsonl`, use the network, or call an LLM.

## Review boundary

Structural validation checks schemas, counts, source assignments, predicates, evidence blocks, page numbers, excerpts, and normalized-value types. It does not establish annotation correctness or owner approval. Complete the deterministic sample in `docs/public_gold_owner_review.md`, correct rejected or ambiguous records, record owner review, and freeze a later approved version before claiming public-gold extraction results.
