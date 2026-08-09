# Stage 4D v0.2 semantic-hardening plan

## 1. Scope and non-goals

This plan defines the minimum safe additive recovery from the closed Stage 4D
development execution v0.1. The recovery is prompt-first: introduce explicit
semantic guidance in prompt v0.2, preserve the strict local
`CandidateExtractionResult` validation boundary and migrate every request,
cache, manifest, execution and authorization identity to v0.2.

This is a plan-only artifact. It does not:

- implement or install prompt v0.2 assets;
- change the candidate schema, provider schema, provider adapter, request
  builder, cache or transaction;
- generate a v0.2 manifest, execution plan or authorization;
- read, repair, normalize, delete or reuse the immutable v0.1 response;
- weaken a local validator or add post-response mutation;
- make a provider call, construct a provider client or access a credential;
- access development documents, gold, matcher or evaluation data; or
- authorize development or held-out execution.

The v0.1 attempt marker, failure record and cache record are closed historical
evidence. They remain immutable and cannot satisfy any v0.2 identity or gate.

## 2. Observed v0.1 failure

The first real request was `llm-v0.1-S001-primary-001`. The provider completed
one call successfully, returned model identifier
`gpt-5.4-mini-2026-03-17`, used zero retries and installed its append-only cache
record. Deterministic local validation then rejected `entities.0` with:

`Value error, alias cannot equal canonical_name after casefold`

The failure occurred after provider success. It was an application-level
semantic validation failure, not an API transport or strict-JSON structural
failure. Prompt v0.1 did not explicitly tell the model that an alias must not
repeat the canonical name after casefolding. The provider JSON Schema can type
`canonical_name` and `aliases`, but it cannot compare those separate values
using Unicode casefold semantics.

The local validator behaved correctly. V0.1 must not be rerun, relabelled as a
success or repaired in place. This plan relies on the existing Stage 4D v0.1
semantic-contract coverage audit and does not inspect the raw cached response.

## 3. Proposed prompt v0.2 changes

Prompt v0.2 must retain the existing evidence-only, development-only and
non-authoritative boundaries and add concise, explicit semantic instructions.
The installed `system_v0_2.txt` and `extraction_v0_2.txt` assets must together
state that:

- `canonical_name` is the preferred entity name;
- `aliases` contains only genuine alternative names;
- an alias must never repeat `canonical_name`, including a case-only or other
  Unicode-casefold equivalent;
- aliases must be unique after casefolding;
- identifiers and textual contract fields must be trimmed and nonblank;
- the result, entities, evidence references and facts may use only the supplied
  source ID;
- evidence IDs may use only supplied evidence, must be nonblank and must be
  unique wherever the contract requires uniqueness;
- supported evidence requires a meaningful, nonblank excerpt;
- supported facts require a meaningful, nonblank `raw_value`;
- required qualifier values must be meaningful and must not contain blank
  required strings or blank list members;
- entity, evidence-reference and candidate IDs must each be unique within the
  result;
- every fact evidence ID must resolve to a returned evidence reference and to
  supplied request evidence;
- supplied source ID, evidence ID, block ID, location type and location value
  must be preserved exactly rather than reformatted or inferred;
- ambiguous or uncertain candidates use the existing review-routing fields
  where the contract requires review;
- warnings, when present, must be meaningful and nonblank; and
- abstention is preferable to fabrication, unsupported inference or invented
  provenance.

Immediately before emitting the strict JSON object, the prompt must require a
concise semantic self-check covering alias casefold rules, ID uniqueness,
source and evidence membership, nonblank supported values, qualifier
completeness, provenance preservation and review routing. The self-check is an
instruction to the model, not a substitute for deterministic validation. It
must not ask the application to delete aliases, repair IDs, normalize output or
otherwise mutate a returned response.

Prompt text must remain source-independent. It must not contain real gold
facts, expected source-specific outputs, owner decisions or special cases for
S001 or any other source.

## 4. Provider-schema change decision

No provider JSON Schema change is recommended for this v0.2 recovery.

