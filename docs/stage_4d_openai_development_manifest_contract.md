# Stage 4D OpenAI Development Manifest Contract

## Status and scope

This document defines the additive offline contract for preparing a future
five-source OpenAI development manifest for `llm-extraction-baseline-v0.1`.
It does not generate the actual five-source manifest, authorize execution,
construct an OpenAI client, read a credential, create a cache, call a provider,
produce candidates, load gold labels, run matching or evaluation, or access
held-out content.

The generic Stage 4C `RequestManifest` remains unchanged. This Stage 4D contract
adds provider-specific preparation, preflight binding, context admission, narrow
budgets and review gates without weakening the Stage 4C models.

## Fixed provider and experiment boundary

The contract binds:

- experiment: `llm-extraction-baseline-v0.1`;
- provider: `openai`;
- requested alias: `gpt-5.4-mini`;
- returned preflight model: `gpt-5.4-mini-2026-03-17`;
- separate model-version or snapshot provenance: `unavailable`;
- provider SDK: `2.46.0`;
- provider configuration: `openai-responses-text-strict-json-v0.1`;
- model configuration: `openai-gpt-5.4-mini-text-strict-json-v0.1`;
- strict-schema SHA-256:
  `45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74`.

Provider controls remain fixed at reasoning effort `none`, exactly 4096 maximum
output tokens, strict JSON Schema, `store=false`, streaming disabled, background
disabled, no tools, tool choice `none`, zero provider-side retries and a
120-second timeout.

## Successful preflight binding

The manifest preparation binds the closed successful synthetic v0.3 preflight:

- preflight ID:
  `openai-gpt-5.4-mini-synthetic-preflight-v0.3`;
- execution-plan SHA-256:
  `21DEC6F5DE7E79EAC2F80F93ABA41CB96BA815F5000AED9810831F671657D5C5`;
- attempt canonical self-hash:
  `7FDEE6CFEFC6A9BAEC59BD702D7B0FBA4265DD049A11F43E5F5F5A4791036848`;
- successful-record canonical self-hash:
  `1849C329F45D5BD0FA3472DB21FFBC60903C7449BC38BE05BFF6C3ACA219F974`;
- attempt canonical LF-content SHA-256:
  `94CD8A7D7F21B9A102467D210B99D5856483794579DA9AB08B41B49A6BA8B119`;
- successful-record canonical LF-content SHA-256:
  `C2C94A7225343896B0B263AE29E0C80054299A1F30F6CDA38E68F6C4F398A4C2`.

The last two values are SHA-256 values over canonical UTF-8 JSON content with no
BOM and exactly one trailing LF. They are not Git object IDs and do not depend
on Windows checkout line endings.

## Metadata-first source routing

Only S001, S002, S003, S004 and S006 are approved. S005, S007 and every unknown
source fail before path parsing, path joining, resolution, existence checks,
file opening, byte reads or JSON parsing.

PR A does not encode the five real ParsedDocument routes. A caller must later
supply reviewed repository-relative route identities. Each route binds the
source, development split, relative ParsedDocument path, document checksum,
canonical ParsedDocument hash, parser commit, schema version and source format.

Absolute paths, Windows drive paths, UNC paths, device paths, `..`, non-normal
POSIX paths, links, reparse points, path escapes and descriptor identity changes
fail closed.

## Whole-block partition policy

The fixed partition policy ID is:

`provider-payload-whole-block-greedy-v0.1`

The planning ceiling is exactly 200,000 canonical provider-payload UTF-8 bytes.
For each validated nonblank block in source order, the builder:

1. creates the deterministic evidence ID
   `llm-evidence-v0.1-{source_id}-{block_id}`;
2. tentatively appends the complete block;
3. rebuilds the production `LLMExtractionRequest`;
4. rebuilds the production OpenAI provider payload;
5. serializes the payload with canonical JSON;
6. retains the block only when the payload is at most 200,000 bytes;
7. otherwise seals the current partition and starts the next;
8. fails closed when one complete block cannot fit.

No block is split or truncated. Partition boundaries do not use titles,
filenames, selected pages, gold labels, expected facts, deterministic
candidates, annotations, matching results or owner outcomes. The 200,000-byte
ceiling is a planning boundary, not proof of model context admission.

Primary request IDs use:

`llm-v0.1-{source_id}-primary-{partition_ordinal:03d}`

Primary order is S001, S002, S003, S004 and S006, then partition ordinal.

## Repeat-selection policy

The fixed repeat policy ID is:

`largest-primary-provider-payload-request-id-tiebreak-v0.1`

Exactly one repeat is selected before any result is observed. The builder
selects the primary with the greatest provider-payload byte length and uses the
lexicographically smallest primary request ID for an exact tie. The repeat:

