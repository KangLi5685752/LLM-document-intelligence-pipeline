# Stage 3B Strict Development Evaluator

## Status

Stage 3B.4A implements and freezes the executable matching and metric semantics for `deterministic-baseline-v0.1`. No real development public-gold evaluation has run and no development score exists. Stage 3B.4B execution, error analysis and baseline freeze is next.

## Why implementation precedes observation

The evaluator is reviewed before the first development score is observed. This ordering reduces the risk of changing comparison normalization, pairing rules or metric denominators to improve an already-seen result. Any later semantic change requires an explicit new experiment version or a documented pre-freeze correction.

## Runtime boundary

The in-memory boundary is:

`DevelopmentGoldBundle` + precomputed `CandidateExtractionResult` attempts + explicit owner challenge assessments -> `DevelopmentEvaluationReport`

The evaluator does not invoke the extractor, load files, resolve paths, access the network or load annotations outside the supplied development bundle. It accepts explicit successful or failed primary and repeat attempts for each frozen development source.

## Matching protocol

Protocol v0.1 comparison normalization applies Unicode NFKC, casefolding, straight quote mapping, Unicode-dash mapping, whitespace collapse and surrounding trim, then removes at most one final `.`, `!` or `?` and trims again. It does not remove words, modality, negation, numbers, units, internal punctuation or date precision.

Typed comparison uses normalized text for textual values; exact `Decimal(str(value))` semantics for numbers and percentages; exact amount and uppercase ISO currency for money; exact stored source precision for dates; exact booleans; ordered elementwise lists; and null-to-null matching only. It adds no tolerance, date expansion, currency conversion, list sorting or approximate credit.

Every gold qualifier is material. A candidate must contain and exactly match the complete gold qualifier projection. Additional declared candidate qualifier keys do not prevent a match, but their sorted names are reported as qualifier over-specification. Missing qualifier values are never inferred.

Strict matches are limited to the same source and require normalized subject text, exact subject type, canonical predicate, exact value type, exact typed normalized value and all material qualifiers. Compatible candidates and annotations are paired once in deterministic lexical order. Unmatched candidates remain false positives, unmatched annotations remain false negatives and an extra candidate with the same semantic key is not removed.

## Value alignment

Normalized-value accuracy is evaluated separately so a value error does not prevent the evaluator from measuring the value-normalization step. Its alignment key contains source, normalized subject, subject type, predicate, value type and material qualifiers, but excludes normalized value. Potential pairs are greedily assigned one-to-one using matching evidence block, normalized raw-value equality, candidate ID and annotation ID as deterministic tie-breakers.

## Evidence metrics

Evidence metrics use strict matches only. Source accuracy requires a referenced evidence record from the gold source. Location accuracy requires one referenced record whose evidence block ID, location type and location value all equal the gold location. Normalized exact excerpt equality is retained as a diagnostic and is not a substitute for location accuracy.

## Source attempts

Each of the five development sources has an explicit primary and repeat attempt. A successful attempt contains one validated single-source result and its canonical output SHA-256. A failed attempt contains only a stable error code. Failed primary sources contribute zero candidates, remain in the five-source schema-valid-result-rate denominator and produce a stable evaluator warning; they are never silently dropped.

## Challenge cases

Challenge outcomes are explicit owner assessments, not source-specific automated pass rules. The three development cases must be assessed individually with an expected behavior, pass/fail outcome, concise rationale and optional sorted candidate or warning references. This evaluation assessment is separate from owner creation and verification of the gold labels.

## Reproducibility

For every development source, the report compares the recorded canonical hashes from the primary and repeat attempts. Equal hashes pass, two different hashes fail and an unavailable output makes the check unavailable. `all_outputs_byte_identical` is true only when all five checks pass.

## Report model

The report retains exact counts and fractions for fact precision, recall and F1; normalized-value exact match; schema-valid result rate; evidence source and location accuracy; excerpt exact-match diagnostics; and development challenge-case pass rate. It also records per-predicate counts, compact strict matches and value alignments, unmatched IDs, duplicate and qualifier diagnostics, challenge assessments, reproducibility checks and stable evaluator warning codes.

The model contains no timestamp, filesystem path, source text, annotation notes, final fact state or rounded-count reconstruction. Canonical serialization uses a JSON-mode model dump, sorted keys, two-space indentation, UTF-8-compatible text and exactly one trailing newline.

## Strictness limitation

Strict matching may count semantically similar or equivalent wording as a false-positive/false-negative pair. This is a deliberate transparency and reproducibility limitation of protocol v0.1, not evidence that the candidate is necessarily semantically wrong.

## Scope boundary

Stage 3B.4A includes no actual development run, development metrics, error analysis or baseline freeze manifest. It does not access held-out semantics and does not change deterministic extraction rules, annotations, reconciliation, final fact states or LLM behavior.

## Next step

Stage 3B.4B will:

1. Run the extractor twice on the five frozen development `ParsedDocument` inputs.
2. Preserve canonical candidate outputs and hashes.
3. Perform owner assessment of the three development challenge cases.
4. Compute the first development report.
5. Classify unmatched candidates and annotations.
6. Freeze rules, code, outputs and metrics.
