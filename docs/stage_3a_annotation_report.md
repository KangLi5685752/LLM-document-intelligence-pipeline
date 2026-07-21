# Stage 3A Annotation Report

## Outcome

Stage 3A created and structurally validated a public-PDF annotation draft for candidate extraction. The draft contains no extractor output and is not approved public gold because owner review remains pending.

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
| `commitment` | 6 |
| `decision` | 2 |
| `finding` | 1 |
| `metric` | 7 |
| `recommendation` | 8 |
| `requirement` | 5 |
| `risk` | 2 |
| `target_date` | 1 |

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
- all predicates resolved through vocabulary v0.1.

The selected pages were also reopened from the original local PDFs during the second annotation pass. This local AI-assisted check does not constitute project-owner approval.

## Known limitations

- One AI-assisted annotator and no inter-annotator agreement.
- Owner verification has not occurred.
- Page-level evidence is coarse and some visually arranged PDFs preserve unusual whitespace.
- The 35-fact subset is small and not representative of enterprise document diversity.
- Procedural held-out labels are public, so familiarity bias cannot be eliminated.
- Structural validity does not prove the semantic correctness of every subject, predicate, or normalization.

## Decision

Stage 3A structural preparation passed. Owner review, correction, record verification, and a versioned public-gold freeze remain required before extraction experiments can claim public-gold results. No extraction result or extraction metric exists.
