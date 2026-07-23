# Stage 3A Annotation Report

## Outcome

Stage 3A prepared, corrected, owner reviewed and froze `public-gold-v0.1`. The asset contains 35 evidence-linked fact annotations and six challenge cases. All 41 records are `owner_verified`; none remain draft or rejected. No extractor, extraction result or extraction metric exists.

See the [Stage 3A completion report](stage_3a_completion_report.md) and [public-gold freeze](public_gold_freeze.md) for the acceptance decision and version controls.

## Inputs and controls

- Corpus: `stage1-corpus-v1.0`
- Public sources: S001-S007
- Frozen parser commit: `71148262f094d54ec7d95e45958bd1aaefc64793`
- Ingestion schema: `0.1`
- Candidate extraction schema: `0.1`
- Annotation and case schema: `0.1`
- Predicate vocabulary: `0.1`
- Owner-review completion date: 2026-07-23
- Network or LLM calls: none
- Synthetic ground truth used: no

## Fact distribution

| Source | Split | Owner-verified facts |
| --- | --- | ---: |
| S001 | Development | 5 |
| S002 | Development | 5 |
| S003 | Development | 4 |
| S004 | Development | 6 |
| S005 | Held out | 5 |
| S006 | Development | 5 |
| S007 | Held out | 5 |
| **Total** |  | **35** |

- Development facts: 25
- Held-out facts: 10
- Owner verified: 35
- Draft: 0
- Rejected: 0

## Predicate distribution

| Predicate | Count |
| --- | ---: |
| `action_status` | 1 |
| `budget` | 2 |
| `commitment` | 8 |
| `decision` | 1 |
| `metric` | 8 |
| `recommendation` | 9 |
| `requirement` | 4 |
| `risk` | 2 |

All predicate, subject-type, value-type and qualifier combinations pass the runtime vocabulary contract.

## Challenge cases

The frozen set contains six owner-verified challenge cases:

- ambiguous: 2;
- unsupported: 2;
- missing expected value: 2;
- draft: 0;
- rejected: 0.

Five cases were approved without correction. The S005 risk-table case was corrected to locate ambiguity in flattened ParsedDocument row association rather than in the visually structured original table.

## Owner-review results

Project-owner review completed on 2026-07-23:

- facts approved without correction: 12;
- facts corrected before approval: 23;
- facts rejected: 0;
- challenge cases approved without correction: 5;
- challenge cases corrected before approval: 1;
- challenge cases rejected: 0.

The decision log and completed worksheets preserve the final fields, notes and review decisions. Owner verification is separate from AI-assisted drafting and does not imply independent double annotation or inter-annotator agreement.

## Evidence validation

Freeze-level validation passed:

- 35/35 facts parsed as strict annotation models;
- 6/6 challenge cases parsed;
- 35/35 source assignments and document families matched the frozen split;
- 35/35 evidence blocks existed in frozen ParsedDocument JSON;
- 35/35 pages matched block locators;
- 35/35 excerpts occurred exactly in normalized block text;
- zero invalid evidence records;
- 35/35 facts and 6/6 cases were owner verified;
- zero draft or rejected records;
- no false day-level normalization remained;
- no network, LLM or synthetic-ground-truth access occurred.

## Freeze

The facts and cases are protected by uppercase SHA-256 values in `data/annotations/public_gold_v0.1_manifest.json`. Freeze tests recompute both hashes and enforce fixed versions, counts, distributions and owner-review status.

## Known limitations

- One project-owner reviewer and no independent second annotator.
- No inter-annotator agreement.
- Page-level PDF evidence can retain awkward whitespace and flattened layouts.
- The 35-fact subset is small and not representative of enterprise document diversity.
- Held-out labels are visible, so held-out evaluation is procedural rather than secret blind.

## Decision

Stage 3A annotation preparation is complete and `public-gold-v0.1` is frozen. Stage 3B may use development labels for deterministic-baseline design. Held-out labels and cases remain prohibited until the baseline experiment version, rules and code are frozen. No extraction capability or result is claimed.
