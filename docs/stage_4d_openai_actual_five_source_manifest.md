# Stage 4D actual OpenAI five-source development manifest v0.1

## Purpose

This document records the frozen and independently reviewed actual Stage 4D
hash-only development manifest for the approved five-source OpenAI comparison.

The manifest was prepared without constructing an OpenAI client, accessing an
API key, making a provider request, creating an execution authorization,
producing candidate output, running evaluation or accessing held-out data.

## Frozen artifact

Repository path:

`reports/llm_extraction/openai_development_manifest/openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json`

Manifest schema:

`0.1`

Review-binding timestamp:

`2026-08-06T01:26:53Z`

Artifact length:

`90809` bytes

Manifest self-hash:

`05ABF3D0FA785B845E0853B907B911EE1A9439F0997052D3603E025AAAA30D0E`

Artifact LF-content SHA-256:

`15DF5E959040B399EDF8CA5455B5060EF71B6672C97D9901E6DB084FE9ACC069`

The artifact is canonical JSON followed by exactly one LF byte.

## Approved source routes

The exact development source order is:

1. `S001`
2. `S002`
3. `S003`
4. `S004`
5. `S006`

Every route records:

- development split and approved corpus status;
- derived-text permission;
- successful ingestion status;
- source-document SHA-256;
- canonical ParsedDocument SHA-256;
- parser commit `71148262f094d54ec7d95e45958bd1aaefc64793`;
- normalized repository-relative ParsedDocument path;
- immutable route self-hash.

`S005`, `S007` and unknown sources remain prohibited. Held-out ParsedDocuments,
annotations and owner outcomes are not authorized as prompt input.

## Partition and repeat inventory

The 200,000-byte whole-block greedy partition policy produced seven primary
requests:

| Source | Primary requests | Block partition | Provider payload bytes |
| --- | ---: | --- | --- |
| `S001` | 1 | 26 | 105273 |
| `S002` | 1 | 22 | 82813 |
| `S003` | 1 | 16 | 72736 |
| `S004` | 3 | 54 / 49 / 15 | 199892 / 199780 / 90000 |
| `S006` | 1 | 61 | 180192 |

The one deterministic repeat is:

`llm-v0.1-S004-repeat-001`

It repeats:

`llm-v0.1-S004-primary-001`

The repeated primary is the largest primary provider payload at `199892` bytes.
The repeat appears after all seven primaries. Its prompt, payload, evidence and
cost identities match the selected primary, while its canonical request and
cache identities remain distinct.

All source blocks are preserved once across each source's primary partitions,
with strictly increasing source sequence and no duplicate block or evidence ID.

## Context and provider controls

The manifest binds the reviewed context observation with self-hash:

`09717CDFE8EFBF669047515AB2258E1C42BF1527AE2A7E7A79F8E2602D2FADF2`

The fixed controls are:

- requested model alias `gpt-5.4-mini`;
- returned preflight model identifier `gpt-5.4-mini-2026-03-17`;
- strict JSON Schema output;
- reasoning effort `none`;
- maximum output tokens `4096`;
- `store=false`;
- no streaming, background mode or tools;
- provider-side retries `0`;
- response timeout `120` seconds.

The largest context admission is:

`199892 + 4096 <= 400000`

## Preflight and reviewed-observation bindings

The manifest binds the closed successful synthetic v0.3 preflight through its
fixed attempt, execution-plan and success-record identities. The v0.3
authorization remains consumed and cannot authorize this development run.

Pricing review self-hash:

`42CF744C6728D84AE344BE86A41686943538281A63F476950DFD03ADB0233F25`

Data-controls review self-hash:

`A15479B7927DCAC2DCBB0DD3AFE43BBAA2160C849B4E71698DA29849B820C7EE`

The manifest requires a same-day pricing review before any later execution.
This frozen manifest does not itself authorize use of its dated pricing
observation for a future provider call.

## Execution budget

The frozen retry-zero plan records:

- primary requests: `7`;
- repeat requests: `1`;
- maximum provider calls: `8`;
- maximum total attempts: `8`;
- maximum retries per invocation: `0`;
- planning input-token budget: `282646`;
- conservative input-token proxy budget: `1130578`;
- maximum output-token budget: `32768`;
- aggregate maximum output cost: USD `0.147456`;
- aggregate planning cost: USD `0.3594405`;
- aggregate conservative cost ceiling: USD `0.9953895`;
- planned authorization cap: USD `1.25`;
- broad project ceiling: USD `25`.

The conservative aggregate remains below the planned authorization cap.

## Hash-only and authorization boundary

The manifest retains hashes and structural identities rather than source text or
provider payload contents. It contains no:

- API key or credential;
- raw prompt or provider request body;
- source-document text;
- provider response;
- candidate facts or candidate output;
- execution authorization ID;
- cache response;
- evaluation result.

The immutable artifact records:

- `manifest_review_status=pending_independent_review`;
- `execution_authorization_required=true`;
- `execution_authorization_status=not_provided`.

The embedded review status records the state at artifact freeze and is not
mutated after review. Independent review completion is recorded in this
document and `PROJECT_STATUS.md`.

## Validation

Artifact-specific tests passed:

`6 passed`

Combined actual-manifest, context-observation and manifest-contract regression
tests passed:

`78 passed, 1 skipped`

The single skip is the unchanged Windows directory-link privilege limitation.

Independent read-only review verified:

- the exact three-file review ZIP inventory;
- 90,809 canonical LF bytes and outer SHA-256;
- manifest, route, pricing-review, data-controls-review and context self-hashes;
- five approved routes and held-out denial;
- complete block coverage and S004 three-way partitioning;
- deterministic largest-primary repeat selection;
- distinct primary/repeat request and cache identities;
- per-invocation and aggregate token/cost reconciliation;
- context, retry and authorization boundaries;
- absence of raw source text, credentials, provider responses and candidate
  outputs;
- the exact additive `.gitattributes` LF rule;
- focused regression coverage.

Review verdict:

`approved_for_evidence_commit`

No provider call or held-out access was performed during generation, testing or
independent review.

## Next controlled step

Implement and independently review a separate bounded development-execution
transaction. After that transaction is frozen and all same-day pricing,
data-control, cache, context and credential gates pass, obtain a new explicit
project-owner authorization bound to the reviewed manifest and execution plan.

Provider execution remains separately unauthorized.