The observed defect is a cross-field Unicode-casefold comparison. The other
highest-risk gaps are principally cross-item uniqueness, request-specific
membership, referential integrity, exact provenance reconciliation and
semantic meaningfulness. These belong at the deterministic application
boundary and cannot be replaced by a static provider schema.

The existing provider schema already supplies useful structural constraints:
closed required objects, declared candidate fields, predicate-specific subject
and value types, declared qualifier keys, `extraction_method="llm"`, bounded
enums and the serializable scalar constraints already derived from the
application models. Adding provider-only keywords solely to duplicate local
rules would not solve the casefold defect and would create new provider,
model-configuration and compatibility identities without sufficient value.

Consequently v0.2 keeps all of the following unchanged:

- provider configuration ID
  `openai-responses-text-strict-json-v0.1`;
- model configuration ID
  `openai-gpt-5.4-mini-text-strict-json-v0.1`;
- response-schema name `candidate_extraction_result_0_1`;
- output contract ID `candidate-extraction-result-0.1`;
- `CandidateExtractionResult` schema version `0.1`; and
- strict-schema SHA-256
  `45655BF2E0824802E2361C47EED4EC86BA5388328AD0301FEC3610C6584B8D74`.

If later offline work identifies a material, supported provider-schema
constraint, that change must be proposed separately. It would invalidate this
no-schema-change decision and require new provider/model configuration and
response-profile identities plus a fresh compatibility decision before a paid
development call.

Another synthetic compatibility preflight is not recommended for the planned
prompt-only v0.2. The successful synthetic preflight v0.3 already established
the selected Responses API, requested model, strict Structured Outputs and
returned-model provenance boundary. Changing prompt text changes request and
payload hashes but does not create a new schema-compatibility question. A new
synthetic paid call would be reconsidered only if the provider schema or API
configuration changes materially.

## 5. Unchanged application semantic invariants

The existing local validation remains authoritative and fail-closed. V0.2 must
continue to reject, without repair:

- blank, padded or duplicate identifiers where the contract requires trimmed
  unique values;
- an alias equal to `canonical_name` after casefolding;
- aliases duplicated after casefolding;
- unknown predicates, incompatible subject/value types, undeclared qualifiers
  and missing meaningful required qualifiers;
- empty or duplicate fact evidence IDs and dangling evidence IDs;
- duplicate entity, evidence-reference or candidate IDs;
- result, entity, fact or evidence source disagreement;
- evidence not present in the approved request;
- block or location data that differs from the approved evidence block;
- blank excerpts for supported evidence and blank raw values for supported
  facts;
- invalid page or slide locations and negative normalized money;
- blank candidate or result warnings; and
- invalid review routing or extraction-method semantics.

Strict JSON parsing, request identity validation, source allowlisting,
same-response provider provenance, append-only cache validation and all
transaction gates also remain unchanged in intent. No warning, alias, fact or
evidence item may be silently removed or rewritten after provider return.

## 6. Version and identity migration

The future implementation must preserve v0.1 code paths and artifacts while
adding a separately reviewable v0.2 identity family.

