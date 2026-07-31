# Project Status

- **Current stage:** Stage 3B.5D deterministic-baseline-v0.4 owner assessment recorded and deterministically validated; independent read-only review pending
- **Last updated:** 2026-07-31
- **Latest milestone:** PR #20 merged the owner-neutral preparation package at `36fe312ef07716a3597ea62a5d146a12b1c9312b`; project owner Kang Li explicitly supplied three `passed` challenge outcomes and exact rationales, now stored separately from the unchanged blank template and deterministically validated
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
- Stage 3B.5C deterministic v0.4 owner-review preparation: exact five-source input and candidate hashes, three frozen challenge cases, all evidence-linked candidates, resolved evidence and warning inventories are assembled with three blank owner assessment rows. Automated challenge diagnostics remain 3/3 structural passes, but formal owner outcomes remain 0 completed and 3 pending.
- PR #20 merged the Stage 3B.5C owner-review preparation package at `36fe312ef07716a3597ea62a5d146a12b1c9312b`.
- Stage 3B.5D formal v0.4 owner assessment: Kang Li supplied `passed` outcomes and exact evidence-based rationales for `PGC-V01-S001-001`, `PGC-V01-S004-001` and `PGC-V01-S006-001`. The separate completed record retains candidate counts 6, 0 and 6, preserves the blank template, and passes deterministic metadata, reference, evidence-consistency, owner-versus-machine and held-out-isolation checks.

## In progress

- Independent read-only review of the completed v0.4 owner-assessment record and validation evidence before commit.

The authoritative v0.1 observation and complete v0.2 and v0.3 baselines remain frozen and immutable. The merged v0.4 implementation retains candidate schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1` and unchanged `match_strict_facts`. Stage 3B.5D changes no extraction or evaluation semantics. Automated diagnostics remain separate machine evidence and did not populate the three formal project-owner outcomes or rationales. No v0.4 freeze manifest exists. No held-out semantic annotation model was deserialized; no S005 or S007 ParsedDocument was opened or executed; held-out raw JSONL bytes and row metadata may be scanned by the guarded loader only for integrity verification and split routing. No held-out extraction result, LLM extractor or LLM reconciliation layer exists. The sparse development gold does not establish exhaustive candidate precision.

## Next tasks

1. Complete an independent read-only review of the recorded assessment, exact owner rationales and deterministic validation evidence.
2. Commit the Stage 3B.5D record only after that review accepts the unstaged change set.
3. Design and review a separate v0.4 finalization transaction.
4. Create a v0.4 freeze manifest only if every acceptance gate passes.
5. Keep held-out execution blocked behind a later explicit guard and authorization.

## Blockers

- v0.1 cannot be finalized.
- Independent read-only review of the completed owner-assessment record remains pending before commit.
- v0.4 cannot be finalized and no v0.4 freeze manifest may be created until the assessment is reviewed and a separate finalization transaction passes every acceptance gate.
- Sparse development gold cannot independently establish exhaustive candidate precision.
- Held-out access remains blocked pending a separate reviewed guard and explicit authorization.

## AG News replacement status

Not yet eligible. Replacement remains conservative until extraction quality improves beyond the small development recovery, benchmark limitations are presented clearly and the project presentation is portfolio-ready.
