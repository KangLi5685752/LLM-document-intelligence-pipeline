# Stage 4D Provider and Model Decision

## Status and authority

- **Experiment:** `llm-extraction-baseline-v0.1`.
- **Decision status:** Reviewed and accepted on 2026-08-03.
- **Provider:** OpenAI.
- **API surface:** Responses API.
- **Requested model alias:** `gpt-5.4-mini`.
- **Scope:** Development-only comparator using approved public source text.
- **Execution status:** Unauthorized. This documentation decision does not authorize an API call.

This decision selects one provider and requested model alias for the first LLM-assisted comparator. It does not implement an adapter, install an SDK, configure a credential, create a real request manifest, make a request, or authorize development or held-out execution.

## Reviewed choice

The controlled first execution is constrained to the following configuration boundary:

| Item | Decision |
| --- | --- |
| Provider | OpenAI |
| API surface | Responses API |
| Requested model alias | `gpt-5.4-mini` |
| Input modality | Text only |
| Output mode | Strict JSON Schema Structured Outputs |
| Tools | None |
| Web search | Disabled |
| File search | Disabled |
| Function calling | Disabled |
| Background mode | Disabled |
| Streaming | Disabled for the controlled first execution |
| Response storage request | `store=false` |
| Maximum provider count | One |
| Credentials | Environment variable only; never committed |

The requested alias is a selection target, not yet a complete reproducibility identity. Real execution remains blocked by the identity, compatibility, manifest-review and owner-authorization gates below.

## Official information review snapshot

Official OpenAI model, pricing, Structured Outputs and data-control information was reviewed on 2026-08-03. At that review point:

- GPT-5.4 mini was documented with a 400,000-token context window;
- observed list pricing was USD 0.75 per million input tokens and USD 4.50 per million output tokens;
- the Responses API documented strict JSON Schema Structured Outputs support; and
- the API supported requesting `store=false`.

Model availability, limits, features and pricing are dated observations, not permanent repository constants. The later preflight must recheck them for the project account and the exact selected model before any manifest is frozen or real request is authorized.

`store=false` is a required request setting, but it is not a zero-retention guarantee. Applicable provider retention, abuse-monitoring and account-level data-control limitations must be documented at preflight and disclosed with any later execution evidence.

## Exact model identity and pricing gate

The alias `gpt-5.4-mini` is insufficient by itself for final reproducibility. Before a real development manifest may be frozen, a separately reviewed adapter and preflight change must:

1. verify that the requested model is available to the project account;
2. record the exact model identifier returned by the API;
3. record every provider-exposed model-version or snapshot identifier; when no separate snapshot/version identifier is exposed, record the literal value `unavailable` in the provenance field rather than silently omitting or inferring it;
4. record the provider request ID;
5. record the exact official SDK version;
6. recheck and record current input and output token pricing;
7. confirm strict structured-output support for the exact selected model; and
8. fail closed if a stable, auditable model identity and complete execution terms cannot be established.

The preflight itself requires separate authorization. This decision does not authorize an API call.

## Request configuration boundary

The future adapter must:

- implement the existing Stage 4B provider-neutral request and response contracts;
- use the Stage 4C canonical manifest, append-only cache and provenance foundation;
- transmit only ordered, approved development block text;
- request strict JSON Schema output through the Responses API;
- set `store=false`;
- send no tools and perform no web browsing, retrieval, file search, function calling or file upload;
- disable background execution and disable streaming for the controlled first execution;
- preserve the exact raw response, provider request identity and usage metadata;
- retain the USD 25 aggregate execution ceiling;
- retain the limits of 100 primary invocations, 10 repeat invocations and 220 total attempts;
- retain the 120-second response-timeout ceiling; and
- keep held-out execution unauthorized.

The later adapter and configuration change must fix the output-token limit and any supported reasoning controls only after compatibility is verified. This decision does not invent or approve parameters whose support has not yet been established for the exact model and API configuration.

## Data and privacy boundary

- Only approved public development-source text may be transmitted.
- Development or held-out gold annotations, expected answers, owner outcomes and evaluation targets must not be transmitted.
- Held-out text must not be transmitted.
- Credentials, authorization headers and private environment values must not enter prompts, cache records, provenance or logs.
- API credentials must be supplied through an environment variable and must never be committed.
- Every request must set `store=false`.
- The project must not claim zero retention.
- Provider retention and abuse-monitoring limitations must be disclosed against the terms verified at preflight.
- Real execution requires explicit project-owner authorization after adapter, preflight and manifest review.

## Alternatives assessed

| Alternative | Outcome for v0.1 |
| --- | --- |
| Multiple providers | Rejected because it would increase cost and attribution complexity for the first controlled comparator. |
| Smallest available model | Deferred because the first comparator prioritizes extraction reliability while remaining inexpensive. |
| Free-tier execution | Not relied upon because account limits and data terms may differ from paid API conditions. |
| Local open-weight model | Deferred because hardware, quantization and serving variables are outside the current comparison objective. |

These scope decisions do not claim that the alternatives are technically inferior in general. They keep the first comparator narrow, attributable and reviewable.

## Remaining authorization gates

Before Stage 4D may make a bounded development request:

1. a single OpenAI adapter must be implemented and tested without real development execution;
2. the exact-identity, compatibility, pricing and account-access preflight must be separately authorized and reviewed;
3. the controlled five-source development request manifest must be generated and independently reviewed; and
4. the project owner must explicitly authorize the bounded execution.

No provider request, development extraction, evaluation, finalization, freeze or held-out access is authorized by this document.
