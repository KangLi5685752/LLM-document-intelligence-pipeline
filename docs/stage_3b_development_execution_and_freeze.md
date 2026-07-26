# Stage 3B Development Execution and Baseline Freeze

## Status

Stage 3B.4B implements a two-checkpoint workflow for `deterministic-baseline-v0.1`. Checkpoint 3B.4B-1 prepares and locks the first real development observation before project-owner challenge review. Checkpoint 3B.4B-2 finalizes the evaluation and baseline freeze only after the owner supplies all three case outcomes.

The implementation itself is committed before the real preparation command is run. No held-out access option exists in this workflow.

## Why the workflow is split

The first development score creates an opportunity for post-observation tuning. The `prepare` checkpoint therefore writes an immutable observation lock immediately after strict matching and before qualitative review. It pins the preparation commit, semantic file hashes, five parsed inputs, primary and repeat candidate hashes, and the first TP, FP and FN counts.

Challenge cases are deliberately separated at that boundary. Their expected behaviours are frozen, but deciding whether the observed candidates and warnings satisfy those behaviours requires project-owner judgment. The implementation may assemble evidence and an incomplete template; it must not populate an outcome or rationale.

The complete `DevelopmentEvaluationReport` requires exactly three completed `ChallengeCaseAssessment` records. A final report, error analysis and baseline freeze manifest therefore cannot be created by `prepare`.

## Fixed development inventory

The scored inventory is exactly, and only, this frozen order:

1. S001
2. S002
3. S003
4. S004
5. S006

Every scored source must be a development `PDF` with corpus role `public_realism`. Its source checksum must match the frozen source register. The batch ingestion report may also contain the development synthetic sources produced by the existing split-level CLI, but the baseline runner constructs and opens only `S001.json`, `S002.json`, `S003.json`, `S004.json` and `S006.json`. It does not glob the parsed directory and accepts no arbitrary source-list option.

## Parser provenance

Preparation validates a Stage 2 `BatchIngestionReport` with:

- corpus version `stage1-corpus-v1.0`;
- parser commit `71148262f094d54ec7d95e45958bd1aaefc64793`;
- run type `full_corpus_validation`;
- a successful, checksum-matching entry for every scored source;
- canonical output names `S001.json` through `S006.json` for the five fixed IDs;
- no non-development report item and no failed scored source.

Each loaded `ParsedDocument` must agree with its source ID, format, source checksum, document ID, block count and parse status. Generated preparation records contain hashes and bounded identifiers, never absolute paths.

## Checkpoint 3B.4B-1: prepare

Run:

~~~powershell
python -m document_intelligence.extraction.development_run_cli prepare \
  --repository-root . \
  --parsed-root artifacts/stage_3b/development_parsed \
  --ingestion-report artifacts/stage_3b/development_ingestion_report.json \
  --working-output-root artifacts/stage_3b/deterministic-baseline-v0.1 \
  --publish-output-root evaluation/baselines/deterministic-baseline-v0.1/development
~~~

Preparation:

1. validates the frozen corpus and ingestion provenance;
2. loads public gold only through `load_baseline_gold(..., access_mode=development)`;
3. opens the five explicit ParsedDocument paths;
4. runs `extract_deterministic_candidates` twice per source;
5. preserves primary and repeat canonical bytes under the ignored working root;
6. publishes primary outputs and records both sets of hashes;
7. runs frozen strict matching and normalized-value alignment;
8. writes the first observation lock immediately;
9. writes structural unmatched diagnostics, an owner-review packet and an incomplete owner-assessment template.

Existing non-empty output roots are protected unless `--force` is explicit. Forced cleanup is restricted to the two dedicated output roots beneath the supplied repository root.

The versioned publish directory contains only:

- `primary/S001.json`;
- `primary/S002.json`;
- `primary/S003.json`;
- `primary/S004.json`;
- `primary/S006.json`;
- `development_run_manifest.json`;
- `observation_lock.json`;
- `owner_challenge_review_packet.json`;
- `owner_challenge_assessment_template.json`;
- `unmatched_review_inventory.json`.

Repeat files are not duplicated in the publish directory when their canonical hashes equal the primary hashes.

