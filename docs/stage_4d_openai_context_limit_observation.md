# Stage 4D OpenAI context-limit observation v0.1

## Purpose

This document records the reviewed, no-call context-limit observation used by the
offline Stage 4D OpenAI development-manifest contract.

It does not create the actual five-source manifest and does not authorize or
perform provider execution.

## Frozen artifact

Repository path:

`reports/llm_extraction/openai_development_manifest/gpt-5.4-mini-context-limit-observation-v0.1.json`

Observation schema:

`0.1`

Observed at UTC:

`2026-08-05T23:20:47Z`

Reviewer:

`Kang Li`

## Reviewed provider source

Source title:

`GPT-5.4 mini Model | OpenAI API`

Source URL:

`https://developers.openai.com/api/docs/models/gpt-5.4-mini`

The reviewed source states:

- requested model alias: `gpt-5.4-mini`;
- available snapshot: `gpt-5.4-mini-2026-03-17`;
- context window: `400000` tokens;
- maximum output: `128000` tokens;
- reasoning effort supports `none`.

The source does not explicitly establish the complete accounting relationship
between input, output and reasoning tokens for this contract. Therefore the
observation records
`input_output_reasoning_share_context_window=false`. This means the relationship
is not asserted as reviewed fact; it is not a claim that the token classes are
definitively independent.

## Conservative admission rule

The contract uses:

`serialized provider-payload bytes + 4096 <= 400000`

The token-admission method is:

`serialized_utf8_byte_upper_bound`

The exact safety rule is:

`one serialized UTF-8 provider-payload byte is admitted as at most one input token for the context-window safety check`

This deliberately avoids inferred tokenizer behavior. The fixed 4096 allowance
preserves the already reviewed output-token ceiling used by the Stage 4D
provider contract.

## Frozen identities

Observation self-hash:

`09717CDFE8EFBF669047515AB2258E1C42BF1527AE2A7E7A79F8E2602D2FADF2`

Artifact LF-content SHA-256:

`3A7B8D498AEE0A6D14C153890DA0056E5240143C1D6A671BFCF7DB80919557B2`

Artifact length:

`771` bytes

The artifact is canonical JSON followed by exactly one LF byte.

## Validation

Artifact-specific regression tests verify:

- exact path, length, LF semantics and outer SHA-256;
- canonical model bytes and observation self-hash;
- exact reviewed values and timestamp;
- absence of credentials, execution authorization and source content;
- fail-closed rejection of rehashed field drift.

Focused result:

`4 passed`

## Authorization and access boundary

This observation was created without:

- constructing an OpenAI client;
- accessing an API key or credential;
- making a provider or network request;
- reading real development ParsedDocuments;
- creating the actual five-source manifest;
- creating cache, attempt or provider-response artifacts;
- creating or consuming execution authorization;
- accessing S005, S007 or held-out data.

The successful synthetic v0.3 preflight remains closed historical evidence. Its
authorization is consumed and cannot be reused.

## Independent review

Independent read-only review completed on `2026-08-06`. The review accepted
the artifact inventory, canonical bytes, outer hash, model self-hash,
official-source values, no-call boundary and focused regression coverage.
No provider execution was performed.

## Next controlled step

Generate the actual hash-only five-source manifest in a separate no-call
change and subject it to independent review. Provider execution remains
separately unauthorized.
