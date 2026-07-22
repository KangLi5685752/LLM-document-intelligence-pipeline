# Evaluation Plan

All targets in this document are design acceptance gates, not achieved results.

## Evaluation questions

1. Can all supported documents be ingested without losing provenance?
2. Can the system extract expected facts into a valid schema?
3. Can it distinguish current and superseded facts?
4. Can it preserve unresolved conflicts?
5. Can every accepted fact be linked to valid evidence?
6. Can unsupported or ambiguous outputs be routed for review?
7. Does an LLM-assisted approach improve over a reasonable deterministic baseline?

## Evaluation layers

### Parsing evaluation

Metrics:

- document-ingestion success rate;
- non-empty output rate;
- metadata completeness;
- page- or slide-locator preservation;
- email-header preservation;
- quoted-history separation;
- parser-warning rate;
- parser-error taxonomy.

Stage 2 acceptance gates:

- 15 of 15 frozen sources ingested successfully;
- 100% schema-valid common Document Objects;
- 100% correct source-format classification;
- 100% PPTX slide-number preservation;
- 100% EML Message-ID, date, sender, and thread-header preservation;
- no test reads ignored `data/raw` unless explicitly running local corpus validation;
- failures return explicit structured errors rather than crashing the batch.

### Extraction evaluation

Fact matching uses:

- normalized subject;
- predicate;
- normalized value;
- predicate-scoped qualifiers when they materially define the metric or recommendation context;
- fact state.

Metrics:

- current-fact precision;
- current-fact recall;
- current-fact F1;
- normalized-value exact match;
- superseded-fact recall;
- duplicate-group accuracy;
- schema-valid output rate;
- unsupported current-fact rate.

### Conflict evaluation

Metrics:

- conflict precision;
- conflict recall;
- unresolved-conflict preservation rate;
- false-resolution count;
- candidate-value coverage.

Held-out synthetic gates:

- both designed held-out conflict families detected;
- zero fabricated conflict resolutions;
- all candidate values retained;
- all unresolved conflicts routed to review.

Exact numerators and denominators must be reported because the benchmark is small.

### Evidence evaluation

Metrics:

- evidence-source accuracy;
- evidence-location accuracy;
- evidence coverage;
- unsupported-claim count.

Gates:

- at least 90% evidence-location accuracy on synthetic ground truth;
- zero unsupported current facts on held-out synthetic sources.

### Review-routing evaluation

Metrics:

- review-routing recall;
- review-routing precision;
- unresolved-conflict routing recall;
- missing-evidence routing recall.

Gates:

- 100% of unresolved conflicts routed to review;
- 100% of unsupported current facts routed or rejected;
- over-routing reported as an error, not as harmless conservatism.

## Synthetic benchmark targets

| Measure | Design acceptance gate |
| --- | ---: |
| Final schema-valid rate | 100% |
| Held-out current-fact precision | at least 0.90 |
| Held-out current-fact recall | at least 0.85 |
| Superseded-fact recall | at least 0.80 |
| Evidence-location accuracy | at least 0.90 |
| Held-out unresolved-conflict recall | 1.00 |
| False conflict resolutions | 0 |
| Unsupported current facts on held-out synthetic data | 0 |

These are acceptance gates and not current results.

## Public-PDF evaluation plan

The seven public PDFs provide realistic format and language coverage. Stage 3A preparation and project-owner review are complete: frozen `public-gold-v0.1` supplies 35 owner-verified facts, six owner-verified challenge cases, runtime predicate-use enforcement, structured qualifiers and checksummed file identity.

The frozen asset contains exactly 35 fact annotations:

- S001: 5;
- S002: 5;
- S003: 4;
- S004: 6;
- S005: 5;
- S006: 5;
- S007: 5.

This yields 25 development facts and 10 held-out facts. The frozen asset also records ambiguous, unsupported, and missing-value challenge cases with page-level evidence.

All 35 facts and six challenge cases are `owner_verified`, with zero drafts or rejections. This completes evaluation-data preparation, not extraction evaluation. No extractor has run and no extraction metric or public-gold result exists.

Limitations:

- one annotator;
- no inter-annotator agreement;
- interpretation bias;
- small sample;
- public documents are not a representative enterprise corpus.

Stage 3A did not run extraction. During Stage 3B, held-out labels and held-out challenge cases must not be loaded during deterministic rule design, rule tests or tuning.

## Development and held-out use

- Development sources may be used for parser debugging, rule design, and prompt iteration.
- Held-out facts and challenge cases may be loaded only for evaluation after the baseline experiment version, rules and code are frozen.
- No rule or prompt may be changed in response to a held-out result without declaring a new experiment cycle.
- Family members cannot cross splits.
- Results must be reported separately for development and held-out data.

## Baselines and proposed system

### Baseline A

Deterministic extraction using:

- metadata;
- regex;
- date and money patterns;
- heading and table cues;
- fixed keyword rules.

### Baseline B

Basic structured LLM extraction using:

- a fixed JSON target;
- limited validation;
- no advanced reconciliation.

### Proposed system

- versioned schema;
- structured extraction;
- evidence requirement;
- normalization;
- duplicate detection;
- temporal and status reconciliation;
- conflict checks;
- bounded retry;
- review routing.

All approaches must use the same frozen corpus and evaluation labels.

## Reproducibility

Later reports must record:

- corpus version;
- split version;
- schema version;
- code commit;
- parser version;
- prompt version;
- model/provider version;
- run date;
- mock or live mode;
- cost and latency where applicable.

## Failure analysis

Qualitative failure analysis must use categories including:

- parser loss;
- reading-order error;
- table-relationship loss;
- email quoted-history confusion;
- alias failure;
- value-normalisation error;
- stale fact selected as current;
- false conflict;
- missed conflict;
- unsupported value;
- incorrect evidence;
- over-routing;
- under-routing.
