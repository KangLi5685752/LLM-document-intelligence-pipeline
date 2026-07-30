# Stage 3B v0.4 actor and value diagnosis

This report is development-evidence specific. It diagnoses S001, S002, S003, S004 and S006 only. The guarded loader may scan held-out JSONL bytes and bounded row metadata for integrity and split routing, but it did not deserialize held-out semantic annotation models or open S005 or S007 ParsedDocuments.

## Correction status

The first v0.4 attempt was rejected during semantic-provenance review because it inferred a UK Government actor from printing location and indirect publication cues, removed actor-bound possessives and semantic modifiers, and permitted parent recovery to shorten source values. A later focused review also found that quotation checks occurred after explicit-subject acceptance and that non-actor parent fragments were labelled as explicit actors. Those defects have been removed. The corrected implementation is pending one final read-only review.

## S002 document identity

- Title: `AI Opportunities Action Plan Government Response`
- `authors_or_senders`: `DSIT`
- Direct role-aware government actor: none
- Resolution: unresolved
- Reason: `DSIT` is an unexpanded acronym and the ParsedDocument contains no complete government organisation in a direct authoring or issuing role. The title, official-publication boilerplate and printing location are insufficient and ignored.

## Corrected actor contract

1. Classify quotation, quoted history and reported speech before any explicit or document-level actor decision.
2. Preserve an explicit statement actor only when the complete bounded subject passes actor eligibility.
3. Otherwise resolve only one complete eligible organisation supplied through `authors_or_senders`, an explicitly authoring metadata role, or bounded front matter with explicit issued, published, authored, prepared or presented-by grammar.
4. Preserve an unchanged non-actor v0.3 subject under `preserved_parent_subject`; do not call it an explicit actor or rewrite it.
5. Do not use source ID, filename, page, family, checksum, annotations, source-specific aliases, the document title subject, generic publisher/creator metadata, licence or parliamentary boilerplate, or printing/publication location.
6. Multiple, contradictory, acronym-only or otherwise ambiguous actors remain unresolved.

## S002 fact outcomes

| Annotation | Evidence | Parent status | Corrected v0.4 outcome | Reason |
| --- | --- | --- | --- | --- |
| `PG-V01-S002-001` | `DOC-S002-B0006` | filtered by v0.3 | not recovered | Institutional first person has no unique direct role-aware authoring actor. The wrapper also preserves `our` and the complete source action. |
| `PG-V01-S002-002` | `DOC-S002-B0006` | filtered by v0.3 | not recovered | Generic government remains unresolved; recovery does not rewrite compounds, articles or semantic scope. |
| `PG-V01-S002-003` | `DOC-S002-B0006` | retained by v0.3 | value normalized, actor unresolved | Affirmative `will` is removed, but generic government is preserved because no direct role-aware government author is present. |
| `PG-V01-S002-004` | `DOC-S002-B0006` | retained by v0.3 | actor unresolved and value incomplete | No direct government author is available and semantic compression remains outside scope. |
| `PG-V01-S002-005` | `DOC-S002-B0008` | filtered by v0.3 | not recovered | Institutional first person has no direct role-aware author and anaphora replacement remains prohibited. |

None of the five S002 commitment annotations is a corrected v0.4 strict match. The two matches reported by the rejected first attempt, `PG-V01-S002-001` and `PG-V01-S002-003`, are explicitly recorded as lost when the unsafe actor inference is removed.

## Corrected value contract

- Remove only leading affirmative `will` and deterministically capitalize the remaining action.
- Preserve `now`, `also`, `immediately`, `still` and `only`.
- Preserve possessives, negation, intent, planning and explicit commitment modality.
- Collapse only the recognized recommendation wrapper around a complete eligible action; preserve quantities, dates, conditions, ownership, scope and subordinate clauses.
- A recovered span must contain the complete normalized parent raw value and may only extend to a safe same-statement boundary.
- Do not paraphrase, resolve general anaphora, synthesize actors or rewrite source ownership.

## Source-independence assurance

The static forbidden-reference audit is a limited leakage blacklist, not standalone proof of source independence. It is combined with neutral counterfactual behavioural tests covering fictional jurisdictions, print/no-print invariance, conflicting actors, title subjects, publisher/creator versus authoring roles, quoted first person and source-identity mutation, plus manual semantic-provenance review. The counterfactual tests passed during this correction; independent read-only review remains pending.
