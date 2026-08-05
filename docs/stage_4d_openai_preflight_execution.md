# Stage 4D OpenAI Preflight Execution Gate

## Scope

Stage 4D-3B implements and offline-tests a separate v0.3 local execution
boundary for one possible future synthetic OpenAI preflight. This correction
does not authorize or perform that preflight, construct a real client during
testing, create real authorization or terms evidence, or access development or
held-out documents.

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

V0.3 real mode requires all of the following before credential access:

- `--execute-real-preflight`;
- the exact confirmation `EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_3`;
- valid authorization for the frozen one-call scope;
- authorization no later than the captured UTC execution time;
- pricing and data-control observations dated on that same UTC date;
- absence of all three fixed v0.3 output artifacts.

Only after those local gates pass may the command read `OPENAI_API_KEY`. Before
directory creation, marker creation, client construction or provider entry,
the v0.3 gate requires an exact string with the generic `sk-` prefix, a
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

The fixed v0.3 attempt marker is created with exclusive semantics immediately before
the plan-bound provider wrapper, existing same-call metadata bridge and
preflight runner may invoke the provider. Its state is
`provider_call_may_have_started`. Request, schema, payload or returned-record
anchor drift fails without retry, preserves the marker and creates no successful
record. The marker also remains after success, timeout, rate limiting, provider
failure, invalid output, local validation failure or later record-write failure.
Its existence blocks automatic retries before credential access or client
construction. SDK retries remain disabled, and the provider-call counter cannot
exceed one.

Only a fully validated v0.3 compatibility record is serialized to the fixed successful
record path, using exclusive creation. After a marker exists, an ordinary
client, provider, validation or success-write failure instead installs one
exclusive immutable v0.3 failure record when filesystem state permits. The
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

V0.3 marks technical compatibility as passed only after one completed provider
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

When technical validation fails after a response has returned, the v0.3 failure
record retains the available contractually valid safe metadata. It never stores
raw output, prompts, provider bodies, headers or credentials.

## Remaining gate

V0.3 paid execution remains unauthorized. No real v0.3 API request or preflight
occurred during this corrective implementation or its offline tests, and no
v0.3 authorization, pricing observation or data-control observation was
created. Current pricing, project-account access, returned live model identity,
live version metadata and live strict-schema compatibility remain unverified.
A future v0.3 attempt requires separate explicit project-owner authorization
and same-day reviewed observations. A successful v0.3 preflight would not
authorize the five-source development manifest or execution, which remain
separately blocked, and would not authorize any held-out access. These local
controls do not claim resistance to arbitrary mutation by a privileged local
actor and do not establish production readiness.
