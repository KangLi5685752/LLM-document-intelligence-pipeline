# Public-PDF Annotations

This directory contains frozen `public-gold-v0.1`:

- `public_gold_facts_v0.1.jsonl`: 35 owner-verified, evidence-linked facts for S001-S007;
- `public_gold_cases_v0.1.jsonl`: six owner-verified ambiguity, unsupported-claim and missing-value cases;
- `public_gold_v0.1_manifest.json`: fixed versions, inventory and uppercase SHA-256 hashes for both JSONL files.

The project-owner review was completed on 2026-07-22. Review decisions are documented in `docs/public_gold_owner_decision_log.md`; dataset identity and change controls are documented in `docs/public_gold_freeze.md`.

## Hash protection

Freeze tests recompute both JSONL SHA-256 values and compare them with the manifest. Any byte-level change to a frozen JSONL file fails the test. Semantic annotation changes, evidence changes, review-status changes and interpretation-changing owner-note changes require a new dataset version and updated manifest; do not silently rewrite v0.1.

## Validation inputs

Regenerate Stage 2 `ParsedDocument` JSON under the ignored artifacts directory with the frozen parser:

~~~powershell
python -m document_intelligence.ingestion.batch_cli --output-root artifacts/annotations/public_gold_parsed --split all --parser-commit 71148262f094d54ec7d95e45958bd1aaefc64793 --run-type full_corpus_validation --report artifacts/annotations/public_gold_ingestion_report.json
~~~

Run freeze-level validation:

~~~powershell
python -m document_intelligence.extraction.annotation_cli --parsed-root artifacts/annotations/public_gold_parsed --report artifacts/annotations/public_gold_validation_report.json --require-owner-verified
~~~

Generated ParsedDocument files and reports remain ignored and must not be committed. Validation reads S001-S007 parsed outputs, `corpus_split.csv` and the two frozen JSONL files. It does not read `synthetic_ground_truth.jsonl`, use the network or call an LLM.

## Development and held-out boundary

Development labels may be loaded for Stage 3B deterministic-baseline design and development evaluation. Held-out facts and challenge cases must not be loaded by rule-design code, rule tests or tuning. They may be accessed only after the baseline experiment version, rules and code are frozen.

## Claim boundary

The frozen asset is owner reviewed and structurally evidence-valid. It does not constitute an extraction result, final fact-state dataset or implementation of an extractor or reconciliation layer.
