# Stage 3B v0.3 development comparison

This report compares additive deterministic-baseline-v0.3 with frozen v0.2 on development sources only.

## Evaluator provenance

Matching uses unchanged protocol v0.1 and the unchanged `match_strict_facts` implementation. Aggregate metrics use an additive deterministic v0.3 report calculator that explicitly reconciles TP, FP and FN with the matcher output and candidate/gold inventories. The complete frozen v0.2 evaluator is not reused.

## Strict metrics

| Baseline | Candidates | TP | FP | FN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| v0.2 | 321 | 0 | 321 | 25 | 0.0 | 0.0 | null |
| v0.3 | 177 | 5 | 172 | 20 | 0.02824858757062147 | 0.2 | 0.04950495049504951 |

## Candidate inventory

- v0.2 by source: {"S001": 43, "S002": 93, "S003": 28, "S004": 52, "S006": 105}
- v0.3 by source: {"S001": 32, "S002": 18, "S003": 12, "S004": 30, "S006": 85}
- v0.2 by predicate: {"action_status": 1, "commitment": 193, "decision": 3, "metric": 84, "requirement": 34, "risk": 6}
- v0.3 by predicate: {"action_status": 2, "budget": 2, "commitment": 24, "decision": 3, "metric": 84, "recommendation": 22, "requirement": 34, "risk": 6}
- v0.3 review-required candidates: 77
- v0.3 semantic duplicates: 0

## Gold recovery

- Exact matched annotation IDs: PG-V01-S001-001, PG-V01-S001-004, PG-V01-S003-001, PG-V01-S003-002, PG-V01-S003-003
- Remaining unmatched annotation IDs: PG-V01-S001-002, PG-V01-S001-003, PG-V01-S001-005, PG-V01-S002-001, PG-V01-S002-002, PG-V01-S002-003, PG-V01-S002-004, PG-V01-S002-005, PG-V01-S003-004, PG-V01-S004-001, PG-V01-S004-002, PG-V01-S004-003, PG-V01-S004-004, PG-V01-S004-005, PG-V01-S004-006, PG-V01-S006-001, PG-V01-S006-002, PG-V01-S006-003, PG-V01-S006-004, PG-V01-S006-005
- Remaining primary mismatch categories: {"evidence_segmentation": 5, "missing_predicate_coverage": 2, "subject_text_resolution": 13}

## Reproducibility and process checks

- Schema-valid source results: 5/5
- Primary/repeat byte-identical source results: 5/5
- Source-independence audit: passed
- Held-out semantic access: No held-out semantic annotation model was deserialized; no S005 or S007 ParsedDocument was opened or executed; held-out raw JSONL bytes and row metadata may be scanned by the guarded loader for integrity verification and split routing.

## Automated development challenge diagnostics

- S001 preserve_missing automated challenge diagnostic (PGC-V01-S001-001): passed
- S004 do_not_extract automated challenge diagnostic (PGC-V01-S004-001): passed
- S006 route_to_review automated challenge diagnostic (PGC-V01-S006-001): passed
- Formal v0.3 owner assessment: not performed.
- Frozen v0.2 owner assessment: unchanged.

## Sparse-gold precision limitation

Official FP and precision values are retained for direct comparability. Because development gold is a selected set of 25 owner-verified facts rather than a proven exhaustive annotation, a strict unmatched candidate is not automatically a confirmed invalid fact; unmatched candidates outside sparse-gold coverage remain unreviewed.
