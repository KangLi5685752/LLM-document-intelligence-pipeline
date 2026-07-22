# Stage 3A Annotation Report

## Outcome

Stage 3A created and structurally validated a public-PDF annotation draft for candidate extraction. Stage 3A.1 then enforced predicate-use constraints at runtime and corrected a recommendation-subject attribution error and a false-precision date normalization identified during semantic review. All 35 facts remain AI-assisted drafts, and full owner review remains pending. The draft contains no extractor output and no extraction metric.

## Inputs and controls

- Corpus: `stage1-corpus-v1.0`
- Public sources: S001-S007
- Frozen parser commit: `71148262f094d54ec7d95e45958bd1aaefc64793`
- Annotation schema: `0.1`
- Predicate vocabulary: `0.1`
- Parsed input batch: 15/15 sources successful; annotation validation used only S001-S007
- Source-file checksums: 7/7 matched `source_register.csv` before annotation
- Network or LLM calls: none
- Synthetic ground truth used: no

## Fact distribution

| Source | Split | Draft facts |
| --- | --- | ---: |
| S001 | Development | 5 |
| S002 | Development | 5 |
| S003 | Development | 4 |
| S004 | Development | 6 |
| S005 | Held-out | 5 |
| S006 | Development | 5 |
| S007 | Held-out | 5 |
| **Total** |  | **35** |

- Development facts: 25
- Held-out facts: 10
- Draft AI-assisted: 35
- Owner verified: 0
- Rejected: 0

## Predicate distribution

| Predicate | Count |
| --- | ---: |
| `action_status` | 1 |
| `budget` | 2 |
| `commitment` | 7 |
| `decision` | 2 |
| `finding` | 1 |
| `metric` | 7 |
| `recommendation` | 8 |
| `requirement` | 5 |
| `risk` | 2 |

The draft covers the required recommendation, commitment, requirement, finding, metric, action-status, risk, and decision material. It does not force all vocabulary predicates into the small subset.

## Challenge cases

Six challenge cases were created:

- ambiguous: 2;
- unsupported: 2;
- missing expected value: 2.

Development and held-out PDFs are represented. The cases preserve uncertainty and absence rather than inventing supported fact values.

## Evidence validation

Structural validation passed:

- 35/35 fact records parsed as strict annotation models;
- 6/6 challenge cases parsed;
- 35/35 source assignments and document families matched the frozen split;
- 35/35 evidence block IDs existed in fresh `ParsedDocument` JSON;
- 35/35 page numbers matched their block locators;
- 35/35 excerpts occurred in normalized block text;
- 0 invalid evidence records;
- all normalized values matched their declared bounded value types;
- all predicates resolved through vocabulary v0.1;
- all predicate, subject-type, value-type, and qualifier combinations passed the runtime vocabulary contract;
- all seven metric facts retained a meaningful `metric_name` plus source-supported context.

The selected pages were also reopened from the original local PDFs during the second annotation pass. This local AI-assisted check does not constitute project-owner approval.

## Semantic corrections

- `PG-V01-S001-001` now attributes the statement to AI Opportunities Action Plan recommendation 2 rather than treating government as the recommending subject. Its source, page, value, and evidence are unchanged.
- `PG-V01-S005-001` no longer converts a month-level deadline into an unsupported calendar day. It now labels an explicit Scottish Government action supported by the same page and block.
- The ten-record sample now displays the exact normalized value for `PG-V01-S007-001` instead of a placeholder.
- Structured metric, recommendation, and budget qualifiers are now explicit where supported.

These corrections do not constitute owner verification. The unchecked full-review worksheet contains every one of the 35 facts in deterministic order.

## Known limitations

- One AI-assisted annotator and no inter-annotator agreement.
- Full owner verification has not occurred; all 35 facts remain `draft_ai_assisted`.
- Page-level evidence is coarse and some visually arranged PDFs preserve unusual whitespace.
- The 35-fact subset is small and not representative of enterprise document diversity.
- Procedural held-out labels are public, so familiarity bias cannot be eliminated.
- Structural validity does not prove the semantic correctness of every subject, predicate, qualifier, or normalization.

## Decision

Stage 3A.1 structural validation remains passed after the contract and annotation corrections. Full owner review, any resulting corrections, record verification, and a versioned public-gold freeze remain required before extraction experiments can claim public-gold results. No extractor, extraction result, or extraction metric exists.
