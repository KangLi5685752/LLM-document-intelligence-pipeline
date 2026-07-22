# Public Gold v0.1 Freeze

## Dataset identity

`public-gold-v0.1` is the frozen Stage 3A public-PDF evaluation asset. Its machine-readable identity and inventory are recorded in `data/annotations/public_gold_v0.1_manifest.json`.

## Freeze date

The dataset was frozen on 2026-07-22 after project-owner semantic review.

## Frozen files and SHA-256 hashes

| Frozen file | SHA-256 |
| --- | --- |
| `data/annotations/public_gold_facts_v0.1.jsonl` | `8640C7C4D2E6A244661BEE73679D1AD964FEAC3BED937E7399D39AC75AFE96EC` |
| `data/annotations/public_gold_cases_v0.1.jsonl` | `435AEFDB93EBFEC17C5CCC0D088EEBFB567B928D346CAF58C6A6692023BB7181` |

The freeze tests recompute both hashes. Any byte change to either JSONL file fails validation until an intentional new dataset version and manifest are created.

## Corpus and parser versions

- Corpus: `stage1-corpus-v1.0`
- Frozen parser commit: `71148262f094d54ec7d95e45958bd1aaefc64793`
- Ingestion schema: `0.1`

## Schema and predicate versions

- Candidate extraction schema: `0.1`
- Predicate vocabulary: `0.1`
- Fact annotation schema: `0.1`
- Challenge-case schema: `0.1`
- Freeze manifest schema: `0.1`

## Fact inventory

The freeze contains 35 owner-verified facts: 25 development and 10 held out. Source counts are S001=5, S002=5, S003=4, S004=6, S005=5, S006=5 and S007=5. Every fact retains `expected_fact_state=unknown`; reconciliation states are outside Stage 3A.

## Challenge-case inventory

The freeze contains six owner-verified cases: two ambiguous, two unsupported and two `missing_expected_value`. The challenge-case set is part of the frozen evaluation asset, not optional commentary.

## Owner-review completion

All 35 facts and all six cases were reviewed against the original PDF pages and frozen ParsedDocument evidence. Twelve facts were approved without correction and 23 were corrected before approval. Five challenge cases were approved without correction and one was corrected before approval. No record was rejected. The review was completed by one project owner; it was not independent double annotation and provides no inter-annotator agreement measure.

## Evidence-validation result

Freeze-level validation passed for all 35 facts and six cases. All declared blocks exist, pages match their block locations, and every fact excerpt occurs exactly in normalized block text. The validation uses no network call, LLM call or synthetic ground truth.

## Development/held-out controls

Development facts may be used in Stage 3B baseline design and development evaluation. Held-out facts and held-out challenge cases must not be loaded during deterministic rule design, rule tests or tuning. Held-out records may be accessed only after the baseline experiment version, rules and code are frozen.

## Allowed uses

- Design and test deterministic candidate extraction against development labels.
- Validate candidate schema, predicate use and evidence links.
- Evaluate the frozen baseline against held-out records only after the experiment freeze.
- Report limitations and error categories with the fixed inventory and hashes.

## Prohibited uses

- Loading held-out labels or cases during rule design or tuning.
- Treating `owner_verified` as independent double annotation.
- Passing gold labels to parsers or extractors as input.
- Changing frozen semantic content without a new dataset version.
- Claiming final fact states, extraction scores or product capability from annotation preparation alone.

## Version-change rules

A new dataset version is required for any change to:

- fact semantic fields;
- challenge-case semantic fields;
- evidence block or page;
- evidence excerpt;
- review status;
- owner notes that change interpretation;
- source distribution;
- split assignment;
- annotation or case schema meaning;
- predicate meaning.

Typographical-only documentation changes outside the frozen JSONL files and manifest do not require a new dataset version.

## Limitations

- Single project-owner review.
- No independent second annotator.
- No inter-annotator agreement.
- Small public-sector corpus with page-level PDF evidence.
- Held-out evaluation is procedural rather than secret blind.

## Claim boundary

`public-gold-v0.1` is frozen and evidence-valid. Candidate extraction models exist, but no deterministic extractor, LLM extractor, reconciliation implementation, extraction result or extraction metric exists yet.
