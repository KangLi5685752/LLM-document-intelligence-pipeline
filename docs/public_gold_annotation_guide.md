# Public Gold Annotation Guide

## Goal

Public gold v0.1 labels bounded candidate facts in the seven frozen public PDFs. It prepares evidence for later candidate-extraction evaluation; it does not label final current, superseded, duplicate, or conflict states.

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

## Raw and normalized values

`raw_value` preserves the source meaning and important qualifiers in readable form. `normalized_value` supplies the bounded machine-comparable representation allowed by the declared `value_type`:

- percentages are numeric percentages;
- money contains a non-negative decimal amount and three-letter uppercase currency;
- exact dates use ISO 8601;
- strings retain material scope and attribution;
- uncertain or absent values are not invented.

If a date phrase has more than one reasonable normalization, record the issue in notes and route it through owner review.

## Evidence excerpts

Each fact points to one existing `PAGE_TEXT` block, its exact 1-based PDF page, and a 20-240 character excerpt occurring in normalized block text. Keep excerpts short enough for review and never substitute them for the source document. Page-level extraction can retain unusual whitespace from visually arranged PDFs; exact block text is authoritative for structural validation.

## Ambiguity, unsupported claims, and missing values

- `ambiguous` cases route to review when subject, denominator, attribution, or layout relationships are unclear.
- `unsupported` cases must not be extracted when the available text cannot support the proposed claim.
- `missing_expected_value` cases preserve absence rather than filling a date, owner, or other value from inference.

Challenge cases contain no invented expected value.

## Two-pass procedure

Pass 1 drafts a bounded subject, canonical predicate, raw value, normalized value, and excerpt from the relevant `ParsedDocument` page block.

Pass 2 reopens the original PDF page, the parsed block, and the record. Check the page, subject, predicate, raw and normalized values, excerpt, and material qualifiers. Record any normalization or scope concern in `notes`. Pass 2 does not confer owner approval.

## Review status

- `draft_ai_assisted`: drafted with local source review; owner decision pending.
- `owner_verified`: the project owner has checked the record and documented the decision.
- `rejected`: the owner has rejected the proposed label, with the reason recorded.

All initial v0.1 records remain `draft_ai_assisted`.

## Held-out controls

Public held-out labels are visible because the benchmark is procedural, not secret. They may be annotated and structurally validated, but their values must not shape predicate code, deterministic rules, prompts, or development assertions. Do not run an extractor on held-out sources during Stage 3A. Freeze a development implementation before later held-out evaluation.

## Limitations

The draft has one annotator, AI assistance, no inter-annotator agreement, a small corpus, coarse page-level blocks, and possible interpretation bias. Structural validation proves referential consistency, not semantic correctness. Owner verification and documented corrections are required before public-gold approval.