| Boundary | Closed v0.1 identity | Proposed v0.2 identity or rule |
| --- | --- | --- |
| Experiment | `llm-extraction-baseline-v0.1` | `llm-extraction-baseline-v0.2` |
| Prompt version | `0.1` | `0.2` |
| Prompt assets | `system_v0_1.txt`, `extraction_v0_1.txt` | `system_v0_2.txt`, `extraction_v0_2.txt` |
| Candidate schema | `CandidateExtractionResult` `0.1` | unchanged `0.1` |
| Output contract | `candidate-extraction-result-0.1` | unchanged |
| Provider configuration | `openai-responses-text-strict-json-v0.1` | unchanged |
| Model configuration | `openai-gpt-5.4-mini-text-strict-json-v0.1` | unchanged |
| Response-schema name | `candidate_extraction_result_0_1` | unchanged |
| Strict-schema hash | `45655BF2...B8D74` | unchanged exact 64-character value stated above |
| Request IDs | `llm-v0.1-{source_id}-{role}-{ordinal:03d}` | `llm-v0.2-{source_id}-{role}-{ordinal:03d}` |
| First recovery request | `llm-v0.1-S001-primary-001` | `llm-v0.2-S001-primary-001` |
| Evidence IDs | `llm-evidence-v0.1-{source_id}-{block_id}` | `llm-evidence-v0.2-{source_id}-{block_id}` |
| Whole-block partition policy | `provider-payload-whole-block-greedy-v0.1` | `provider-payload-whole-block-greedy-v0.2`, with the same algorithm and 200,000-byte ceiling but the v0.2 evidence-ID template |
| Repeat-selection policy | `largest-primary-provider-payload-request-id-tiebreak-v0.1` | unchanged; rerun against the new v0.2 primary inventory |
| Cache root | `.cache/llm_extraction/llm-extraction-baseline-v0.1/openai/` | `.cache/llm_extraction/llm-extraction-baseline-v0.2/openai/` |
| Manifest artifact | `openai-gpt-5.4-mini-five-source-development-manifest-v0.1.json` | `reports/llm_extraction/openai_development_manifest/openai-gpt-5.4-mini-five-source-development-manifest-v0.2.json` |
| Manifest schema | `0.1` | unchanged `0.1` if its structure is unchanged; the artifact identity and self-hash are new |
| Execution-plan artifact | `openai-gpt-5.4-mini-five-source-development-execution-plan-v0.1.json` | `reports/llm_extraction/openai_development_execution_plan/openai-gpt-5.4-mini-five-source-development-execution-plan-v0.2.json` |
| Execution-plan schema | `0.1` | unchanged `0.1` if its structure is unchanged; the artifact identity and self-hash are new |
| Execution ID | `openai-gpt-5.4-mini-five-source-development-execution-v0.1` | `openai-gpt-5.4-mini-five-source-development-execution-v0.2` |
| Authorization scope | `bounded-five-source-openai-development-execution-v0.1` | `bounded-five-source-openai-development-execution-v0.2` |
| Confirmation phrase | `EXECUTE_BOUNDED_FIVE_SOURCE_OPENAI_DEVELOPMENT_V0_1` | `EXECUTE_BOUNDED_FIVE_SOURCE_OPENAI_DEVELOPMENT_V0_2` |
| Execution root | `.../openai-gpt-5.4-mini-five-source-development-v0.1/` | `reports/llm_extraction/openai_development_execution/openai-gpt-5.4-mini-five-source-development-v0.2/` |
| Attempt markers | v0.1 root plus `{cache_identity_sha256}.attempt.json` | v0.2 execution root plus `attempts/{cache_identity_sha256}.attempt.json` |
| Failure records | v0.1 root plus `{cache_identity_sha256}.failure.json` | v0.2 execution root plus `failures/{cache_identity_sha256}.failure.json` |
| Final execution record | v0.1 `execution-record.json` | v0.2 execution root plus `execution-record.json` |

Prompt SHA-256, canonical request SHA-256, provider-payload SHA-256 and cache
identity SHA-256 are derived identities, not names that this plan may invent.
Every value must be recomputed from installed prompt v0.2 bytes and the exact
new request, recorded in the v0.2 manifest, reconciled into the execution plan
and independently reviewed. Each must differ from the corresponding v0.1
identity where prompt/request content participates in the hash. The manifest
and execution-plan self-hashes and outer file hashes must likewise be newly
computed; reusing a v0.1 hash is an error.

The new prompt can change serialized payload sizes. The future manifest must
therefore rerun whole-block partitioning and derive the request count, ordinals,
repeat target, token estimates and cost ceiling from the v0.2 payloads. This
plan does not assume that the v0.1 eight-invocation inventory remains bytewise
or numerically identical.

### V0.1 compatibility and additive implementation boundary

The current repository carries v0.1 identity and `Literal` constraints across
multiple shared layers, including:

