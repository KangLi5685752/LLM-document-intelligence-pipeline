# Stage 4D OpenAI Preflight Execution Gate

## Scope

The separately authorized synthetic preflight v0.3 completed successfully and
is a closed historical transaction. Its one-call authorization is consumed.
That result verified the previous provider-facing schema and configuration; it
does not verify the later alias-safe provider boundary.

Real development execution v0.2 subsequently showed that prompt-only alias
enforcement was insufficient: the first response again failed the local
alias-versus-canonical-name casefold invariant. PR #49 therefore introduced a
material provider-facing schema change for development v0.3 by retaining the
required `CandidateEntity.aliases` field while constraining it with
`maxItems=0`.

PR #51 implemented an additive, default-deny synthetic compatibility preflight
v0.4 for that exact alias-safe schema and provider configuration. The mandatory
independent pre-real review passed before execution. The later separately
authorized transaction completed successfully with one provider call and zero
retries. Its authorization is consumed, v0.4 is closed and its attempt and
successful record are being frozen as immutable evidence. Held-out execution
remains prohibited.

## Closed v0.1 incident

The authorized v0.1 local transaction created the permanent attempt marker
`openai-gpt-5.4-mini-synthetic-preflight-v0.1.attempt.json` for execution plan
`3FCFBEE20038F4FF0E2406EAD0DB62C683CFD5A3D9313759F29BCF41D006038D`.
The unchanged 517-byte marker has file SHA-256
`5B75790CE978B2AC7C6ECC2CFC00C1B21BF398AB5C622F04F2F67EE05A8B61AC`
and canonical self-hash
`9B5952B20A88152EBC4FD14026515AAB70397144736A0ED1762585ECEAF93967`.
It produced no successful record and returned the stable local error
`provider_api_failure`. More than one hour later, the OpenAI project evidence
showed Last used as Never, no Responses logs, zero requests, zero tokens and
USD 0.00 spend. A truncated clipboard credential is the leading inference for
the local failure, not a proven fact.

The v0.1 marker is permanent historical evidence. V0.1 is closed, must not be
retried, and is not an authorization for any later preflight.

## Closed v0.2 incident

The separately authorized v0.2 transaction created its permanent attempt marker
and made exactly one provider call with zero retries. Its immutable failure
record states `failure_stage=post_provider_validation`,
`local_error_code=preflight_output_invalid` and
`successful_record_written=false`. The provider response had returned and
`validate_provider_output` had completed, but the v0.2 runner then rejected the
validated result because a separate assertion required empty entity, evidence
and candidate collections plus the expected abstention warning.

That assertion incorrectly mixed technical API/schema compatibility with model
semantic behaviour. The v0.2 response contents are not reproduced or inferred
here, and no exact v0.2 token usage or cost is claimed. Its marker and failure
record remain immutable historical evidence; v0.2 is closed and must not be
retried or retroactively given a success record.

V0.3 uses a distinct preflight ID, authorization scope, confirmation phrase,
request/evidence identifiers and attempt, success and failure filenames. It
does not inspect, modify, replace or count v0.1 or v0.2 artifacts.

The deterministic execution plan contains only fixed identifiers, canonical
hashes, a one-call limit and the three fixed v0.3 repository-relative artifact
paths.
Every hash anchor is derived at runtime from the existing production request,
prompt, strict-schema and provider-payload builders in the same readiness
transaction. This necessarily reads only the two frozen installed prompt text
assets; it does not read environment values, construct a client, access the
network or open development, held-out, gold, manifest, cache or evidence data.
Plan assembly after that derivation is deterministic and side-effect free.

The attempt marker's plan is also enforced at provider entry. An internal
wrapper recomputes the canonical request, prompt, synthetic-document,
strict-schema and exact provider-payload hashes from the exact request supplied
by the existing preflight runner. It delegates once to the existing same-call
metadata bridge only when all five values equal the readiness plan. After the
runner returns, the successful record's corresponding five anchors must
independently reconcile with that same plan before serialization or file
creation.

## Frozen v0.3 live result

The separately authorized transaction used preflight ID
`openai-gpt-5.4-mini-synthetic-preflight-v0.3`, authorization scope
`single-synthetic-openai-preflight-v0.3` and execution-plan SHA-256
`21DEC6F5DE7E79EAC2F80F93ABA41CB96BA815F5000AED9810831F671657D5C5`.
It completed with compatibility and preflight status `passed`, one provider
call and zero retries. The returned model identifier was
`gpt-5.4-mini-2026-03-17`; no separate model-version or snapshot field was
exposed, so that provenance is recorded literally as `unavailable`. The pinned
provider SDK version was `2.46.0`.

