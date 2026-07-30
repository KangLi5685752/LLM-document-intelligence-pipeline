# Stage 3B v0.4 development comparison

This deterministic report compares v0.2, v0.3 and additive v0.4 on the five development sources only.

## Evaluator provenance

Matching protocol 0.1 and `match_strict_facts` are unchanged. TP, FP and FN are calculated by the additive v0.4 report calculator and reconciled with matcher inventories.

## Strict metrics

| Baseline | Candidates | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v0.2 | 321 | 0 | 321 | 25 | 0.0 | 0.0 | None |
| v0.3 | 177 | 5 | 172 | 20 | 0.02824858757062147 | 0.2 | 0.04950495049504951 |
| v0.4 | 178 | 5 | 173 | 20 | 0.028089887640449437 | 0.2 | 0.04926108374384237 |

## v0.4 inventory

- Candidates by source: {"S001": 32, "S002": 18, "S003": 13, "S004": 30, "S006": 85}
- Candidates by predicate: {"action_status": 2, "budget": 2, "commitment": 25, "decision": 3, "metric": 84, "recommendation": 22, "requirement": 34, "risk": 6}
- Commitments by source: {"S001": 1, "S002": 14, "S003": 8, "S004": 1, "S006": 1}
- Commitment total: 25
- Actor-resolution methods: {"authors_or_senders": 1, "explicit_statement_actor": 2, "preserved_parent_subject": 11, "unresolved": 11}
- Actor classification order: quotation_or_reported_speech -> institutional_first_person_or_generic_government -> eligible_explicit_statement_actor -> preserved_parent_subject
- Value-normalisation operations: {"affirmative_will_removed": 21, "intent_or_planning_preserved": 4}
- Preserved semantic modifiers: {"also": 2}
- Rejected recovery reasons: {"actor_not_eligible_or_unresolved": 165, "ineligible_action": 2, "unsafe_or_ambiguous_parent_completion": 1}
- Unresolved actor count: 22

## Strict recovery

- Exact matches: PG-V01-S001-001, PG-V01-S001-004, PG-V01-S003-001, PG-V01-S003-002, PG-V01-S003-003
- Exact S002 commitments: 
- Lost former matches: 
- Lost rejected-attempt matches: PG-V01-S002-001, PG-V01-S002-003
- Remaining S002 commitments: PG-V01-S002-001, PG-V01-S002-002, PG-V01-S002-003, PG-V01-S002-004, PG-V01-S002-005

## Safeguards

- Non-commitment semantic parity with v0.3: true
- Static forbidden-reference audit: passed
- Counterfactual behavioural tests: passed_during_current_correction
- Manual semantic provenance review: correction_applied_pending_read_only_review
- Schema-valid sources: 5/5
- Primary/repeat byte-identical sources: 5/5
- Held-out access: No held-out semantic annotation model was deserialized; no S005 or S007 ParsedDocument was opened or executed. The guarded loader may scan held-out raw JSONL bytes and row metadata only for integrity and split routing.

## Automated challenge diagnostics

- PGC-V01-S001-001 preserve_missing: passed
- PGC-V01-S004-001 do_not_extract: passed
- PGC-V01-S006-001 route_to_review: passed

## Claim boundary

Official strict FP and precision are reported for comparison, but the selected 25-fact development gold is not proven exhaustive; an unmatched candidate is not automatically a manually confirmed semantic error.

The static forbidden-reference audit is a limited leakage blacklist, not standalone proof that rules are source-independent.

Formal v0.4 owner assessment has not been performed. Held-out extraction remains blocked.