- `src/document_intelligence/llm_extraction/contracts.py`;
- `src/document_intelligence/llm_extraction/prompting.py`;
- `src/document_intelligence/llm_extraction/cache.py`;
- `src/document_intelligence/llm_extraction/manifest.py`;
- `src/document_intelligence/llm_extraction/provenance.py`;
- `src/document_intelligence/llm_extraction/openai_development_manifest.py`;
- `src/document_intelligence/llm_extraction/openai_development_execution_plan.py`;
  and
- `src/document_intelligence/llm_extraction/openai_development_execution.py`.

The future implementation must therefore be additive and version-aware. It
must not replace the existing global v0.1 experiment or prompt identity in a
way that causes historical v0.1 requests, cache records, manifests, provenance
records, execution plans, attempt markers, failure records or execution records
to be interpreted as v0.2.

Existing v0.1 prompt assets and canonical request, cache and evidence behavior
must remain valid and covered by regression tests. V0.2 may use additive V02
models, explicitly version-selected builders or a carefully generalized
version-aware contract only if exact v0.1 serialized bytes and validation
behavior remain unchanged.

Broadening a `Literal` or shared model is not automatically harmless. Any
shared-model change must prove that existing v0.1 canonical serialization,
hashes, loaders and rejection behavior are unchanged. The implementation must
not merely change `EXPERIMENT_ID`, `PROMPT_VERSION`, `SYSTEM_PROMPT_NAME`,
`EXTRACTION_PROMPT_NAME`, cache-root constants, request/evidence templates or
execution constants globally from v0.1 to v0.2.

The immutable v0.1 execution evidence from PR #44 must remain valid under the
production loaders after all v0.2 offline tests. Required compatibility
regressions must prove that:

- v0.1 prompt hashes remain stable;
- representative v0.1 canonical request bytes and hashes remain stable;
- a representative v0.1 cache identity remains stable;
- the frozen v0.1 manifest and execution plan still validate;
- committed v0.1 attempt and failure evidence still validate; and
- no v0.2 request can consume a v0.1 cache or execution identity.

## 7. Regression-test matrix

All fixtures must be fictional and offline. Tests must exercise the real
application models, `validate_provider_output`, identity builders, cache and
transaction guards rather than copied expressions. No test may load the real
v0.1 cached response, real gold or held-out content.

| Case | Required fixture or mutation | Required result |
| --- | --- | --- |
| Canonical-name alias | `canonical_name="X"`, `aliases=["x"]` | deterministic application rejection for casefold equality |
| Duplicate aliases | aliases that differ only by case | deterministic application rejection |
| Blank aliases | empty, whitespace-only and padded alias variants | rejection without trimming or deletion |
| Required qualifiers | blank required string or blank required list member for a predicate requiring meaningful qualifiers | predicate/application rejection |
| Empty fact evidence | `evidence_ids=[]` | rejection |
| Duplicate fact evidence | the same evidence ID twice | rejection |
| Dangling evidence | fact refers to an unreturned or unsupplied evidence ID | rejection |
| Duplicate object IDs | separate cases for entity, evidence-reference and candidate IDs | rejection at result reconciliation |
| Source disagreement | result, entity, evidence or fact uses a source other than the fictional request source | rejection |
| Blank supported excerpt | supported evidence with empty or whitespace-only excerpt | rejection |
| Blank supported raw value | supported fact with empty or whitespace-only `raw_value` | rejection |
| Invalid location | zero, negative, non-ASCII-digit or nonnumeric page/slide value, plus approved-block location mismatch | rejection |
| Negative money | normalized money amount below zero | rejection |
| Blank warnings | blank candidate warning and blank result warning | rejection |
| Valid semantic output | fictional valid candidate satisfying all constraints | accepted byte-for-byte without repair |
| Prompt content | prompt v0.2 contains every required rule and the final semantic self-check, with no source-specific or gold text | pass exact text/contract assertions |
| Prompt determinism | LF/CRLF input normalization yields the same canonical v0.2 prompt hash while prompt v0.1 assets remain unchanged | deterministic pass |
| Version separation | otherwise equivalent v0.1 and v0.2 fictional requests | different prompt SHA, canonical request SHA and provider-payload SHA |
| Cache separation | construct v0.1 and v0.2 fictional cache identities for equivalent evidence | v0.1 cache cannot satisfy the v0.2 read; paths and hashes differ |
| Immutable failure | fictional response reproducing the alias defect | rejected and retained unchanged; no repair function or mutation path is invoked |
| Provider boundary | prompt-only v0.2 request with unchanged schema/configuration | one fake-client call at most, zero SDK retries, exact existing provider controls |
| Held-out isolation | `S005`, `S007` and unknown source IDs with path/client/cache spies | rejected before path access, cache access, credential access or provider invocation |

