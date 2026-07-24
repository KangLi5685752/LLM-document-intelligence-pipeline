# Stage 3B Development-Only Public-Gold Loader

## Status

Stage 3B.2 implements the development-only annotation access boundary for `deterministic-baseline-v0.1`. No extractor, metric or result exists. Stage 3B.3 deterministic rule implementation is next.

## Purpose

The loader supplies development labels to evaluation and failure-analysis tooling. It does not supply labels to the extractor runtime. The future extractor must receive only frozen `ParsedDocument` input and must not import a gold-data loader.

## Why a dedicated loader is required

The generic Stage 3A loaders intentionally deserialize the complete dataset for freeze and structural validation. Baseline development needs a narrower, fail-closed API that returns development semantics only. Public labels cannot be made secret, but a dedicated boundary prevents accidental programmatic loading of held-out semantics during rule design and tuning.

## Access sequence

The safe API executes these controls in order:

1. Deny held-out or unknown access mode before repository I/O.
2. Validate the frozen experiment configuration.
3. Validate the public-gold freeze manifest and its repository-relative paths.
4. Stream and verify both JSONL SHA-256 hashes before semantic deserialization.
5. Metadata-scan each binary JSONL line for its ID, source and split.
6. Semantically deserialize and validate development records only.
7. Return a deterministically ordered development bundle.

## Metadata versus semantics

Full file bytes are necessarily read for binary SHA-256 verification. ID, source and split metadata are then read from each bounded binary line to determine its route. Development lines are decoded into `GoldFactAnnotation` or `GoldChallengeCase`; held-out semantic objects are never constructed and their raw lines are discarded after metadata verification.

This is procedural isolation, not cryptographic secrecy. The held-out bytes remain visible in the public repository and are read for integrity and metadata routing, but they are not exposed as semantic Python objects by the baseline API.

## Development bundle

`load_baseline_gold` returns exactly 25 owner-verified development facts and three owner-verified development challenge cases from S001, S002, S003, S004 and S006. The bundle includes only frozen experiment/schema identity, content hashes, development source IDs and the deterministically ordered development records. It contains no paths, timestamps, ParsedDocument data, synthetic ground truth or held-out semantics.

`summarize_development_gold` returns deterministic non-semantic counts and hashes. It excludes subjects, values, qualifiers, excerpts, notes and challenge descriptions.

## Held-out guard

Stage 3B.2 provides no valid bypass. `held_out` and unknown access modes are rejected before repository-root resolution, file opening or hashing. A future held-out API requires the planned versioned baseline freeze manifest, its validator and a separate reviewed implementation. Adding a file with a plausible freeze-manifest name does not enable access.

## Generic loader boundary

`load_gold_fact_annotations` and `load_gold_challenge_cases` remain available for complete Stage 3A dataset validation. Deterministic-baseline implementation and evaluation code must use `load_baseline_gold`. The future extractor must not import the generic loaders or the guarded gold loader because its only input is `ParsedDocument`.

## CLI

Print the deterministic development summary:

~~~powershell
python -m document_intelligence.extraction.baseline_gold_cli --repository-root . --access development
~~~

Write the same canonical JSON to a new report path:

~~~powershell
python -m document_intelligence.extraction.baseline_gold_cli --repository-root . --access development --report artifacts/baseline_gold_summary.json
~~~

Existing reports require `--force` for replacement. A held-out request is an expected rejection with exit code 1 and the stable access-denied message:

~~~powershell
python -m document_intelligence.extraction.baseline_gold_cli --repository-root . --access held_out
~~~

## Failure behavior

The API fails closed for:

- missing, malformed or incompatible experiment configuration;
- missing, malformed, non-frozen or incompatible manifest;
- manifest paths that differ from or escape the fixed repository paths;
- experiment/manifest version or hash disagreement;
- byte-level facts or cases hash mismatch;
- missing, duplicate or invalid metadata;
- unknown sources or IDs;
- experiment, record and corpus-split disagreement;
- invalid or non-owner-verified development semantics;
- wrong counts, source inventories or challenge-case IDs.

Errors never include raw JSONL content or held-out semantic fields.

## Tests

The regression suite verifies the real 25-fact/3-case bundle, deterministic summaries, frozen hashes, immediate held-out denial, absence of environment or placeholder-file bypasses, strict config/manifest compatibility, path containment, CLI behavior and forbidden-input isolation. Temporary fixtures contain valid development records and metadata-valid but semantically invalid placeholder held-out records; successful loading proves held-out lines are not passed to semantic Pydantic validation.

## Limitations

- Labels remain visible in the public repository.
- Python cannot make public bytes secret.
- Generic complete-dataset validation utilities still exist.
- The controls prevent accidental use, not deliberate manual circumvention.
- A single-developer procedural held-out evaluation remains vulnerable to prior familiarity.

## Claim boundary

- No extraction has run.
- No score exists.
- No held-out evaluation has run.
- No performance claim is made.
- No production-security claim is made.