Observed usage was 7,332 input tokens and 155 output tokens, latency was 4,600
ms and estimated actual cost was USD 0.0061965. The semantic diagnostic was
`valid_semantic_variance`: zero entities, one evidence reference, zero candidate
facts and the warning `No extractable candidate facts were supported by the
supplied evidence blocks.` This classification remained separate from the
successful technical compatibility result. Raw provider output, prompts,
provider bodies, headers and credentials are not stored in the frozen record.

## Closed alias-safe v0.4 boundary

V0.4 uses preflight ID
`openai-gpt-5.4-mini-synthetic-preflight-v0.4`, authorization scope
`single-synthetic-openai-preflight-v0.4`, confirmation phrase
`EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_4` and separate attempt, success
and failure paths. Its reserved request
`llm-v0.3-S001-primary-999` is an `LLMExtractionRequestV03` built with prompt
version `0.3`, harmless synthetic text only and the development-v0.3 provider
and model identities.

The plan and provider-entry checks explicitly use
`DEFAULT_OPENAI_RESPONSES_CONFIGURATION_V0_3`,
`build_openai_candidate_schema_v0_3()` and the corresponding explicit payload
configuration. The strict provider schema keeps aliases required, uses an
array type and sets `maxItems=0`; the local `CandidateEntity` and
`CandidateExtractionResult` 0.1 contracts remain unchanged. V0.4 preserves the
compatibility-versus-semantics separation: a locally valid response is either
`expected_abstention` or `valid_semantic_variance`, and either may support a
technical compatibility pass.

## Frozen v0.4 live result

The successful transaction used execution-plan SHA-256
`F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E`.
It returned model `gpt-5.4-mini-2026-03-17` through provider SDK `2.46.0`;
no separate model-version or snapshot field was exposed, so provenance is
recorded literally as `unavailable`.

The call used 7,594 input tokens and 177 output tokens, took 4,634 ms and cost
an estimated USD 0.006492. Compatibility and preflight status are `passed`, the
alias-safe strict schema is compatible and local output validation is `valid`.
The semantic diagnostic is `valid_semantic_variance`: zero entities, one
evidence reference, zero candidate facts and the warning `No extractable facts
present in the supplied evidence; abstained from emitting candidate facts.`
This semantic variance does not negate compatibility and is not evidence of
development extraction quality.

## Readiness mode

The command defaults to readiness validation. It loads exactly the three paths
supplied for authorization, pricing and data controls; validates strict UTF-8
JSON and the existing frozen models; validates UTC timing and fixed artifact
absence; and reports only non-sensitive plan identifiers. Readiness mode does
not read `OPENAI_API_KEY`, construct a client, create the output directory or
write an artifact.

Production command execution is bound to the local checkout that contains the
installed execution module, expected project metadata, Git identity and frozen
prompt assets. Launching from that repository root or one of its safe
subdirectories resolves to the same fixed reports path; an unrelated working
directory fails before input loading or credential access. There is no CLI
repository-root override.

The public Python readiness and execution entrypoints also resolve that
verified installed checkout internally and expose no repository-root or
artifact-path override. The console-script `main()` accepts only its normal
optional argument sequence and exposes no clock, credential-reader, client or
root injection. Temporary repository roots, clocks, fictional credentials and
fake clients are accepted only by underscored private helpers used in offline
tests; those helpers are not exported.

Before any supplied JSON path is opened, component-aware repository rules deny
development and held-out documents, gold, evaluation evidence, request
manifests, response caches, deterministic evidence and the preflight output
artifacts. UNC, device-namespace and identifiable remote-drive paths are also
denied before filesystem inspection. Each permitted local input is opened once
through a descriptor-bound regular-file read: its path chain, link and reparse
state, opened descriptor identity, regular-file type and 32 KiB byte limit are
checked without reopening it for JSON parsing.

## Real-mode gate

V0.4 real mode requires all of the following before credential access:

- `--execute-real-preflight`;
- the exact confirmation `EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_4`;
- valid authorization for the frozen one-call scope;
- authorization no later than the captured UTC execution time;
- pricing and data-control observations dated on that same UTC date;
- absence of all three fixed v0.4 output artifacts.

