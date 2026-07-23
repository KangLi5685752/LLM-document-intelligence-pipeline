# Stage 3A Completion Report

## Scope

Stage 3A establishes the pre-reconciliation candidate contract and freezes an owner-reviewed public-PDF evaluation asset. It does not implement deterministic or LLM extraction, reconciliation or extraction metrics.

## Candidate extraction contract

`CandidateExtractionResult` schema `0.1` represents unreconciled candidate entities, facts and block-linked evidence. Candidate facts have no final `fact_state`; current, superseded, duplicate and conflict decisions remain outside the implemented layer.

## Predicate contract

Predicate vocabulary `0.1` contains 20 bounded definitions. Runtime validation shared by candidate and gold models normalizes registered predicates, enforces allowed subject and value types, requires meaningful mandatory qualifiers and rejects undeclared qualifiers.

## Public fact annotations

`public-gold-v0.1` contains 35 owner-verified facts across S001-S007. The fixed distribution is 25 development and 10 held out, with source counts S001=5, S002=5, S003=4, S004=6, S005=5, S006=5 and S007=5.

## Challenge cases

The asset contains six owner-verified cases: two ambiguous, two unsupported and two missing expected values. These cases define review, rejection or missing-value behavior without inventing supported facts.

## Owner-review results

Project-owner semantic review completed on 2026-07-23. Twelve facts were approved without correction and 23 were corrected before approval. Five challenge cases were approved without correction and one was corrected before approval. No fact or case was rejected, and no draft record remains.

## Corrections made

Corrections restored source speech acts, actor attribution, modal wording, material scope, time precision, survey populations, metric meaning and complete bounded evidence. The S005 challenge case now distinguishes visually structured table rows from flattened page-text association. Full per-record outcomes are in `docs/public_gold_owner_decision_log.md`.

## Validation results

- Fact records: 35/35 valid
- Challenge cases: 6/6 valid
- Evidence block, page and excerpt failures: 0
- Owner-verified facts: 35
- Owner-verified cases: 6
- Draft records: 0
- Rejected records: 0
- Development facts: 25
- Held-out facts: 10
- False day-level March 2027 normalization: absent
- Network calls: none
- Synthetic ground truth loaded: no

## Frozen manifest

`data/annotations/public_gold_v0.1_manifest.json` records the freeze date, fixed corpus/parser/schema versions, counts, split controls and SHA-256 hashes. Tests recompute the hashes for both JSONL files and fail on unversioned changes.

## Acceptance gates

- Candidate and predicate contracts implemented: passed.
- All 35 facts owner reviewed with non-empty notes: passed.
- All six cases owner reviewed with non-empty notes: passed.
- Exact source, split and challenge distributions: passed.
- All fact evidence references valid against frozen ParsedDocument output: passed.
- Freeze-level validator with `--require-owner-verified`: passed.
- Checksummed deterministic manifest: passed.
- Full repository test suite: passed (256 tests on 2026-07-23).

## Limitations

- Single project-owner review.
- No independent second annotator or inter-annotator agreement.
- Small, public-sector-focused sample.
- Page-level evidence and flattened PDF layout.
- Procedural rather than secret-blind held-out evaluation.

## Stage 3A decision

Stage 3A is complete. The repository suite and freeze checks pass, and `public-gold-v0.1` is the immutable evaluation asset for the next experiment cycle.

## Next stage

Stage 3B will freeze the deterministic-baseline experiment plan, enforce development-only label loading, implement deterministic candidate extraction, and freeze code and rules before any held-out evaluation. Reconciliation and RAG remain out of scope.

## Claim boundary

The repository has candidate contracts and an owner-reviewed frozen annotation asset. It has no extractor, reconciled `KnowledgeExtractionResult`, extraction score or demonstrated extraction performance.
