# Stage 3B Deterministic Rule Engine

## Status

Stage 3B.3 implements deterministic candidate generation for `deterministic-baseline-v0.1`. No public-gold development score exists yet, and no held-out extraction has run. Stage 3B.4 development evaluation, error analysis and baseline freeze is next.

## Purpose

The engine provides a transparent and reproducible baseline for later comparison with structured LLM extraction. Its rules are intentionally inspectable and conservative. Their existence is not a claim of best performance, production readiness or superiority to an LLM.

## Runtime boundary

The runtime flow is:

`ParsedDocument` only -> deterministic rules -> `CandidateExtractionResult`

The public extractor accepts one validated `ParsedDocument` object. It does not accept a path, reopen a source file, call a network service or read annotation data. Gold labels are unavailable to extractor runtime. Evaluation and failure-analysis tooling has a separate guarded label-access boundary.

Rule selection may inspect bounded document-block structure and text. Source identity and checksum are used only for provenance and deterministic IDs. Filename, title, source ID, page number and known expected values never select a rule.

## Public API

- `extract_deterministic_candidates(document)` returns one schema-valid source-level `CandidateExtractionResult`.
- `canonical_candidate_result_json(result)` emits sorted, two-space-indented UTF-8 JSON with one trailing newline.
- `get_deterministic_rule_inventory()` returns the immutable reviewed rule inventory.
- `DETERMINISTIC_BASELINE_VERSION` identifies `deterministic-baseline-v0.1`.

`DeterministicExtractionError` reports input or output-contract failures without introducing a fallback extraction path.

## Rule inventory

The inventory order and priorities are fixed. Eight rules produce candidates and two rules apply shared policy.

| Priority | Rule family | Predicate | Behaviour |
| ---: | --- | --- | --- |
| 10 | numbered recommendation detection | `recommendation` | Explicit recommendation labels and explicit recommend constructions only |
| 20 | explicit commitment language | `commitment` | Actor-attributed commitment and future-action language |
| 30 | mandatory requirement language | `requirement` | Explicit obligations and prohibitions without strengthening guidance |
| 40 | explicit decision language | `decision` | Recorded determinations, excluding proposals and options |
| 50 | risk or impact statement detection | `risk` | Explicit risk, threat and adverse-impact statements |
| 60 | quantitative metric detection | `metric` | Bounded percentages and simple numeric measures |
| 70 | monetary budget detection | `budget` | Currency amounts linked to budget, funding, investment or allocation |
| 80 | action progress status detection | `action_status` | Explicit status for identified actions, tasks or milestones |
| 90 | heading and same-block subject attribution | Policy only | Same-statement subject or immediately preceding eligible context |
| 100 | exact evidence-span preservation | Policy only | Exact, contiguous, length-bounded evidence from one block |

The inventory contains no source-specific, filename-specific, document-title-specific, page-specific or expected-value-specific condition.

## Statement segmentation

Segmentation restarts for every eligible block. Metadata, email-header and quoted-history blocks are excluded from candidate text. Page text, slide titles, shape text, table text and current email bodies are eligible.

Non-empty physical lines are the primary boundaries. A conservative punctuation rule may subdivide a line into sentences while retaining original character offsets. Explicit numbered recommendation items remain intact. The engine never joins blocks, crosses locations, reorders text or reconstructs visual table rows. Whitespace may be collapsed for comparison and normalized string values, but evidence always uses original block text.

## Subject attribution

The engine prefers an explicit source-stated subject inside the bounded statement. If none exists, it may use only an eligible immediately preceding line in the same block. Eligible context is short, non-sentential and conservatively title-like, label-like or colon-terminated.

Subject attribution never crosses a block. Impersonal references, missing subjects and multiple plausible actors cause abstention. The explicit `Recommendation <number>` label is a permitted subject for a numbered recommendation. Subject text remains an exact source substring.

Lexical subject typing recognizes recommendation, programme, policy, initiative, organisation, risk, metric and decision cues. Other is used only where the predicate registry permits it. A budget candidate is withheld when its subject cannot safely map to an allowed budget subject type.

## Rule behaviour

### Recommendation

The rule accepts explicit numbered recommendation labels and explicit `recommend`, `recommends` or `recommended` constructions with a safe subject. Arbitrary numbered lists and standalone `should` wording do not qualify. Numbered recommendations retain an integer `recommendation_id`; their value is the complete bounded recommended action.

### Commitment

The rule recognizes `will`, `will not`, `commits to`, `has committed to`, `intends to` and `plans to` when attributable to an explicit or same-block contextual subject. It preserves modal strength and negation. `May`, `might`, `could` and aspirations are not commitments.

### Requirement

The rule recognizes `must`, `must not`, `shall`, `required to`, `is required to` and `are required to`. It preserves prohibitions and does not strengthen `should`, optional guidance or possibility language.

### Decision

The rule recognizes explicit `decided to`, `agreed to`, `approved`, `selected`, `chose to` and `resolved to` statements. It preserves conditions in the bounded value and excludes proposals, options and recommendations that do not record a determination.

### Risk

The rule requires explicit `risk of`, `risk that`, identified-risk, `threat of` or adverse-impact language. Ordinary benefits, neutral impacts and generic possibilities do not qualify. A bounded risk relationship flattened into a table line may emit a `0.50` ambiguous review candidate; an unbounded table relationship is skipped with a deterministic warning.

### Metric

