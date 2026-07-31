# Project Status

- **Current stage:** Stage 3B.5E-1 deterministic-baseline-v0.4 finalization transaction implementation in progress; no real finalization or freeze has run
- **Last updated:** 2026-07-31
- **Latest milestone:** PR #21 merged the completed and independently audited owner-assessment package at `d9cddfd21a302151213ea5cde27f400a382e1e64`; formal owner outcomes are 3/3 passed and remain distinct from 3/3 passed automated diagnostics
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0 foundation.
- Stage 1 corpus strategy, audit, synthetic fixtures, evaluation design and `stage1-corpus-v1.0` freeze.
- Stage 2 Common Document Object, PDF/PPTX/EML parsers, dispatcher, CLIs, batch ingestion and frozen-corpus validation.
- Stage 3A candidate extraction schema `0.1`, predicate vocabulary `0.1`, public annotation models and checksummed `public-gold-v0.1` freeze.
- Stage 3B.1 `deterministic-baseline-v0.1` experiment and strict matching protocol `0.1`.
- Guarded development-only gold access with metadata-first routing and held-out denial.
- Pure ParsedDocument deterministic extraction, canonical output, hash-derived IDs and exact evidence provenance.
- Development-run, reproducibility, owner-review, observation-lock and transactional freeze contracts.
- Immutable failed v0.1 observation and read-only S004 diagnosis.
- Frozen additive v0.2 plan, extractor, evaluator, execution workflow and evidence-integrity controls.
- PR #17 merged through commit `35949e538756c2e592533fda1564da29427ae03a`.
- Frozen `deterministic-baseline-v0.2` development evidence: TP 0, FP 321, FN 25, F1 null and challenge pass rate 2/3.
- PR #18 merged through commit `bc758f2a294023b1629565badbbbdb5b89dca4d6`.
- Stage 3B.5A additive `deterministic-baseline-v0.3` integrated development comparison: TP 5, FP 172, FN 20, recall 0.20, F1 0.04950495049504951 and automated challenge diagnostics 3/3 passed; formal v0.3 owner assessment was not performed.
- PR #19 merged through commit `4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc`, completing and integrating Stage 3B.5B.
- Corrected additive `deterministic-baseline-v0.4` authoritative development comparison: TP 5, FP 173, FN 20, precision 0.028089887640449437, recall 0.2, F1 0.04926108374384237, 178 candidates and 25 commitments. All five original v0.3 strict matches remain; no S002 commitment is a strict match. The final actor-method inventory is one `authors_or_senders`, two `explicit_statement_actor`, eleven `preserved_parent_subject` and eleven `unresolved`; non-commitment facts and resolved evidence are identical to v0.3.
- Stage 3B.5C deterministic v0.4 owner-review preparation: exact five-source input and candidate hashes, three frozen challenge cases, all evidence-linked candidates, resolved evidence and warning inventories were assembled with three blank owner assessment rows. At that preparation checkpoint, automated challenge diagnostics were 3/3 structural passes while formal owner outcomes remained 0 completed and 3 pending.
- PR #20 merged the Stage 3B.5C owner-review preparation package at `36fe312ef07716a3597ea62a5d146a12b1c9312b`.
- Stage 3B.5D formal v0.4 owner assessment: Kang Li supplied `passed` outcomes and exact evidence-based rationales for `PGC-V01-S001-001`, `PGC-V01-S004-001` and `PGC-V01-S006-001`. The separate completed record retains candidate counts 6, 0 and 6, preserves the blank template, and passes deterministic metadata, reference, evidence-consistency, owner-versus-machine and held-out-isolation checks.
- PR #21 merged Stage 3B.5D through commit `d9cddfd21a302151213ea5cde27f400a382e1e64`. The required independent read-only audit passed with no critical findings or required corrections and is recorded separately as machine review evidence.

## In progress

- Stage 3B.5E-1 additive v0.4 finalization and freeze transaction implementation, using fictional temporary repositories and fictional candidate outputs for write-path tests only.

The authoritative v0.1 observation and complete v0.2 and v0.3 baselines remain frozen and immutable. The merged v0.4 implementation retains candidate schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1` and unchanged `match_strict_facts`. Formal owner outcomes and automated diagnostics remain separate provenance fields. This implementation milestone has not opened any real development ParsedDocument, run real v0.4 extraction, or created any real finalization output. No v0.4 freeze manifest exists. No held-out semantic annotation model was deserialized; no S005 or S007 ParsedDocument was opened or executed. Held-out execution remains blocked pending a separate guard and explicit authorization. No held-out extraction result, LLM extractor or LLM reconciliation layer exists. The sparse development gold does not establish exhaustive candidate precision.

## Next tasks

1. Complete the Stage 3B.5E-1 finalization transaction implementation and independent read-only review.
2. Merge the reviewed implementation before any real finalization execution.
3. Run the public read-only prerequisite audit on the merged commit.
4. Execute the exact five-source finalization once with an explicit freeze date only if all 28 process gates pass.
5. Validate the installed fourteen-file transaction without rewriting it.
6. Keep held-out execution blocked behind a later separate guard and explicit authorization.

## Blockers

- v0.1 cannot be finalized.
- The Stage 3B.5E-1 implementation must pass independent read-only review and be merged before real finalization.
- v0.4 is not frozen; no real finalization may run until the merged transaction reproduces the exact candidate hashes and all 28 process gates pass.
- Sparse development gold cannot independently establish exhaustive candidate precision.
- Held-out access remains blocked pending a separate reviewed guard and explicit authorization.

## AG News replacement status

Not yet eligible. Replacement remains conservative until extraction quality improves beyond the small development recovery, benchmark limitations are presented clearly and the project presentation is portfolio-ready.
