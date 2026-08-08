# Stage 4D bounded OpenAI development execution plan v0.1

## Purpose

This document records the frozen and independently reviewed no-call execution
plan for the approved five-source Stage 4D OpenAI development comparison.

The plan defines the transaction boundary that a later implementation must
enforce. It does not create execution authorization and does not permit a
provider call.

## Frozen artifact

Repository path:

`reports/llm_extraction/openai_development_execution_plan/openai-gpt-5.4-mini-five-source-development-execution-plan-v0.1.json`

Execution ID:

`openai-gpt-5.4-mini-five-source-development-execution-v0.1`

Authorization scope:

`bounded-five-source-openai-development-execution-v0.1`

Artifact length:

`12641` bytes

Execution-plan self-hash:

`F92DBA083F5A92E6EFFF0E7D58B9D05553934AD3689FB90A3D091BD39D9D29A7`

Artifact LF-content SHA-256:

`FFFE07FEA0F19FF46B4B5F060B012699BA1A68E6C9BDE94AF7E7CF93E6956F93`

The artifact is canonical UTF-8 JSON followed by exactly one LF byte.

## Manifest binding

The plan binds the reviewed actual five-source manifest through all of:

- repository-relative artifact path;
- manifest self-hash
  `05ABF3D0FA785B845E0853B907B911EE1A9439F0997052D3603E025AAAA30D0E`;
- canonical LF-content SHA-256
  `15DF5E959040B399EDF8CA5455B5060EF71B6672C97D9901E6DB084FE9ACC069`;
- exact artifact length `90809` bytes.

The plan cannot be derived from a different valid manifest because the
production builder requires the fixed manifest self-hash and the plan's own
canonical self-hash is fixed.

## Provider binding

The plan fixes:

- provider `openai`;
- requested alias `gpt-5.4-mini`;
- preflight-returned identifier `gpt-5.4-mini-2026-03-17`;
- separate version or snapshot provenance `unavailable`;
- provider SDK `2.46.0`;
- provider configuration
  `openai-responses-text-strict-json-v0.1`;
- model configuration
  `openai-gpt-5.4-mini-text-strict-json-v0.1`;
- strict-schema SHA-256
  `45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74`.

A later transaction must still validate the actual returned provider metadata.
The preflight identifier is a frozen prior observation, not evidence that a
later call has already occurred.

## Invocation inventory

| Order | Request | Source | Role | Payload bytes | Cache identity |
| ---: | --- | --- | --- | ---: | --- |
| 1 | `llm-v0.1-S001-primary-001` | `S001` | primary | 105273 | `F2B9349EAA71220ADABD9327DA085AF7C3AF65D0A5492496338F1D6E07A82393` |
| 2 | `llm-v0.1-S002-primary-001` | `S002` | primary | 82813 | `EC5404C802BD54EAFD90E08E56C727AF258F2B2BFFE706A3AE6954118E8704DE` |
| 3 | `llm-v0.1-S003-primary-001` | `S003` | primary | 72736 | `B8A877459D061497631CEBD9FF38209BA832A54D8284003ED47A5148F72F285C` |
| 4 | `llm-v0.1-S004-primary-001` | `S004` | primary | 199892 | `4282CF340940EEF55C3CAB2E630D5B1EE56BF5A0AC3EA798B006DA2F77C34A80` |
| 5 | `llm-v0.1-S004-primary-002` | `S004` | primary | 199780 | `8917AA5F5A4AE09290D7F331266B628698FC2D7AC0A0AB69B33ACAA5160E8345` |
| 6 | `llm-v0.1-S004-primary-003` | `S004` | primary | 90000 | `4BB0156C6FF7C3A50310FA8DE4D7C29675A31879712E79FA3F7F2B8226A804C4` |
| 7 | `llm-v0.1-S006-primary-001` | `S006` | primary | 180192 | `DE477D531FDB654FFDDDF040E9F4D47F447890B75DBBE2035A47032D5DD81E05` |
| 8 | `llm-v0.1-S004-repeat-001` | `S004` | repeat | 199892 | `3845479111B03DAAF1797E64E7C88E041F3EF19AFD882C4A4A0669D9BDB9A422` |

The repeat is bound to `llm-v0.1-S004-primary-001`. Each invocation has a
distinct cache identity and distinct attempt-marker and failure-record paths
derived only from that opaque cache identity.

## Execution controls

The plan fixes:

- maximum provider calls: `8`;
- maximum total attempts: `8`;
- maximum retries per invocation: `0`;
- provider-side retries: `0`;
- response timeout: `120` seconds;
- maximum output-token budget: `32768`;
- conservative aggregate cost ceiling: USD `0.9953895`;
- authorization cap: USD `1.25`;
- same-day pricing review required;
- same-day data-controls review required.

The conservative ceiling remains below the authorization cap.

## Cache and partial-failure policy

The later transaction must:

- check the append-only local cache before installing an attempt marker;
- prohibit cache bypass, replacement and automatic overwrite;
- cache successful provider responses only;
- install an exclusive invocation-specific attempt marker before client
  construction for a cache miss;
- stop after the first provider or local failure;
- preserve already completed cache records;
- treat an attempt marker without a cache record as non-retryable in v0.1;
- permit reuse of a successfully cached response after a later local parse
  failure;
- install a final execution record only after every invocation is valid.

The plan does not implement these operations. It freezes the requirements for
the separately reviewed transaction implementation.

## Authorization and access boundary

The plan requires a new explicit project-owner authorization that binds:

- this execution-plan self-hash;
- the reviewed manifest self-hash;
- maximum provider calls `8`;
- cost cap USD `1.25`;
- the fixed authorization scope.

Readiness and artifact generation created no authorization.

Only `S001`, `S002`, `S003`, `S004` and `S006` are approved. `S005`, `S007`,
unknown sources, held-out ParsedDocuments, held-out annotations, gold labels,
deterministic candidates and owner outcomes remain prohibited as prompt input.

## Hash-only boundary

The artifact contains structural identities and controls. It contains no:

- source-document or evidence text;
- raw prompt or provider request body;
- API key, credential or authorization ID;
- provider response or raw response;
- candidate facts or candidate output;
- evaluation result.

## Validation and independent review

Contract tests:

`7 passed`

Frozen-artifact tests:

`6 passed`

Combined execution-plan tests:

`13 passed`

Complete offline suite:

`1779 passed, 13 skipped`

The thirteen skips are the unchanged Windows symbolic-link and directory-link
privilege limitations. Compilation and `git diff --check` also passed.

Independent read-only review verified:

- exact five-file review ZIP inventory;
- expected module and test identities;
- canonical 12,641-byte artifact and exact LF SHA-256;
- recomputed execution-plan self-hash;
- exact manifest and provider bindings;
- eight ordered invocation, payload and cache identities;
- distinct attempt-marker and failure-record paths;
- retry-zero call, attempt, timeout and cost limits;
- cache-first append-only and partial-failure controls;
- explicit authorization requirement and absence of authorization creation;
- development-only allowlist and held-out denial;
- absence of source text, prompts, credentials, responses and candidate output;
- exact additive `.gitattributes` LF rule;
- tamper rejection and full-suite compatibility.

Review verdict:

`approved_for_evidence_commit`

No provider call, API-key access, client construction, cache operation, attempt
marker, authorization artifact, candidate output, evaluation or held-out access
occurred during plan generation, testing or independent review.

## Next controlled step

Implement and independently review the bounded development-execution
transaction against this frozen plan.

Provider execution remains separately unauthorized. A new explicit
project-owner authorization must not be created until the transaction
implementation and its offline evidence have completed independent review.
