# Stage 4D v0.1 semantic-contract coverage audit

## Status and scope

This document records the offline semantic-contract diagnosis following the
closed first real Stage 4D bounded development execution. It does not modify the
v0.1 prompt, provider schema, application models, request identities or
execution evidence. It does not implement or execute a recovery version.

## Observed failure

The first S001 provider call completed successfully and its response was cached.
Deterministic local validation then rejected `entities.0` because an alias was
equal to `canonical_name` after casefolding.

The OpenAI strict JSON Schema represents `canonical_name` as a string and
`aliases` as an array of strings. It cannot compare those values after Unicode
casefolding. Prompt v0.1 also does not explicitly tell the model to exclude the
canonical name and case-only duplicates from `aliases`.

The result is therefore a model-output semantic failure combined with a prompt
coverage gap and an application-validator/JSON-Schema expressiveness gap. It is
not a provider transport failure. The local validator behaved correctly and
must not be weakened to accept the response.

## Structural and semantic layers

The provider schema correctly enforces closed objects, required fields,
canonical predicate variants, predicate-compatible subject and value types,
declared qualifier keys and `extraction_method="llm"`.

Application validation must continue to enforce rules that the current static
provider schema cannot reliably represent, including:

- alias inequality and alias uniqueness after casefold;
- cross-item entity, evidence and candidate ID uniqueness;
- source membership and fact/evidence source agreement;
- evidence-reference membership and absence of dangling IDs;
- exact request evidence, block and location reconciliation;
- semantic grounding and review boundaries.

## High-risk provider-schema coverage gaps

Future offline hardening must address or explicitly retain deterministic checks
for these schema-valid but locally invalid classes:

1. aliases equal to the canonical name or duplicated after casefold;
2. blank or empty required qualifier values;
3. empty, duplicate, blank or padded source and evidence identifiers;
4. duplicate object IDs and dangling evidence references;
5. source disagreement across result, fact and evidence objects;
6. blank supported evidence excerpts or supported fact raw values;
7. negative serialized monetary amounts;
8. invalid page or slide locator strings;
9. blank candidate or result warnings.

Rules expressible within the supported provider JSON Schema subset may be added
to a new versioned provider profile. Cross-field, casefold, request-specific,
referential and semantic rules must remain deterministic post-provider checks.

## Recovery identity boundary

Any recovery must be additive and separately reviewed. At minimum it requires:

- prompt version `0.2` and new prompt bytes;
- a new `llm-extraction-baseline-v0.2` experiment identity;
- new request IDs, prompt hashes, canonical request hashes and cache identities;
- new provider/model configuration identities if the strict provider schema is
  hardened;
- a new manifest, execution plan, authorization and execution ID;
- separate v0.2 marker, failure, cache and execution-record paths.

`CandidateExtractionResult` schema `0.1` and its output-contract identity may
remain unchanged if the application model and local semantics are preserved.
The existing v0.1 response and artifacts must remain immutable and must not be
reused under a new request identity.

No v0.2 prompt/schema hardening, manifest, authorization, provider call,
candidate output or evaluation exists as a result of this audit.