Additional manifest and transaction regression tests must prove that v0.2
cannot load a v0.1 manifest, plan, authorization, marker, failure record, final
record or cache entry; that hashes reconcile across every v0.2 layer; and that
the v0.1 files remain byte-identical after the offline test run.

## 8. Bounded recovery execution design

The recovery is a new transaction, not a continuation of v0.1:

1. Implement prompt v0.2 and additive version-aware request construction while
   preserving v0.1 prompt assets and historical artifact loaders.
2. Complete the regression matrix and an independent source-independence and
   no-repair review before generating a real manifest.
3. Generate a new five-source development manifest from the same approved
   development routing boundary only. Recompute partitions, request IDs,
   prompt/request/payload/cache hashes, call budget and conservative cost from
   v0.2 bytes. Do not supply gold, deterministic candidates or owner outcomes.
4. Independently review and freeze the v0.2 manifest.
5. Build and independently review a new v0.2 execution plan and additive
   transaction implementation bound to that exact manifest.
6. Obtain a new project-owner authorization bound to the exact v0.2 manifest
   hash, plan hash, execution ID, authorization scope, maximum calls, attempts
   and cost cap, with same-day pricing and data-control observations.
7. If separately authorized, make `llm-v0.2-S001-primary-001` the first
   meaningful paid recovery call. It must use the new cache root and may not
   consume the v0.1 S001 cache record.
8. Continue to later v0.2 development invocations only after S001 passes strict
   provider mapping, unchanged local semantic validation, evidence/request
   reconciliation, cache verification and transaction gates. Stop at the first
   failure.
9. Run the one deterministic repeat selected from the regenerated primary
   inventory only at its frozen final position.
10. Install the v0.2 final execution record last and only after every frozen
    invocation succeeds.

The existing controls remain the baseline: `gpt-5.4-mini`, returned-model
provenance capture, OpenAI SDK `2.46.0`, strict JSON Schema, `store=false`, no
tools, reasoning effort `none`, `max_output_tokens=4096`, timeout 120 seconds,
provider-side retries zero and transaction retries zero. The new manifest and
plan must derive exact aggregate limits instead of copying v0.1 totals.

### Review efficiency

Independent review checkpoints may be combined where they examine the same
frozen implementation state. The project does not require redundant repeated
full-suite or full-repository reviews when no relevant bytes changed. Before a
real provider call, however, the final manifest, execution plan, transaction
implementation and authorization binding still require one complete independent
pre-execution review.

## 9. API-call readiness gates

No v0.2 provider call may occur until all of these gates pass in order:

1. Prompt v0.2 assets and additive request/version code are reviewed, frozen
   and installation-safe; prompt v0.1 bytes are proven unchanged.
2. The complete fictional regression matrix passes offline across supported
   Python versions, with no real credential, client, network or document use.
3. The unchanged CandidateExtractionResult 0.1 and strict provider schema hash
   are reconciled. Any schema or API-configuration change stops this plan and
   requires a new compatibility decision.
4. A newly generated v0.2 manifest passes canonical self-hash, source-route,
   partition, payload, cache-identity, context, token and cost validation.
5. Independent review approves the exact manifest inventory and confirms that
   only S001, S002, S003, S004 and S006 development text can be supplied.
6. A new v0.2 execution plan binds the exact manifest, provider controls,
   invocation order, attempt/failure paths, final-record path and derived
   budgets; its hashes are independently verified.
7. The additive v0.2 transaction passes fake-client success, semantic failure,
   cache conflict, crash residue, date rollover, budget, credential-scrubbing
   and rollback/failure-evidence tests.