- appears after every primary invocation;
- uses role `repeat`;
- uses `llm-v0.1-{source_id}-repeat-001`;
- preserves the selected primary's blocks, prompt and provider payload;
- has a distinct request ID, canonical request hash and append-only cache
  identity.

## Hash-only invocation inventory

The serialized manifest does not contain raw source text, prompt text, provider
request bodies or absolute paths. Each invocation binds:

- invocation order, source, role and request ID;
- repeated-primary identity where applicable;
- document checksum and canonical ParsedDocument hash;
- ordered block/evidence IDs, sequences, per-block text hashes and locations;
- block count and supplied UTF-8 text bytes;
- canonical prompt, request and provider-payload byte lengths;
- prompt, request, strict-schema and provider-payload SHA-256 values;
- append-only cache-identity SHA-256;
- planning and conservative token/cost calculations.

Actual five-source hashes remain audit-derived candidates until the later real
builder recomputes them from reviewed routes and ParsedDocuments.

## Context-limit review gate

A preparation can be structurally valid while blocked. A final manifest cannot
become eligible for independent review without a self-hashed reviewed context
observation recording the model identities, source title and URL, UTC review
time, reviewer, exact context boundary, support for 4096 output tokens, support
for reasoning effort `none`, token-admission method and exact safety rule.

The conservative admission method is:

> one serialized UTF-8 provider-payload byte is admitted as at most one input
> token for the context-window safety check

Every invocation must satisfy:

`canonical_provider_payload_byte_length + 4096 <= reviewed_context_window_tokens`

This rule is applied regardless of whether provider documentation describes
input and output/reasoning as sharing a context boundary. The contract does not
hardcode a context-window size and makes no tokenizer claim.

## Cost planning and narrow budget

The contract binds reviewed pricing and data-control observations to separate
review identities. Pricing calculations are deterministic:

- planning input-token estimate: `ceil(provider_payload_bytes / 4)`;
- conservative input-token proxy: `provider_payload_bytes`;
- maximum output tokens per call: 4096;
- per-call maximum output cost;
- per-call planning cost ceiling;
- per-call conservative cost ceiling;
- aggregate planning cost;
- aggregate conservative cost ceiling.

The planned authorization cap is exactly USD 1.25. It is a planning ceiling,
not execution authorization. The conservative aggregate must fit within USD
1.25, which remains below the broad Stage 4 project ceiling of USD 25. Same-day
pricing review may still be required by the later execution gate.

The exact call budget is derived from the invocation inventory:

- primary count: derived;
- repeat count: exactly one;
- maximum provider calls: total invocation count;
- maximum retries per invocation: zero;
- maximum total attempts: maximum provider calls;
- provider-side retries: zero;
- timeout: 120 seconds.

## Cache policy

The planned repository-relative cache root is:

`.cache/llm_extraction/llm-extraction-baseline-v0.1/openai/`

It is local, Git-ignored and append-only. Replacement and unplanned cache bypass
are prohibited. Primary and repeat cache identities remain distinct. This PR
does not create the directory or any cache record.

## Authorization boundary

The manifest contains only:

- `execution_authorization_required = true`;
- `execution_authorization_status = "not_provided"`.

It contains no authorization ID, authorization timestamp, authorized-by value,
confirmation phrase, credential or mutable placeholder. A later separate
execution plan must bind the frozen manifest hash, new explicit owner
authorization, same-day observations and fixed execution artifact paths.

## Development and held-out isolation

The contract explicitly denies:

- S005, S007 and unknown sources;
- held-out ParsedDocuments;
- held-out annotations;
- gold labels as prompt input;
- deterministic candidates as prompt input;
- owner outcomes as prompt input.

The implementation imports no gold loader, matcher, evaluator, OpenAI client or
network library.

## Canonical identity

Self-hashed observations, routes, reviews, preparations and manifests use
sorted-key compact canonical JSON, UTF-8, no BOM, exactly one trailing LF and
uppercase SHA-256, excluding each self-hash field from its own hash input.
Persisted final-manifest bytes also end in exactly one LF.

## Current limitations and non-claims

After this PR:

- no actual five-source manifest exists;
- no context-limit observation for the real model has been frozen;
- no execution authorization exists;
- no development API request has occurred;
- no candidate, cache or execution evidence exists;
- the current mock runner is not authorized for real execution;
- no extraction-quality, superiority, held-out-generalization or production
  claim is supported.

## Later controlled sequence

1. Independently review this offline contract.
2. Obtain and review current context-limit evidence without a provider call.
3. Generate and freeze the actual hash-only five-source manifest in a separate
   no-call evidence change.
4. Independently reconcile the frozen manifest.
5. Implement and review a separate immutable development-execution transaction.
6. Obtain new owner authorization bound to that manifest and execution plan.
7. Perform at most the reviewed invocation count with zero retries.
8. Audit execution evidence before Stage 4E evaluation and owner review.