Only after those local gates pass may the command read `OPENAI_API_KEY`. Before
directory creation, marker creation, client construction or provider entry,
the v0.4 gate requires an exact string with the generic `sk-` prefix, a
conservative minimum of 120 characters, a maximum of 512 characters, and only
non-whitespace printable supported key characters. The 120-character floor is
intentionally conservative for the current long project-scoped key profile so
plausible partial clipboard values fail locally; it does not inspect a real key
or claim to validate provider authentication. Shape failures use a stable local
code and never include the
supplied value, any portion of it, its length, hash, fingerprint or
representation. The key is not accepted through arguments or JSON and is not
included in messages or artifacts. CLI option abbreviation is disabled, and
invalid syntax returns a fixed status-2 error without echoing supplied argument
names or values. This program does not control shell history or operating-system
process listings. `store=false` remains a request requirement, not a
zero-retention guarantee.

The immutable provider configuration sets reasoning effort to `none` and
`max_output_tokens` to exactly `4096`, explicitly capping the combined output
and reasoning tokens for the paid request. Both fields are part of the
canonical provider payload and therefore its execution-plan, provider-entry
and returned-record bindings. They have no caller-controlled production or CLI
override.

## One-call transaction

The fixed v0.4 attempt marker is created with exclusive semantics immediately before
the plan-bound provider wrapper, existing same-call metadata bridge and
preflight runner may invoke the provider. Its state is
`provider_call_may_have_started`. Request, schema, payload or returned-record
anchor drift fails without retry, preserves the marker and creates no successful
record. The marker also remains after success, timeout, rate limiting, provider
failure, invalid output, local validation failure or later record-write failure.
Its existence blocks automatic retries before credential access or client
construction. SDK retries remain disabled, and the provider-call counter cannot
exceed one.

Only a fully validated v0.4 compatibility record is serialized to the fixed successful
record path, using exclusive creation. After a marker exists, an ordinary
client, provider, validation or success-write failure instead installs one
exclusive immutable v0.4 failure record when filesystem state permits. The
self-hashed record binds the authorization, plan, exact installed marker-file
hash, UTC failure time, failure stage, stable local error, retry and call counts,
and the fact that no successful record was written. It may include only a
sanitized HTTP status, provider error type/code and provider request ID from the
pinned SDK interface. Before those text diagnostics reach the final exception or
record, the transaction rejects values containing `sk-`, the complete supplied
credential or a meaningful credential fragment, prefix or suffix. Ordinary
values such as `invalid_request_error`, `invalid_api_key` and a non-sensitive
request ID remain eligible. Provider bodies, raw messages, headers, prompts,
evidence, outputs and credentials are excluded, and the original SDK exception
is not attached as cause or context. Stable stages distinguish client and
provider construction, the provider call, post-response provider validation,
final record validation and successful-record writing. The public failure-record
loader verifies the canonical self-hash first and maps a mismatch to
`preflight_failure_record_hash_mismatch`. A failure record cannot coexist with a
successful record. A process crash can still leave only the permanent marker;
the transaction does not claim otherwise.

## Compatibility and semantic diagnostic

V0.4 marks technical compatibility as passed only after one completed provider
call, strict structured-output and `validate_provider_output` success, complete
same-call request/response/model/SDK/token metadata, zero retries, reconciled
request/prompt/document/schema/payload hashes and exclusive success-record
installation. The record retains returned model and version provenance,
provider IDs, pinned SDK version, token usage, latency, cost estimate,
raw-response hash and parsed-output hash without storing raw provider output.

Semantic behaviour is then recorded separately as a frozen diagnostic containing
only entity, evidence-reference and candidate-fact counts plus a canonical
warning inventory. Exact zero-candidate abstention is classified
`expected_abstention`; every other schema-valid result is
`valid_semantic_variance`. Non-empty semantic collections or different warnings
cannot independently turn a technical compatibility pass into failure.

When technical validation fails after a response has returned, the v0.4 failure
record retains the available contractually valid safe metadata. It never stores
raw output, prompts, provider bodies, headers or credentials.

## Remaining gate

The historical v0.3 and v0.4 results are closed and immutable. V0.4 must not be
rerun or assigned another outcome artifact. Its successful compatibility result
does not authorize a development provider execution.

The next controlled gate is to prepare and independently review a
development-v0.3 five-source manifest without executing it. Any later execution
plan and provider transaction remain separately reviewed and explicitly
authorized. Held-out access remains unauthorized behind a later separately
reviewed guard. These controls do not establish model superiority, extraction
quality, held-out generalization or production readiness.