8. Repository status and artifact inventory prove that v0.1 evidence is
   unchanged and no conflicting v0.2 marker, failure or final record exists.
9. A fresh explicit project-owner authorization binds the exact v0.2 plan,
   manifest, execution ID, scope, maximum calls, attempts and cost cap.
10. Current account/model access, returned-model provenance rules, pricing,
    context limit and data controls are reviewed; required observations are
    valid for the UTC execution date.
11. The real-mode confirmation phrase and all local gates pass before
    credential access, client construction, marker creation or provider entry.
12. Immediately before the first call, the transaction revalidates the
    development allowlist, held-out denial, budgets, append-only cache state
    and first request ID `llm-v0.2-S001-primary-001`.

Passing this plan review, by itself, satisfies none of the execution gates.

## 10. Rollback and failure-evidence policy

V0.2 uses forward-only, append-only evidence rather than rollback:

- check the v0.2 cache before installing an attempt marker;
- install an exclusive v0.2 marker before credential access, client
  construction or a possible provider call;
- allow at most one provider call for a cache miss and never retry;
- install a successful provider response in the v0.2 cache before local
  candidate validation so original-call evidence survives a later semantic
  failure;
- never place a v0.1 response under a v0.2 cache identity;
- on provider, cache, local semantic or record-validation failure, stop the
  transaction and preserve the marker, any installed cache record and one
  sanitized self-hashed v0.2 failure record where filesystem state permits;
- retain only safe provenance and stable error information in failure evidence,
  never credentials, prompts, raw output or document text;
- treat a marker without a cache record as possible-call evidence that blocks
  automatic reuse of that v0.2 invocation;
- never delete or overwrite a marker, cache entry, failure record or historical
  artifact to enable another attempt; and
- install the final execution record exclusively and last.

A v0.2 semantic failure is diagnosis evidence, not permission to edit the
cached response. Any further paid recovery after a terminal v0.2 failure
requires a new additive version, plan, identities, review and authorization.

## 11. Exact definition of v0.2 execution success

The bounded v0.2 development execution succeeds only when:

- the exact independently frozen manifest and execution plan validate;
- every regenerated invocation runs once in the frozen order or is satisfied
  by an already valid cache entry with the exact same v0.2 identity;
- every provider return has complete same-call request, response, model, SDK,
  token and hash provenance with zero retries;
- every raw response is cached append-only under its exact v0.2 identity;
- every parsed result satisfies strict JSON, CandidateExtractionResult 0.1,
  predicate, source, evidence, provenance and review-routing validation without
  repair or mutation;
- primary/repeat determinism and all manifest reconciliation checks pass;
- provider calls, attempts, output tokens and actual cost remain within the
  newly authorized exact limits;
- no v0.2 failure record exists;
- one canonical self-hashed final execution record reconciles every invocation
  and is installed last; and
- v0.1 evidence and all held-out boundaries remain unchanged.

Success means completion of this bounded development extraction transaction.
It does not mean that extraction quality is acceptable, that evaluation gates
pass, that the LLM is superior to deterministic v0.4, that a baseline is
frozen, that held-out access is allowed or that the system is production-ready.

## 12. Held-out isolation

V0.2 remains development-only. Only S001, S002, S003, S004 and S006 may be
routed into the future manifest. S005, S007 and unknown sources must fail before
document-path resolution, cache access, credential access, client construction
or provider invocation.

Held-out ParsedDocuments, annotations, semantic gold and execution paths remain
inaccessible. Development gold, expected answers, deterministic candidates,
matcher output and owner outcomes must not enter prompts, provider requests,
cache identities or model-facing tests. Held-out access requires a later,
separately reviewed guard and explicit project-owner authorization; this plan
does not design or grant that authorization.

## 13. Authorization statement

This semantic-hardening plan authorizes no provider execution. It creates no
prompt implementation, manifest, execution plan, transaction, authorization,
attempt marker, cache record, failure record or successful record. Provider
calls, network requests, API-key accesses and held-out accesses performed by
this planning task are all zero.
