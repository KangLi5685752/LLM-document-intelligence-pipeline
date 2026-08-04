# Stage 4D OpenAI Preflight Execution Gate

## Scope

Stage 4D-3A implements and offline-tests the local execution boundary for one
possible future synthetic OpenAI preflight. It does not perform that preflight,
construct a real client during testing, create real authorization or terms
evidence, or access development or held-out documents.

The deterministic execution plan contains only fixed identifiers, canonical
hashes, a one-call limit and the two fixed repository-relative artifact paths.
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

Real mode requires all of the following before credential access:

- `--execute-real-preflight`;
- the exact confirmation `EXECUTE_SINGLE_SYNTHETIC_OPENAI_PREFLIGHT_V0_1`;
- valid authorization for the frozen one-call scope;
- authorization no later than the captured UTC execution time;
- pricing and data-control observations dated on that same UTC date;
- absence of both fixed output artifacts.

Only after those local gates pass may the command read the nonblank
`OPENAI_API_KEY` environment value and lazily construct the pinned SDK client.
The key is not accepted through arguments or JSON and is not included in
messages or artifacts. CLI option abbreviation is disabled, and invalid syntax
returns a fixed status-2 error without echoing supplied argument names or
values. This program does not control shell history or operating-system process
listings. `store=false` remains a request requirement, not a zero-retention
guarantee.

## One-call transaction

The fixed attempt marker is created with exclusive semantics immediately before
the plan-bound provider wrapper, existing same-call metadata bridge and
preflight runner may invoke the provider. Its state is
`provider_call_may_have_started`. Request, schema, payload or returned-record
anchor drift fails without retry, preserves the marker and creates no successful
record. The marker also remains after success, timeout, rate limiting, provider
failure, invalid output, local validation failure or later record-write failure.
Its existence blocks automatic retries before credential access or client
construction.

Only a fully validated `OpenAIPreflightRecord` is serialized, using the existing
canonical serializer, to the fixed successful-record path. That write is also
exclusive. A provider or validation failure creates no successful record, and
a record-write failure preserves the marker without retrying the provider. Raw
SDK responses and transient public metadata values are never serialized by this
transaction boundary.

## Remaining gate

No real API request or preflight occurred during implementation or testing, and
no real authorization, pricing observation or data-control observation was
created. Current pricing, project-account access, returned live model identity,
live version metadata and live strict-schema compatibility remain unverified.
Stage 4D-3B requires separate explicit project-owner authorization and same-day
reviewed observations before the one-call real mode may be used. A successful
preflight would not authorize five-source development execution or any held-out
access. These local controls do not claim resistance to arbitrary mutation by a
privileged local actor and do not establish production readiness.
