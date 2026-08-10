# Stage 4D OpenAI Synthetic Preflight v0.4 Completion Report

## 1. Purpose and scope

This report closes the successful Stage 4D synthetic OpenAI compatibility
preflight v0.4 and records the evidence accepted for freezing. The transaction
tested one harmless synthetic request against the alias-safe provider schema
and configuration introduced for development v0.3. It is compatibility
evidence, not development extraction or extraction-quality evidence.

## 2. Authorization and one-call boundary

The transaction used preflight ID
`openai-gpt-5.4-mini-synthetic-preflight-v0.4`, authorization scope
`single-synthetic-openai-preflight-v0.4` and authorization ID
`openai-gpt-5.4-mini-synthetic-preflight-v0.4-2026-08-10-001`. Kang Li
authorized at most one provider call for the fixed synthetic request. The
transaction made one provider call with zero retries. That authorization is
consumed.

The external authorization, pricing and data-control files were reviewed
execution inputs. Their SHA-256 identities were respectively
`5C566B27900FA87CC92C69FD80DF6748601395FD786F4218F968EC267532FF7F`,
`B4626DF16D9FF2616C16B4485601F32441148ED99B7E8D5585ED475FC2697EB3`
and `AA6F3FD819E21BCDB7C5E7086CDBF0F56806370AEAB4C442CF099CD45549CEF7`.
The external files are not repository evidence and were not copied here.

## 3. Implementation provenance and pre-real review

PR #51 implemented the additive v0.4 compatibility contract and was merged at
`b53636d6b1c6d72260b34332db6a1e72da66cfc2`. Its deterministic execution-plan
SHA-256 is
`F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E`.

The mandatory independent pre-real review passed before provider execution. It
confirmed the merge commit, exact execution plan, exact external input
identities, absence of all v0.4 outcome artifacts, and zero provider calls,
API-key access, prohibited historical synthetic-v0.2 content access and
held-out access during review.

## 4. Frozen artifact inventory

The terminal v0.4 inventory contains exactly:

- `reports/llm_extraction/openai_preflight/openai-gpt-5.4-mini-synthetic-preflight-v0.4.attempt.json`;
- `reports/llm_extraction/openai_preflight/openai-gpt-5.4-mini-synthetic-preflight-v0.4.record.json`.

The v0.4 failure record is absent. Both evidence files retain their original
runtime bytes and one trailing LF newline.

## 5. Hash and execution-plan reconciliation

| Artifact | Outer SHA-256 | Canonical self-hash |
| --- | --- | --- |
| v0.4 attempt | `4E3706404B51C2BBA7218F18D26869CF05A4DBE1B2DF4C3AB761A3238DD96E1B` | `3F4E1B1F8EFD90218262EC24C5F75269CD9CBA3C87C92570448EB187ACD7752A` |
| v0.4 successful record | `1B4D40049671511B04B4D792A1F245D8325BE518AAB4E15CEC60683B49B504D6` | `36952C89DA9D1B56462AFCA39BD0EE58A6E9F7B7AAEE6A70C2AF068D705ACECF` |

Production V04 models reproduce the canonical marker and record bytes. The
marker binds the execution plan, and the successful record reconciles the
request, prompt, synthetic-document, strict-schema and provider-payload
anchors:

- prompt: `556DB1C4D2CDEAE0EEA49C60407246F956DF27850EF9001F7EDA0078F59CD283`;
- canonical request: `58ADDE1DFABA56786840F0101D55BE54CBC08F7BFD55E41992AE4EC1A310789F`;
- synthetic document: `98A52939E982B1D7E9784B078C1483B85526AC0B7F62787B80A86C75127FF5FC`;
- alias-safe strict schema: `C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E`;
- provider payload: `B1B5F4EB733DE4336FA593F1A7F381487A2E7C9B71FCAE03AAE7BFF29D63DF4B`;
- parsed output: `194862DFE8AC13B2397C5C213A35DF67C3C4DAA5DB3A43B34E3F4393A8F0C4E3`;
- raw-response hash only: `9A16D76AEC76724383D452B183A5E2568F2C2048FE11CC05BD130CC1D3421F93`.

Raw provider output was not retrieved or stored in this closure.

## 6. Exact live compatibility result

The v0.4 record has `preflight_schema_version=0.4`, experiment
`llm-extraction-baseline-v0.3`, request `llm-v0.3-S001-primary-999` and input
classification `synthetic_preflight_text`. It binds OpenAI Responses,
requested alias `gpt-5.4-mini`, provider configuration
`openai-responses-text-strict-json-v0.2` and model configuration
`openai-gpt-5.4-mini-text-strict-json-v0.2`.

Both `compatibility_status` and `preflight_status` are `passed`.
`strict_schema_compatible=true` and `local_output_validation_status=valid`.
The request used `store=false`, no streaming, no background execution and no
tools.

## 7. Semantic diagnostic

The diagnostic is `valid_semantic_variance` with zero entities, one evidence
reference, zero candidate facts and the warning:

`No extractable facts present in the supplied evidence; abstained from emitting candidate facts.`

This semantic variance does not negate technical compatibility and does not
establish extraction quality.

## 8. Model, SDK, usage, latency and cost

The returned model identifier is `gpt-5.4-mini-2026-03-17`. No separate
model-version or snapshot field was exposed, so provenance is recorded
literally as `unavailable`. The provider SDK version is `2.46.0`.

- provider calls: 1;
- retries: 0;
- input tokens: 7,594;
- output tokens: 177;
- latency: 4,634 ms;
- estimated actual cost: USD 0.006492.

## 9. Safe-data and sensitive-data review

The successful record contains safe structured provenance, hashes, usage and
diagnostic counts. It contains no API credential or credential fragment, raw
prompt, raw provider output, provider request or response body, HTTP header,
development content or held-out content. The record stores only the
raw-response hash, never the response body.

## 10. Closure and non-retry rule

The one-call authorization is permanently consumed. The attempt marker and
successful record close v0.4 as an immutable historical transaction. V0.4 must
not be rerun, retried, regenerated or assigned another outcome artifact.

## 11. Development and held-out isolation

The transaction used only the fixed synthetic request. It did not access or
transmit development or held-out document content. No development-v0.3
five-source manifest, development extraction, evaluation or owner-review result
exists from this transaction. S005 and S007 remained untouched and blocked.

## 12. Limitations and non-claims

This evidence does not establish development extraction success, improved
precision, recall or F1, model superiority, held-out generalization,
production readiness or AG News replacement eligibility.

## 13. Next controlled gate

The next controlled step is to prepare and independently review a
development-v0.3 five-source manifest without executing it. Any later provider
execution requires its own reviewed plan, transaction boundary and explicit
project-owner authorization. Held-out work remains separately blocked.
