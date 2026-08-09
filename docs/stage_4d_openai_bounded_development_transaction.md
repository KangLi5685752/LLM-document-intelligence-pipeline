# Stage 4D bounded OpenAI development-execution transaction

## Purpose

This document records the implemented and independently reviewed Stage 4D
bounded development-execution transaction for the approved five-source OpenAI
development comparison.

The transaction implements the previously frozen execution plan. It does not
itself create project-owner authorization and does not authorize or perform a
real provider execution.

## Frozen execution boundary

The transaction is bound to:

- execution ID
  `openai-gpt-5.4-mini-five-source-development-execution-v0.1`;
- authorization scope
  `bounded-five-source-openai-development-execution-v0.1`;
- execution-plan self-hash
  `F92DBA083F5A92E6EFFF0E7D58B9D05553934AD3689FB90A3D091BD39D9D29A7`;
- execution-plan LF-content SHA-256
  `FFFE07FEA0F19FF46B4B5F060B012699BA1A68E6C9BDE94AF7E7CF93E6956F93`;
- manifest self-hash
  `05ABF3D0FA785B845E0853B907B911EE1A9439F0997052D3603E025AAAA30D0E`;
- manifest LF-content SHA-256
  `15DF5E959040B399EDF8CA5455B5060EF71B6672C97D9901E6DB084FE9ACC069`.

The frozen invocation inventory remains seven primary requests followed by one
deterministic S004 repeat. Only S001, S002, S003, S004 and S006 are approved.

## Transaction architecture

The implementation adds a default-deny production transaction that:

- validates the exact frozen plan and manifest before execution can become
  possible;
- reconstructs all eight requests through the existing production builders and
  reconciles request, prompt, schema, payload and cache identities;
- requires a new execution-specific project-owner authorization;
- requires same-day UTC pricing and data-control observations;
- revalidates those dated terms before every new cache-miss provider attempt;
- uses the existing append-only `ResponseCache`;
- checks cache before creating an attempt marker;
- installs an exclusive invocation-specific marker before credential access,
  client construction or provider execution;
- permits at most one provider call per cache miss and performs zero retries;
- caches a successful provider response before local candidate validation;
- preserves successful cache records after later local-parse failures;
- stops after the first provider or local failure;
- installs a final execution record only after all eight invocations validate.

The production CLI is exposed as:

`run-openai-development-execution`

Readiness is the default mode. Real execution additionally requires an explicit
execution flag, the exact confirmation phrase and separately supplied valid
authorization and dated observations.

## Authorization boundary

The development authorization contract binds:

- the exact execution ID and authorization scope;
- the frozen execution-plan SHA-256;
- the frozen manifest SHA-256;
- maximum provider calls `8`;
- maximum total attempts `8`;
- cost cap USD `1.25`;
- explicit project-owner identity;
- UTC authorization timestamp;
- explicit real development-execution authorization.

No such real authorization was created during implementation or review.

Historical synthetic-preflight authorizations cannot satisfy this contract. The
successful v0.3 authorization remains consumed and closed.

## Provider and budget controls

The transaction preserves:

- provider `openai`;
- requested alias `gpt-5.4-mini`;
- pinned SDK `2.46.0`;
- strict JSON Schema output;
- `store=false`;
- no tools;
- reasoning effort `none`;
- timeout `120` seconds;
- maximum output tokens `4096` per invocation;
- maximum aggregate output tokens `32768`;
- maximum provider calls `8`;
- maximum attempts `8`;
- retries `0`;
- frozen conservative cost ceiling USD `0.9953895`;
- authorization cap USD `1.25`.

Pricing drift that invalidates the frozen plan fails closed rather than
silently changing the plan.

## Cache and original-call provenance

`CacheRecord` now supports an optional typed OpenAI original-call provenance
envelope.

The additive envelope preserves safe same-call metadata required for later
cache-only local reprocessing:

- exact model-version or snapshot provenance;
- literal `unavailable` only when the original provider call exposed no
  separate identifier;
- source provider-response ID;
- canonical public-metadata SHA-256;
- exact public-metadata path inventory;
- explicit same-call observation status.

It does not persist the SDK response object, credentials, headers, raw prompts
or unrestricted provider metadata.

When the additive envelope is absent, legacy Stage 4C cache serialization and
hash calculation remain unchanged. Existing legacy cache bytes therefore remain
compatible.

