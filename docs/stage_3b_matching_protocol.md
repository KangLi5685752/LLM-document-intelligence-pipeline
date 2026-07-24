# Stage 3B Deterministic Baseline Matching Protocol v0.1

## Scope

This protocol applies only to public-gold candidate extraction. It does not assign final fact states and does not evaluate reconciliation or synthetic conflicts.

## Comparison unit

The comparison units are one emitted `CandidateFact` and one `GoldFactAnnotation`. Comparisons occur only within the same `source_id`.

## Text normalization

Comparison uses this fixed sequence:

1. Apply Unicode NFKC.
2. Apply `casefold`.
3. Map common typographic quote variants to straight equivalents.
4. Map Unicode dash variants to a hyphen.
5. Collapse every whitespace run to one ASCII space.
6. Trim surrounding whitespace.
7. Ignore one trailing sentence-final `.`, `!` or `?`.
8. Do not remove words, modal verbs, numbers, negation, units or date precision.

Comparison normalization does not alter stored raw values.

## Subject matching

A subject match requires normalized `subject_text` equality and exact `subject_type` equality. Baseline v0.1 uses no fuzzy matching, embeddings, source-specific aliases or external entity resolution.

## Predicate matching

Predicate matching requires exact canonical predicate equality after the existing registry normalizer.

## Value matching

- **Strings, status, person and organisation:** comparison-normalized text equality.
- **Number and percentage:** exact `Decimal(str(value))` equality.
- **Money:** exact amount and uppercase ISO currency equality.
- **Date:** exact stored source-precision string equality.
- **Boolean:** exact equality.
- **List:** elementwise normalized equality with order preserved.
- **Null:** matches only null.

Baseline v0.1 introduces no numeric tolerance.

## Qualifier matching

- Every qualifier present in the gold record is material in v0.1.
- The candidate must contain and match all gold qualifier keys.
- String qualifier values use text normalization.
- Numeric and boolean qualifier values use typed exact equality.
- List qualifiers use order-preserving element equality.
- Extra declared candidate qualifiers do not block strict fact matching, but must be reported as qualifier over-specification.
- Contradictory extra qualifiers are an error.

## Strict match key

The strict match key contains:

- `source_id`;
- normalized `subject_text`;
- `subject_type`;
- canonical predicate;
- `value_type`;
- normalized typed value;
- gold-material qualifier projection.

## One-to-one counting

For each strict match key:

- TP = `min(predicted count, gold count)`;
- FP = `max(predicted count - gold count, 0)`;
- FN = `max(gold count - predicted count, 0)`.

Extra duplicates therefore count as false positives. One candidate cannot satisfy multiple gold facts.

## Normalized-value exact match

Value normalization is evaluated separately among deterministic one-to-one pairs aligned on:

- `source_id`;
- normalized subject;
- `subject_type`;
- predicate;
- `value_type`;
- material qualifiers.

The normalized value is excluded from this alignment key. Ties are resolved deterministically in this order:

1. matching evidence block;
2. normalized raw-value equality;
3. `candidate_id` lexical order;
4. `annotation_id` lexical order.

The metric numerator is aligned pairs with exact normalized typed-value equality; its denominator is all pairs produced by this alignment.

## Evidence metrics

Evidence-source accuracy has:

- numerator: strictly matched facts whose referenced evidence source matches the gold source;
- denominator: strictly matched facts.

Evidence-location accuracy has:

- numerator: strictly matched facts with at least one evidence reference whose block ID, location type and location value match the gold evidence;
- denominator: strictly matched facts.

Evidence excerpt coverage is also reported as a diagnostic, not as a substitute for location accuracy.

## Schema-valid result rate

Schema-valid result rate has:

- numerator: source-level `CandidateExtractionResult` files that validate;
- denominator: all attempted development source outputs.

Invalid candidate attempts must be recorded separately rather than silently dropped.

## Challenge cases

Each of the three development cases is reported individually:

- **`route_to_review`:** pass when no unsupported non-review candidate is emitted for the ambiguous relationship and the extractor either emits a review-required ambiguous candidate or an explicit abstention warning.
- **`do_not_extract`:** pass when the prohibited generalized or unsupported claim is absent.
- **`preserve_missing`:** pass when the missing value is not fabricated, even if the supported surrounding recommendation is extracted.

Development challenge-case pass rate uses passed development cases as its numerator and all three development cases as its denominator.

## Empty denominators

Metrics with zero denominators are reported as null, not 0 or 1, and reports retain the raw counts. Aggregate F1 is calculated from unrounded counts rather than rounded precision and recall.

## Reproducibility

The evaluator requires deterministic record order, deterministic IDs, canonical JSON, repeated-run output hash comparison, and recording of the exact run command and code commit.

## Claim boundary

Strict matching may under-credit semantically equivalent wording. Baseline v0.1 deliberately prioritises transparency and reproducibility over fuzzy credit.
