# Stage 3B.4D-3 deterministic baseline v0.2 implementation audit

Audit date: 2026-07-28

## Scope

Stage 3B.4D-1 and Stage 3B.4D-2 implementations are complete. This document records the local pre-observation implementation audit; no real development execution occurred.

The audit is limited to the reviewed implementation at `29dad914a416bb3251cb7615b04fbf712ecf3de6`. It does not authorize a real prepare run, report a development score or claim that pull-request CI has passed.

## Reviewed identities

- Main/base commit: `f224c4e385fab5c4e0348bcf251015630cea9af8`
- Planning anchor: `f224c4e385fab5c4e0348bcf251015630cea9af8`
- Reviewed implementation HEAD: `29dad914a416bb3251cb7615b04fbf712ecf3de6`
- D-1 anchor: `2e54c7f0eb7a7173d4fe3c7b9941f7121fe15722`

The exact implementation chain after main is:

1. `aa48e43fec9dca29b09564efe002105e5b09976f` — `feat: implement deterministic baseline v0.2 extractor`
2. `169303b8f68b5e01ec39b6383153ed21a3936d75` — `fix: preserve v0.1 baseline scope in v0.2`
3. `2e54c7f0eb7a7173d4fe3c7b9941f7121fe15722` — `fix: complete v0.1 value normalization carryover`
4. `027e2c6fe73c4c7af470194a2fe1fb54d7bbb3fe` — `feat: implement deterministic v0.2 evaluation workflow`
5. `29dad914a416bb3251cb7615b04fbf712ecf3de6` — `fix: harden deterministic v0.2 evidence integrity`

## Implementation inventory

The reviewed main-to-implementation diff contains exactly 14 additions: nine implementation files and five test files. It contains no modification, deletion or rename.

Implementation files:

- `src/document_intelligence/extraction/baseline_freeze_v0_2.py`
- `src/document_intelligence/extraction/deterministic_rules_v0_2.py`
- `src/document_intelligence/extraction/deterministic_v0_2.py`
- `src/document_intelligence/extraction/deterministic_v0_2_cli.py`
- `src/document_intelligence/extraction/development_evaluation_v0_2.py`
- `src/document_intelligence/extraction/development_run_models_v0_2.py`
- `src/document_intelligence/extraction/development_run_v0_2.py`
- `src/document_intelligence/extraction/development_run_v0_2_cli.py`
- `src/document_intelligence/extraction/evaluation_models_v0_2.py`

Test files:

- `tests/test_baseline_freeze_v0_2.py`
- `tests/test_deterministic_extractor_v0_2.py`
- `tests/test_development_evaluation_v0_2.py`
- `tests/test_development_run_v0_2_cli.py`
- `tests/test_stage_3b_development_run_v0_2.py`

The Git blob object IDs and uppercase SHA-256 values are frozen in [`reports/stage_3b_v0_2_implementation_hashes.json`](../reports/stage_3b_v0_2_implementation_hashes.json).

## Audit checks

- Frozen plan validator: passed; 9 immutable v0.1 artifacts and 24 immutable v0.1 semantic files verified.
- Focused suite: passed; 269 tests in 260.59 seconds.
- Full suite: passed; 786 tests in 262.81 seconds.
- `compileall`: passed for `src/document_intelligence/extraction` and `tests`.
- Git diff check: passed.
- Planning blob validation: passed for all 6 protected paths at the planning anchor.
- D-1 blob validation: passed for all 4 protected paths at the D-1 anchor.
- Source-independence audit: passed with no violations in the committed D-1 extractor and rules blobs.
- Public-gold identity verification: passed for the frozen config, guarded loader, actual annotation files and v0.2 workflow literals.
- Held-out isolation: passed; held-out semantic content was not accessed.
- v0.2 evidence isolation: passed; the repository development evidence root and its observation, owner-review, evaluation and freeze artifacts do not exist.

## Result

**pre-observation implementation audit passed locally**

This result is local evidence only. It does not claim that pull-request CI passed or that Stage 3B.4D is fully complete.

## PR and merge requirements

All of the following remain required:

- pull-request review;
- Python 3.10 CI success;
- Python 3.11 CI success;
- Python 3.12 CI success;
- merge using **Create a merge commit**;
- post-merge validation on `main`.

Squash merge, rebase merge and history rewriting are prohibited. A real prepare run is prohibited before post-merge approval.

## Real execution boundary

**real prepare is not yet authorized**

The implementation commit recorded by the future first real prepare run will be the final pull-request merge commit, not `29dad914a416bb3251cb7615b04fbf712ecf3de6`. All 14 reviewed implementation and test blobs must remain identical through that merge. Real development execution remains blocked until the merge commit exists and post-merge validation on `main` passes.
