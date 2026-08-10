# Stage 4D bounded OpenAI development execution plan v0.3

## Purpose

This document records the frozen no-call execution plan for the independently
reviewed Stage 4D development-v0.3 five-source manifest. The plan defines the
controls that a later, separately reviewed transaction must enforce. It does
not implement that transaction, create authorization or permit a provider
call.

## Frozen artifact

Repository path:

`reports/llm_extraction/openai_development_execution_plan/openai-gpt-5.4-mini-five-source-development-execution-plan-v0.3.json`

- execution-plan schema version: `0.3`;
- execution ID:
  `openai-gpt-5.4-mini-five-source-development-execution-v0.3`;
- authorization scope:
  `bounded-five-source-openai-development-execution-v0.3`;
- artifact length: `13077` bytes;
- execution-plan self-hash:
  `12191955D5ED1F6EBF0B0BC97AA6A2EF11B164186645FD68D6270D8A241A0F0A`;
- artifact outer SHA-256:
  `0F567327922CE7C9609CA41C8500AD39BFB3A8F09E8FD0E5BEC4F96E325F38B6`.

The artifact is canonical sorted-key compact UTF-8 JSON followed by exactly
one LF byte. Its self-hash excludes only `execution_plan_sha256`.

## Manifest binding

The plan derives only from the committed manifest at:

`reports/llm_extraction/openai_development_manifest/openai-gpt-5.4-mini-five-source-development-manifest-v0.3.json`

It binds:

- exact artifact length `90686` bytes;
- canonical-LF and outer SHA-256
  `EE634214A296D4CB18687F48FD241E4A64B8848C2AD80FC697F797FE527AEB6E`;
- manifest self-hash
  `D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327`.

Plan generation loaded and validated this artifact directly. It did not
regenerate the manifest or open ignored ParsedDocuments.

## Provider and schema binding

The plan fixes:

- provider `openai`;
- requested model alias `gpt-5.4-mini`;
- compatibility-preflight returned model identifier
  `gpt-5.4-mini-2026-03-17`;
- separate model-version or snapshot provenance `unavailable`;
- provider SDK `2.46.0`;
- provider configuration
  `openai-responses-text-strict-json-v0.2`;
- model configuration
  `openai-gpt-5.4-mini-text-strict-json-v0.2`;
- output contract `candidate-extraction-result-0.1`;
- response schema
  `candidate_extraction_result_0_1_aliases_empty_v0_3`;
- strict-schema SHA-256
  `C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E`.

The local `CandidateExtractionResult` contract remains schema version `0.1`.
The closed synthetic preflight v0.4 is compatibility evidence only; it is not
development extraction-quality evidence.

## Invocation inventory

| Order | Request | Source | Role | Payload bytes | Conservative ceiling (USD) |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | `llm-v0.3-S001-primary-001` | `S001` | primary | 106660 | 0.098427 |
| 2 | `llm-v0.3-S002-primary-001` | `S002` | primary | 84200 | 0.081582 |
| 3 | `llm-v0.3-S003-primary-001` | `S003` | primary | 74123 | 0.07402425 |
| 4 | `llm-v0.3-S004-primary-001` | `S004` | primary | 197889 | 0.16684875 |
| 5 | `llm-v0.3-S004-primary-002` | `S004` | primary | 196624 | 0.1659 |
| 6 | `llm-v0.3-S004-primary-003` | `S004` | primary | 99320 | 0.092922 |
| 7 | `llm-v0.3-S006-primary-001` | `S006` | primary | 181579 | 0.15461625 |
| 8 | `llm-v0.3-S004-repeat-001` | `S004` | repeat | 197889 | 0.16684875 |

The inventory contains seven primaries and one repeat. Primary distribution is
S001 `1`, S002 `1`, S003 `1`, S004 `3` and S006 `1`. The final request repeats
`llm-v0.3-S004-primary-001`.

Every invocation copies its request, prompt, strict-schema, provider-payload
and cache hashes from the manifest. Attempt-marker and failure-record paths are
derived deterministically from the distinct cache identity. No raw document or
prompt text is stored in the plan.

## Execution controls

The future transaction is bounded by:

- maximum provider calls: `8`;
- maximum total attempts: `8`;
- maximum retries per invocation: `0`;
- maximum transaction retries: `0`;
- provider-side retries: `0`;
- response timeout: `120` seconds;
- maximum output tokens per invocation: `4096`;
- maximum aggregate output tokens: `32768`;
- manifest conservative cost ceiling: USD `1.001169`;
- planned authorization cap: USD `1.25`;
- same-day pricing review required;
- same-day data-controls review required.

The sum of the eight invocation conservative ceilings is exactly USD
`1.001169`, strictly below the USD `1.25` cap.

## Cache and failure policy

The plan records the cache root:

`.cache/llm_extraction/llm-extraction-baseline-v0.3/openai/`

A later transaction must read the append-only cache before installing an
attempt marker. Cache replacement and bypass remain forbidden, and only
successful provider responses may be cached.

For a cache miss, the future transaction must:

- install a permanent per-invocation marker before credential access and
  client construction;
- install a successful provider-response cache record before local
  validation;
- write sanitized, self-hashed failure evidence;
- stop after the first provider or local failure;
- preserve completed cache records;
- prohibit automatic retry or overwrite;
- install a final execution record exclusively and last, only after all eight
  outputs validate.

These are frozen requirements only. No attempt, failure or execution artifact
was created by this plan task.

## Authorization and access boundary

Execution remains unauthorized. A later real transaction requires explicit
project-owner authorization bound to:

- this exact execution-plan SHA-256;
- the manifest self-hash;
- maximum provider calls `8`;
- maximum total attempts `8`;
- the exact USD `1.25` cost cap;
- the fixed v0.3 authorization scope.

Readiness must not create authorization. Only S001, S002, S003, S004 and S006
are in the plan inventory. S005, S007, unknown sources, held-out
ParsedDocuments and annotations, gold labels, deterministic candidates and
owner outcomes remain prohibited.

## Non-claims and next gate

This no-call plan does not establish transaction readiness, candidate results,
evaluation results, model-quality improvement, held-out generalization or
production readiness. The v0.1 and v0.2 bounded development executions remain
closed and immutable.

The next engineering gate is a separate additive transaction and readiness
implementation, followed by complete independent pre-execution review. No
provider call can occur without a later exact authorization.

Plan preparation and generation opened no ignored ParsedDocuments and made no
provider call, credential or API-key access, real-client construction, cache
access, or evaluation, gold, owner-outcome or held-out access. The clean-archive
plan-specific tests also required no ignored ParsedDocuments.

During broader local regression and full-suite validation, two pre-existing
tests read the locally available approved development ParsedDocuments for
S001, S002, S003, S004 and S006. Those reads were test-only and did not
influence plan generation, invocation selection, hashes, costs or frozen plan
bytes; they were not a provider execution or development extraction run. No
S005, S007 or held-out access occurred, and there was no provider call,
credential or API-key access, real-client construction, cache access, or
evaluation, gold or owner-outcome access.