The bounded OpenAI transaction fails closed when a cache record does not
contain sufficient original-call provenance for a valid development execution.

## Attempt-marker semantics

For a cache miss:

1. cache is checked first;
2. existing marker state is reconciled;
3. same-day terms are revalidated;
4. a pending marker is constructed;
5. the marker is installed exclusively;
6. only after successful installation does it become durable transaction state;
7. credential and client boundaries may then be crossed.

A marker without a valid cache record permanently blocks another provider
attempt for that invocation in v0.1.

Existing markers are reconciled against the current:

- execution ID;
- execution-plan SHA-256;
- manifest SHA-256;
- authorization SHA-256;
- invocation order;
- request ID;
- cache identity;
- exact frozen marker path.

A competing process that wins exclusive marker installation leaves the losing
transaction with no provider side effect and no failure record referring to an
uninstalled marker.

## Failure semantics

Pre-attempt safety refusals that occur before any durable invocation state
exists do not consume the invocation.

If there is:

- no installed marker;
- no cache;
- no provider call;
- no local parse;

the sanitized error is raised without installing the invocation failure
record.

Durable failures continue to produce immutable sanitized evidence where
appropriate, including failures after marker installation and local parse
failures involving an existing successful cache.

Failure evidence excludes credentials, raw prompts, evidence text, raw
responses, arbitrary SDK exception dumps and candidate content.

## UTC rollover recovery

A pricing or data-control observation must:

- use the current execution UTC date; and
- not be timestamped in the future relative to the gate.

The same check occurs immediately before every new cache-miss attempt marker.

If UTC rolls into a new date during a transaction, the next new provider
attempt stops before marker installation or provider-side work.

After fresh reviewed observations are supplied for the new UTC date, an
unconsumed invocation can continue. Already completed invocations are reused
from cache without another provider call.

## Held-out isolation

The transaction remains development-only.

It does not load or use:

- S005;
- S007;
- held-out ParsedDocuments;
- held-out semantic annotations;
- gold labels for scoring;
- deterministic candidate outcomes;
- project-owner evaluation outcomes.

Stage 4E evaluation is a separate later step.

## Independent review

The transaction underwent multiple independent read-only review passes.

The reviews identified and required correction of:

1. loss of provider-exposed model-version/snapshot provenance during
   cache-only recovery;
2. incomplete reconciliation of existing attempt markers;
3. a same-day terms-gate UTC timing window;
4. permanent failure evidence being created for pre-attempt safety refusals;
5. durable marker state being assigned before exclusive marker installation
   completed.

All required corrections were implemented and regression-tested.

The final marker-installation review confirmed that the durable marker variable
is assigned only after successful exclusive installation and that a losing
concurrent transaction cannot create a failure record referencing an
uninstalled marker.

Final independent review verdict:

`approved_for_evidence_commit`

## Validation

Stage 4C cache tests:

- `22 passed`;
- `4` expected Windows link-privilege skips.

Final transaction, CLI and cache validation:

- `75 passed`;
- `5` expected Windows link-privilege skips.

Broader affected Stage 4B-4D regression suite:

- `727 passed`;
- `8` expected platform skips.

Complete offline suite:

- `1834 passed`;
- `14` expected Windows symbolic-link, junction or reparse-point privilege
  skips;
- `0 failures`.

Additional validation passed:

- `python -m compileall -q src tests`;
- `git diff --check`.

## Safety evidence

During transaction implementation, testing and independent review:

- real API key accesses: `0`;
- real OpenAI client constructions: `0`;
- real provider calls: `0`;
- network requests: `0`;
- real development authorization artifacts created: `0`;
- real development cache records created: `0`;
- held-out sources accessed: `0`.

The two historical local v0.2 preflight artifacts were not part of the review
or implementation evidence and remain outside this change.

## Current boundary

This milestone establishes the reviewed transaction implementation only.

It does not establish:

- successful five-source LLM extraction;
- extraction quality;
- superiority over the deterministic baseline;
- held-out generalization;
- production readiness.

Provider execution remains separately unauthorized.

The next controlled step is to integrate this implementation through review,
commit, PR and CI. Only after integration may a new explicit project-owner
authorization and fresh same-day terms evidence be prepared for the bounded
five-source development execution.