The rule supports a single source-stated percentage or simple numeric measure with a named measure, measured population or safe context. Monetary values and action-completion ratios are excluded. Multiple plausible percentages or measures cause abstention. Metric names are deterministic lowercase snake case derived from source wording. Explicit month-year and year-only periods retain their source precision.

### Budget

The rule requires both a supported currency amount and an explicit budget, funding, investment or allocation relationship. GBP, USD and EUR symbols or codes are supported with thousand, million and billion scaling and common unambiguous abbreviations. `Up to`, approved, committed and proposed states remain distinct. Bare currency mentions, approximate amounts and unsupported subject types are not normalized into confident budgets.

### Action status

The rule recognizes explicit completed, delivered, met, in-progress, on-track, delayed and not-started states for an identified action, task, milestone, workstream, deliverable or recommendation. Explicit `X of Y` action-completion statements remain action status rather than a generic metric. An `action_id` is added only when the source states one.

## Value normalization

- String and status values collapse internal whitespace while retaining modal strength, negation, numbers, units, date precision and material punctuation.
- Percentages use a numeric normalized value and `unit="percent"`.
- Simple numeric measures retain the explicitly stated precision and unit.
- Money uses `NormalizedMoney` with a non-negative base-unit `Decimal` amount and uppercase ISO currency.
- Recommendation IDs are integers copied from explicit labels.
- Metric qualifiers are limited to `metric_name`, `unit`, explicit `population` and explicit `period`.
- Action IDs and budget status are emitted only when source-stated.
- No missing unit, denominator, date or deadline is invented.

Every string `raw_value` is an exact evidence substring. Numeric normalization does not add precision or turn an approximate statement into an exact value.

## Evidence

Every candidate references one existing block from the same source. An evidence excerpt is an exact contiguous substring of `block.text`, uses the block's unchanged location type and value, and is at most 240 characters. The engine does not insert ellipses, reconstruct text or combine locations.

When same-block heading context is required, the contiguous excerpt includes both the heading and statement. A supported relationship uses `supported`; a bounded flattened-layout risk relationship uses `ambiguous`. Evidence that cannot contain the complete bounded support within 240 characters causes abstention rather than truncation. Identical spans can be shared by distinct candidate facts through one deterministic evidence ID.

## Confidence and review

Confidence values are fixed rule-strength heuristics, not probabilities:

- `0.90`: explicit same-statement subject, trigger, value and supported evidence;
- `0.70`: eligible immediately preceding same-block subject context and supported evidence;
- `0.50`: bounded flattened-layout ambiguity.

Every `0.50` or ambiguous-evidence candidate requires review. Supported `0.90` and `0.70` candidates normally use `not_required`. No other confidence value is emitted or tuned.

## Determinism

Batch, evidence and candidate IDs use SHA-256 over explicit stable version, source, checksum, block, location, offset, rule, subject, typed-value, qualifier and evidence components. The engine does not use Python `hash()`, random values, UUID4, timestamps, process data or paths.

Blocks, statements, rules and candidate signatures have a fixed sort order. Exact duplicate semantic/provenance candidates are suppressed. Evidence and warnings are unique and deterministically ordered. Repeated extraction and canonical serialization of identical input are byte-identical.

## Abstention

Warnings contain stable codes and bounded provenance identifiers rather than source semantics. Categories include:

- `abstained_missing_subject`;
- `abstained_multiple_values`;
- `abstained_ambiguous_relationship`;
- `abstained_evidence_too_long`;
- `abstained_unsupported_subject_type`;
- `skipped_flattened_table_relationship`.

Normal non-matches are silent. Lower recall is acceptable for this baseline when the alternative would be an unsupported or over-confident extraction.

## Candidate entities

`deterministic-baseline-v0.1` returns `entities=[]`. Each candidate fact retains its source-stated `subject_text` and bounded `subject_type`. Standalone entity resolution and consolidation belong to later extraction or reconciliation work and are not approximated by another heuristic here.

## CLI

The CLI accepts an existing JSON file containing one `ParsedDocument`; it does not parse raw PDF, PPTX or EML files:

~~~powershell
python -m document_intelligence.extraction.deterministic_cli --input path/to/parsed_document.json --output path/to/candidate_result.json
~~~

Omit `--output` to write canonical JSON to stdout. An existing output requires `--force`. Failures use exit code 1 and concise stderr without absolute paths.

## Tests

The regression suite uses invented, source-independent in-memory `ParsedDocument` fixtures. It covers all rule families, negative triggers, same-block boundaries, exact evidence, confidence and review routing, typed normalization, deterministic IDs and order, duplicate suppression, warnings, canonical JSON, CLI behavior, no-gold imports and no extractor file or network access. It does not load real parsed artifacts or use real annotation wording.

## Limitations

- Shallow regex and structural heuristics.
- English-only trigger patterns.
- Page-level PDF text blocks rather than reconstructed layout.
- Limited grammatical parsing and pronoun resolution.
- Conservative abstention that may reduce recall.
- No visual table reconstruction.
- Heuristic metric names and subject types.
- No public-gold evaluation result yet.
- No LLM comparison.
- No reconciliation, entity consolidation or final fact state.

## Claim boundary

- The deterministic rule engine exists.
- No development F1 or other public-gold score exists yet.
- No held-out score or held-out extraction exists.
- No production-readiness claim is made.
- No claim is made that the rules outperform an LLM.
