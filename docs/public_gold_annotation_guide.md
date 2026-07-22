# Public Gold Annotation Guide

## Goal

Frozen `public-gold-v0.1` labels bounded candidate facts in the seven frozen public PDFs. It prepares evidence for later candidate-extraction evaluation; it does not label final current, superseded, duplicate, or conflict states.

## Inclusion criteria

Include one source-stated fact when:

- the subject and value are explicit;
- a canonical v0.1 predicate represents the relationship;
- the value can be preserved raw and normalized without inventing information;
- one `PAGE_TEXT` block contains a short supporting excerpt;
- the page and block can be verified against the original PDF.

Suitable material includes formally numbered recommendations, explicit government commitments, governance requirements, reported research findings, quantitative metrics, action progress, stated risks, and recorded decisions.

## Exclusion criteria

Do not create a supported fact from:

- inferred intent or causality;
- an ambiguous value or denominator;
- a figure whose value is unavailable in parsed page text;
- decorative headings;
- an isolated reference entry;
- a long third-party quotation;
- a statement whose subject or attribution cannot be retained;
- a visual relationship that page-level parsing did not preserve reliably.

Represent these conditions as challenge cases when they test expected review, rejection, or missing-value behaviour.

## Subject and predicate selection

Choose the narrowest source-stated subject that remains intelligible outside the sentence. Use only a predicate registered in vocabulary v0.1. Do not introduce a new relationship because it appears convenient for one source. When several predicates could apply, prefer the one that preserves the source's speech act: for example, a recommendation remains a `recommendation`, while an organisation's explicit undertaking may be a `commitment`.

Runtime validation applies the same predicate-use rules to candidate facts and gold annotations. It normalizes aliases, checks the subject and value types against the registered definition, requires meaningful required qualifiers, and rejects undeclared qualifier names. The validation is vocabulary-based and contains no source-specific exception.

## Qualifiers

Use qualifiers only when declared by the selected predicate and supported by the source:

- every `metric` requires a stable `metric_name`;
- add metric `unit`, `population`, and `period` when the source supports them;
- retain `recommendation_id` for numbered recommendations;
- retain `budget_status` when the source states committed, proposed, draft, advisory, approved, or another explicit status;
- retain `date_type` only when it is applicable to a supported `target_date`.

An empty qualifier object is valid only when the predicate has no required qualifier. Do not use qualifiers to carry inferred context.

## Raw and normalized values

`raw_value` preserves the source meaning and important qualifiers in readable form. `normalized_value` supplies the bounded machine-comparable representation allowed by the declared `value_type`:

- percentages are numeric percentages;
- money contains a non-negative decimal amount and three-letter uppercase currency;
- exact dates use ISO 8601 only at the precision stated by the source;
- strings retain material scope and attribution;
- uncertain or absent values are not invented.

Do not infer a day from a month-level deadline. In particular, “before the end of” a named month does not support substituting the month's final calendar day as an exact date. Preserve the source precision or route the phrase through owner review; if the annotation cannot be normalized without false precision, select a different unambiguous fact or exclude it.

## Evidence excerpts

Each fact points to one existing `PAGE_TEXT` block, its exact 1-based PDF page, and a 20-240 character excerpt occurring in normalized block text. Keep excerpts short enough for review and never substitute them for the source document. Page-level extraction can retain unusual whitespace from visually arranged PDFs; exact block text is authoritative for structural validation.

## Ambiguity, unsupported claims, and missing values

- `ambiguous` cases route to review when subject, denominator, attribution, or layout relationships are unclear.
- `unsupported` cases must not be extracted when the available text cannot support the proposed claim.
- `missing_expected_value` cases preserve absence rather than filling a date, owner, or other value from inference.

Challenge cases contain no invented expected value.

## Two-pass procedure

Pass 1 drafts a bounded subject, canonical predicate, structured qualifiers, raw value, normalized value, and excerpt from the relevant `ParsedDocument` page block.

Pass 2 reopens the original PDF page, the parsed block, and the record. Check the page, subject, predicate, raw and normalized values, excerpt, and material qualifiers. Record any normalization or scope concern in `notes`. Pass 2 does not confer owner approval.

If sample review exposes a semantic defect, correct the draft and extend the owner worksheet to the complete annotation set. The completed `docs/public_gold_full_review.md` covers all 35 facts; the ten-record sample remains a convenience view, not an approval substitute.

Project-owner review is a distinct semantic pass after structural validation. The owner checks the original PDF page, frozen ParsedDocument block, bounded subject and predicate, qualifiers, values and normalization, then records approve, correct-before-approval or reject. Structural success proves referential consistency; owner verification records a semantic decision by the project owner.

## Review status

- `draft_ai_assisted`: drafted with local source review; owner decision pending.
- `owner_verified`: the project owner has checked the record and documented the decision.
- `rejected`: the owner has rejected the proposed label, with the reason recorded.

All 35 facts and six challenge cases in frozen v0.1 are `owner_verified`, with non-empty decision notes. The completed review does not retroactively change `annotation_method`: it records that AI-assisted drafting was followed by project-owner semantic verification.

## Held-out controls

Public held-out labels are visible because the benchmark is procedural, not secret. During Stage 3B, held-out facts and held-out challenge cases must not be loaded by deterministic rule-design code, rule tests or tuning. Freeze the baseline experiment version, rules and code before accessing held-out records for evaluation.

## Limitations

The frozen asset had AI-assisted drafting followed by one project-owner review. It has no independent second annotator, no inter-annotator agreement, a small corpus, coarse page-level blocks and possible interpretation bias. Owner verification improves semantic control but is not independent replication. Future semantic changes require a new dataset version.