Preparation does not create:

- `development_evaluation_report.json`;
- `final_error_analysis.json`;
- `baseline_freeze_manifest.json`.

## Observation lock

The lock uses date `2026-07-26` and status `first_development_result_observed`. It records:

- the implementation commit used for preparation;
- SHA-256 values for the experiment config, baseline plan, matching protocol, deterministic extractor, deterministic rule inventory, matcher, evaluation models and evaluator;
- exact scored source order;
- primary and repeat candidate-output hashes;
- preliminary TP, FP and FN;
- exact precision, recall and F1 fractions;
- per-predicate counts;
- duplicate and qualifier over-specification counts;
- unmatched candidate and annotation IDs;
- `challenge_review_status=pending_owner_review`;
- no minimum F1 gate;
- the requirement that later semantic tuning use `deterministic-baseline-v0.2`.

After this artifact exists, the v0.1 experiment configuration, deterministic rules, matching semantics and evaluator semantics must not change.

## Structural unmatched inventory

The preparation inventory uses exact, deterministic structural comparisons only. It may report subject-text, subject-type, value-type, normalized-value or qualifier mismatches, absence of a same-source predicate candidate, strict non-match and additional candidate duplication.

Closest IDs are review aids. They do not state that a semantically similar candidate is wrong. The workflow uses no fuzzy matching, embedding, LLM or network service.

## Owner-review packet

The packet contains only the three development cases:

- `PGC-V01-S001-001`;
- `PGC-V01-S004-001`;
- `PGC-V01-S006-001`.

For each case it preserves the frozen expected behaviour, description, evidence block IDs and page values. It adds only candidates that reference a listed challenge evidence block, their bounded candidate fields and evidence excerpts, plus relevant result and candidate warning codes.

The assessment template initializes `outcome` and `rationale` to `null`. Codex and the workflow must not infer or populate them.

## Checkpoint 3B.4B-2: finalize

After the project owner completes all three outcomes and rationales, run:

~~~powershell
python -m document_intelligence.extraction.development_run_cli finalize \
  --repository-root . \
  --prepared-root evaluation/baselines/deterministic-baseline-v0.1/development \
  --owner-assessments path/to/completed-assessments.json
~~~

Finalization is implemented and tested before the score is observed, but it is not run in checkpoint 3B.4B-1. It:

1. reloads and revalidates every canonical preparation artifact;
2. verifies primary files, recorded repeat hashes and the observation lock;
3. rejects any changed immutable file hash;
4. rejects a missing outcome or rationale;
5. validates candidate and warning references;
6. invokes the frozen `evaluate_development_candidates` implementation;
7. requires final TP, FP and FN to equal the observation lock;
8. writes the complete evaluation report, bounded final error analysis and baseline freeze manifest.

## Baseline freeze manifest

The final manifest schema is implemented now but no instance is created by `prepare`. It requires:

- experiment, corpus, parser, public-gold, candidate-schema and matching-protocol versions;
- exact public-gold hashes;
- exact development source and challenge-case inventories;
- immutable file hashes;
- parsed source and JSON hashes;
- primary and repeat candidate hashes;
- evaluation, assessment and error-analysis hashes;
- every exact metric numerator and denominator;
- every acceptance gate present and passed;
- byte-identical repeat outputs;
- `no_post_observation_semantic_changes=true`;
- `held_out_access_status=still_blocked_pending_separate_guarded_execution`.

The model rejects held-out IDs, non-identical outputs, missing hashes, absent gates and any claim that held-out access is enabled. Its validator also compares report metrics and current immutable hashes with the frozen values.

## Held-out boundary

A completed baseline freeze manifest is necessary evidence for a future held-out run, but it is not an authorization switch. The current development gold loader still rejects held-out mode, and this CLI exposes no held-out option. Stage 3B.5 requires a separately reviewed guard and explicit invocation.

## Limitations

- The development benchmark is small and PDF-only.
- Strict matching may under-credit semantically similar wording.
- Structural closest-item diagnostics are not semantic judgments.
- Challenge outcomes require one project owner and do not provide inter-annotator agreement.
- The freeze preserves reproducibility evidence; it does not establish production readiness or enable held-out access.
