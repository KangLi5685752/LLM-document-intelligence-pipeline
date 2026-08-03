# Stage 4D OpenAI Preflight Contract

## Scope

Stage 4D-2A implements an offline contract and test harness for one possible
future OpenAI Responses API compatibility preflight. This change does not
construct a real client, configure credentials, make an API request or create a
preflight evidence artifact.

The existing canonical request and provider-payload builders read only the two
installed, frozen prompt-package assets. The harness permits no development or
held-out document access, gold or source-register access, manifest access,
document discovery or arbitrary repository-file access.

No project-account access, live strict-schema acceptance, returned model
identity, snapshot or version identity, current pricing, or current provider
retention terms have been verified.

## Future authorization boundary

A real preflight requires a separate explicit project-owner authorization that
permits exactly one provider call under the fixed
`single-synthetic-openai-preflight-v0.1` scope. There is no default or implicit
authorization.

The future request uses one fixed synthetic evidence block. `S001` is used only
as an administrative placeholder required by the frozen request contract. No
real S001, development or held-out document text is transmitted.

## Reviewed observations

The caller must supply dated, reviewed pricing and data-control observations on
the UTC execution date. Pricing values are observations, not permanent project
constants. Requiring `store=false` is not represented as a zero-retention
guarantee; the reviewed retention and abuse-monitoring limitation must remain
explicit.

Every separately provider-exposed model-version or snapshot field must be
recorded by name and value in the same provider observation that returns the
response. The transient observation accepts only typed public-metadata entries
whose values are strings, integers, booleans or null. It rejects nested values
and sensitive paths. The observation derives its ordered field-path inventory
and canonical SHA-256 internally; callers cannot supply either independently.

The exact `response.id`, `response.model`, `response._request_id` and
`sdk.version` entries must reconcile with the provider response. Every explicit
version/snapshot identifier must also reconcile with an entry of the same name
and value. The provenance source response ID must equal that response ID. The
final canonical preflight record retains only the derived metadata hash and
field paths, never the transient metadata values. If the provider exposes no
separate field, the same-call observation must use the literal value
`unavailable`; that value is rejected if the metadata projection nevertheless
contains a separate model-version, snapshot or revision field. Case and
hyphen/underscore variants are normalized for this contradiction check, while
the required `sdk.version` entry remains allowed because it records SDK rather
than model provenance. SDK identity, including `sdk.version`, `sdk_version`,
`provider_sdk_version` and normalized path variants, can never be supplied as a
model-version or snapshot identifier. Model aliases, returned model IDs,
response IDs, request IDs and created timestamps are not inferred as snapshot
identifiers, and hyphenated identity aliases cannot be supplied as version
provenance.

One shared semantic validator protects both the transient provider observation
and the final record. It requires the four exact standard metadata paths,
rejects version-bearing paths when provenance is `unavailable`, and requires
every explicit provenance path to remain in the final field inventory. The
observation additionally reconciles metadata values. These semantic checks are
independent of, and run before acceptance of, a correctly recomputed record
self-hash.

The offline same-call observation contract is implemented in Stage 4D-2A.
Stage 4D-2B implements and tests the SDK bridge offline. The bridge delegates to
the existing adapter's shared execution primitive exactly once and binds the
validated provider response to the exact SDK response object returned by that
injected call. It inspects only the SDK response's public
`model_dump(mode="python")` mapping, records the four required standard metadata
entries, and requires the dumped top-level `id` and `model` to reconcile exactly
with the mapped provider response. It recursively discovers separately exposed
version-like string fields in mappings, lists and tuples, using deterministic
zero-based index path segments, while excluding identity, every descendant of a
normalized `sdk` or `*_sdk` namespace, and sensitive content fields. Every valid
separate identifier is preserved with its full response path; unsupported
iterable containers fail closed without being consumed outside sensitive
subtrees, invalid values and normalized duplicates fail closed, and when no
identifier is exposed the bridge records the literal `unavailable`. Ordinary
public-serialization exceptions are mapped to the typed preflight metadata
failure without catching process-control base exceptions.

Implementation and testing constructed no real OpenAI client, accessed no API
key, made no network or API request, and did not run the real synthetic
preflight. Project-account access, the returned live model identity, any live
snapshot or version identity, current pricing and data-control terms, and live
strict-schema compatibility therefore remain unverified. One real preflight
call still requires explicit project-owner authorization and same-day reviewed
terms.

## Downstream gates

A successful real synthetic preflight would establish only the bounded
compatibility observations recorded by that request. It would not authorize a
five-source development execution. Development-manifest generation, independent
manifest review and project-owner execution authorization remain separate
gates. Held-out execution remains unauthorized.
