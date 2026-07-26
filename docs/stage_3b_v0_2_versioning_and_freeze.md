# Stage 3B deterministic-baseline-v0.2 Versioning and Freeze

## Status

This record freezes the additive implementation and evidence boundaries for `deterministic-baseline-v0.2` before implementation. It does not create v0.2 code, candidate outputs, an observation lock, owner assessments or a final freeze manifest.

## Why v0.1 remains immutable

`deterministic-baseline-v0.1` has an observed, checksummed execution history. Four published outputs are repeat-identical, S004 failed reproducibly, and the observation lock records the first preliminary diagnostics. Changing the implementation or artifacts after that observation would make the retained evidence describe different semantics.

The following v0.1 source and configuration files therefore remain byte-identical:

- `src/document_intelligence/extraction/deterministic.py`;
- `src/document_intelligence/extraction/deterministic_rules.py`;
- `src/document_intelligence/extraction/evaluation_models.py`;
- `src/document_intelligence/extraction/development_evaluation.py`;
- `src/document_intelligence/extraction/development_run_models.py`;
- `src/document_intelligence/extraction/development_run.py`;
- `src/document_intelligence/extraction/baseline_freeze.py`; and
- `configs/experiments/deterministic_baseline_v0.1.json`.

The v0.1 planning documents and all nine files below `evaluation/baselines/deterministic-baseline-v0.1/development/` are also immutable. The v0.2 validator verifies the exact committed artifact inventory and SHA-256 values without loading semantic content or running extraction.

## Why v0.2 requires additive models

The v0.1 report, run-manifest, observation-lock, owner-review packet, owner-assessment template, unmatched-inventory and freeze contracts use literal `deterministic-baseline-v0.1` identities. The run and freeze orchestration also assumes the v0.1 output layout. Mutating those literals would invalidate v0.1 reconstruction; importing them directly for v0.2 would serialize the wrong experiment identity.

Candidate schema `0.1`, predicate vocabulary `0.1`, the guarded development gold loader and matching protocol `0.1` do not encode the observed extractor version and remain unchanged shared contracts. Version-dependent extraction, report, run and freeze layers must be additive.

## Future v0.2 implementation file inventory

The future implementation PR is limited to these planned versioned files, subject to review before first execution:

- `src/document_intelligence/extraction/deterministic_v0_2.py`;
- `src/document_intelligence/extraction/deterministic_rules_v0_2.py`;
- `src/document_intelligence/extraction/deterministic_v0_2_cli.py`;
- `src/document_intelligence/extraction/evaluation_models_v0_2.py`;
- `src/document_intelligence/extraction/development_evaluation_v0_2.py`;
- `src/document_intelligence/extraction/development_run_models_v0_2.py`;
- `src/document_intelligence/extraction/development_run_v0_2.py`;
- `src/document_intelligence/extraction/baseline_freeze_v0_2.py`;
- `tests/test_deterministic_extractor_v0_2.py`;
- `tests/test_development_evaluation_v0_2.py`;
- `tests/test_stage_3b_development_run_v0_2.py`; and
- `tests/test_baseline_freeze_v0_2.py`.

The modules may call unchanged public helpers from `models.py`, `predicates.py`, the guarded baseline-gold loader and `matching.py`. They must not modify, monkey-patch or write through v0.1 modules. The v0.2 CLI must have a distinct module entry point and the v0.2 workflow must use a distinct output root.

## Preparation commit boundary

Before a real development document is run through v0.2:

1. all required corrections and any included optional corrections are implemented in the additive inventory;
2. every approved family has neutral positive and negative regression coverage;
3. all pre-observation gates pass;
4. the full implementation is reviewed; and
5. one immutable implementation commit is recorded in the future v0.2 run manifest.

No real v0.2 development extraction may be used to select, adjust or add rules before this commit. Planning diagnostics from v0.1 are the only real-source evidence allowed for v0.2 design.

## First-observation lock boundary

The v0.2 workflow must execute primary and repeat attempts for exactly S001, S002, S003, S004 and S006. As soon as candidate counts, TP/FP/FN or derived metrics are first visible, it must write a v0.2 observation lock containing:

- experiment and preparation-commit identity;
- unchanged corpus, parser, gold, schema, predicate and matching versions;
- all source attempts, including failures;
- exact parsed-input and primary/repeat output hashes;
- source-level and aggregate reproducibility states;
- exact preliminary numerators and denominators; and
- structural unmatched identifiers and reason-code counts.

The lock is written before owner review. It does not claim process acceptance or authorize held-out access.

## Owner-review boundary

Owner review begins only if all five sources complete and each primary/repeat pair is byte-identical. The packet contains the three development challenge cases and bounded references to v0.2 candidate IDs, evidence IDs and warning codes. The owner supplies every outcome and rationale explicitly. The workflow must not infer a pass from missing output, abstention or a source failure.

The assessment artifact is separate from deterministic code. Updating an incomplete template with owner judgments does not change extraction semantics, but it remains a reviewed evidence checkpoint.

## Final freeze boundary

Finalization must reload and verify the preparation commit, observation lock, five primary outputs, repeat hashes, structural diagnostics, owner packet and completed assessments. A v0.2 freeze manifest is legal only if every process acceptance gate passes. Exact metric numerators and denominators must reconcile with the observation lock and final report.

No minimum F1 is required. A complete but weak baseline may be frozen so it can be compared honestly later. Non-binding quality targets must be reported independently and cannot be converted into authorization for more v0.2 tuning.

The final manifest must retain held-out status `blocked_until_successful_v0.2_development_freeze_and_separate_guard`. Even a valid v0.2 development freeze is not itself a held-out execution guard.

## Post-observation v0.3 requirement

After the first v0.2 observation, any semantic change requires `deterministic-baseline-v0.3`. This includes trigger eligibility, actor classification, candidate guard behavior, qualifier attachment, normalized values, confidence, warnings, review routing, duplicate policy, schema use, matching or metric semantics.

The failed or weak v0.2 observation, its code commit and its artifacts must remain preserved. A v0.3 cycle requires a new reviewed plan, additive versioned implementation, neutral gates, preparation commit and first-observation lock. It must not overwrite v0.1 or v0.2 evidence.

## Held-out and claim boundaries

No held-out fact or challenge semantic content may be loaded during planning, implementation, neutral testing, development execution or owner review. A later held-out run requires both a successful v0.2 development freeze and a separately reviewed explicit guard.

This planning record supports only the claim that an evidence-backed, source-independent v0.2 scope and version boundary were frozen before implementation. It provides no v0.2 extraction or performance result.
