# Stage 4D OpenAI Synthetic Preflight v0.3 Completion Report

## 1. Purpose and scope

This report records the completed Stage 4D synthetic OpenAI preflight v0.3 and
the evidence accepted for finalization. The result establishes live Responses
API and strict-schema compatibility for one fixed synthetic request. It is not
development-corpus extraction or extraction-quality evidence.

## 2. Authorization and execution boundary

The transaction used preflight ID
`openai-gpt-5.4-mini-synthetic-preflight-v0.3` and authorization scope
`single-synthetic-openai-preflight-v0.3`. The separately approved boundary
permitted at most one provider call for the fixed synthetic request, with no
development or held-out document access. The transaction made one provider call
and zero retries.

## 3. Implementation provenance

The additive v0.3 compatibility contract was implemented in commit
`a42050c97c3ec69615cd86c69991d627a7ed6ce7` and merged through PR #37 at
`3a8048f2c69de7bdce776b183611aac438efc3f3`. Its deterministic execution-plan
SHA-256 is
`21DEC6F5DE7E79EAC2F80F93ABA41CB96BA815F5000AED9810831F671657D5C5`.

## 4. Artifact inventory

The frozen v0.3 inventory contains exactly these outcome artifacts:

- `reports/llm_extraction/openai_preflight/openai-gpt-5.4-mini-synthetic-preflight-v0.3.attempt.json`
- `reports/llm_extraction/openai_preflight/openai-gpt-5.4-mini-synthetic-preflight-v0.3.record.json`

The v0.3 failure record does not exist.

## 5. Hash and canonical validation

| Artifact | Outer SHA-256 | Canonical self-hash |
| --- | --- | --- |
| v0.3 attempt | `94CD8A7D7F21B9A102467D210B99D5856483794579DA9AB08B41B49A6BA8B119` | `7FDEE6CFEFC6A9BAEC59BD702D7B0FBA4265DD049A11F43E5F5F5A4791036848` |
| v0.3 successful record | `C2C94A7225343896B0B263AE29E0C80054299A1F30F6CDA38E68F6C4F398A4C2` | `1849C329F45D5BD0FA3472DB21FFBC60903C7449BC38BE05BFF6C3ACA219F974` |

Independent validation loaded both artifacts through the production v0.3
models, reproduced their canonical bytes and self-hashes, rebuilt the execution
plan and reconciled the request, prompt, synthetic-document, strict-schema and
provider-payload anchors. The marker-plus-success-without-failure terminal state
also reconciled.

## 6. Live compatibility result

Both `compatibility_status` and `preflight_status` are `passed`. The provider
returned once, strict structured output and local provider-output validation
passed, required safe metadata was complete, all deterministic hashes
reconciled and the canonical successful record was installed.

## 7. Semantic diagnostic

The separately frozen semantic diagnostic is
`valid_semantic_variance`. It records:

- entity count: 0;
- evidence-reference count: 1;
- candidate-fact count: 0;
- warning: `No extractable candidate facts were supported by the supplied evidence blocks.`

Semantic variance did not change the successful compatibility result. Raw
provider output is not stored, and these counts do not establish extraction
quality.

## 8. Model and SDK provenance

The returned model identifier is `gpt-5.4-mini-2026-03-17`. No separate
model-version or snapshot field was exposed, so
`model_version_or_snapshot_provenance` is recorded literally as `unavailable`.
The provider SDK version is `2.46.0`.

## 9. Usage, latency, and cost

- input tokens: 7,332;
- output tokens: 155;
- latency: 4,600 ms;
- estimated actual cost: USD 0.0061965;
- provider calls: 1;
- retries: 0.

## 10. Sensitive-data review

The successful record contains only safe structured provenance, usage,
diagnostic counts and hashes. It does not contain API credentials or credential
fragments, raw prompts, raw provider output, provider request or response
bodies, HTTP headers, development content or held-out content. The API key was
removed from the process after execution. No credential value, representation,
hash, fingerprint, prefix or suffix is recorded here.

## 11. Historical-evidence integrity

The historical evidence remained byte-unchanged during v0.3 finalization:

- v0.1 attempt outer SHA-256:
  `5B75790CE978B2AC7C6ECC2CFC00C1B21BF398AB5C622F04F2F67EE05A8B61AC`;
- v0.2 attempt outer SHA-256:
  `2FBE59B5C413D1F9BDB0951DDC6AE9284B7316E5E574693D9CA563DE2243018A`;
- v0.2 failure outer SHA-256:
  `6AA93A9F1093CD38C5254C760A5AE162A672411BE0804FCA82F1B7D8F9F0495E`.

V0.1 and v0.2 remain closed historical incidents and are not part of this v0.3
evidence change set.

## 12. Authorization closure and no-retry rule

The one-call v0.3 authorization is consumed. The permanent attempt marker and
successful record close this transaction; v0.3 must not be retried or assigned
another outcome artifact.

## 13. Development and held-out isolation

The preflight used only the fixed synthetic request. It did not access or
transmit development or held-out document content. It did not create a
five-source request manifest, development extraction, evaluation or owner-review
result. Held-out access remains unauthorized.

## 14. Limitations and non-claims

This successful synthetic transaction does not establish strong extraction
performance, model superiority, development-source success, exhaustive
precision, held-out generalization, production readiness or AG News replacement
eligibility. The semantic diagnostic is descriptive and non-evaluative.

## 15. Next controlled gate

The next controlled step is to prepare and independently review the five-source
development manifest without executing it. Any development provider request
requires separate explicit project-owner authorization. Held-out work remains
behind a later separately reviewed guard and separate authorization.

## 16. Independent audit verdict

The independent read-only audit verified the artifact inventory, outer hashes,
canonical self-hashes, execution-plan reconciliation, exact safe result fields,
sensitive-data boundary and historical hashes. Its verdict was
`approved_for_evidence_finalization`.
