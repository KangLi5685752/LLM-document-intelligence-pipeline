# Stage 4D OpenAI Development Manifest v0.3

## Purpose and scope

This document records the frozen, offline preparation manifest for a possible
bounded five-source OpenAI development execution using
`llm-extraction-baseline-v0.3`. It is hash-only preparation evidence that has
now completed a separate independent read-only review. It is not an execution
plan, authorization, provider result, evaluation result or model-quality claim.

The manifest was prepared from repository base
`ba90ecaff60cc4be89c13d2e2d42893ec13b91a9`. No provider call, credential
access, cache creation, development execution or evaluation occurred.

## Frozen artifact

Path:

`reports/llm_extraction/openai_development_manifest/openai-gpt-5.4-mini-five-source-development-manifest-v0.3.json`

- byte length: 90,686;
- outer SHA-256: `EE634214A296D4CB18687F48FD241E4A64B8848C2AD80FC697F797FE527AEB6E`;
- canonical self-hash: `D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327`;
- encoding: canonical sorted-key compact UTF-8 JSON, no BOM, one trailing LF;
- embedded freeze-state review status: `pending_independent_review`;
- execution authorization: required and `not_provided`.

The immutable embedded `manifest_review_status=pending_independent_review`
records the state at the instant the artifact was frozen. It is intentionally
unchanged. The later external review completion is documented below and does
not rewrite historical manifest bytes.

## Independent review

The independent read-only review verdict is `approved_for_evidence_commit`.
The review ZIP contained the exact six intended repository overlays plus only
the approved development ParsedDocuments for S001, S002, S003, S004 and S006.
S005, S007, the protected historical synthetic-v0.2 artifacts and `.cache`
were absent.

All five ParsedDocument canonical hashes reconciled with their frozen routes.
Whole-block primary coverage reconciled exactly:

- S001: 26/26;
- S002: 22/22;
- S003: 16/16;
- S004: 118/118;
- S006: 61/61.

The review reconciled seven primaries plus one deterministic repeat. Focused
v0.3 manifest tests independently passed 15/15, and 32 relevant manifest
regressions passed. Deterministic regeneration from the five approved
ParsedDocuments and committed v0.4 compatibility evidence was byte-for-byte
identical to the frozen manifest, reproducing outer SHA-256
`EE634214A296D4CB18687F48FD241E4A64B8848C2AD80FC697F797FE527AEB6E`
and manifest self-hash
`D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327`.

No provider call, credential access, cache access, evaluation or held-out
access occurred during independent review.

## Approved source routes

The exact route order is `S001`, `S002`, `S003`, `S004`, `S006`. The manifest
contains route, document and canonical ParsedDocument hashes, ordered block
identities and block-text hashes only. S005 and S007 were not accessed and are
not present in the invocation inventory.

Gold labels, deterministic candidates and owner outcomes were not used as
prompt inputs or partition signals.

## V0.3 partition inventory

The source-independent policy is
`provider-payload-whole-block-greedy-v0.3`. It uses actual prompt 0.3,
`LLMExtractionRequestV03`, alias-safe provider payload bytes and the 200,000
byte ceiling. Blocks are never split or truncated.

| Request | Blocks | Provider-payload bytes |
| --- | ---: | ---: |
| `llm-v0.3-S001-primary-001` | 26 | 106,660 |
| `llm-v0.3-S002-primary-001` | 22 | 84,200 |
| `llm-v0.3-S003-primary-001` | 16 | 74,123 |
| `llm-v0.3-S004-primary-001` | 53 | 197,889 |
| `llm-v0.3-S004-primary-002` | 47 | 196,624 |
| `llm-v0.3-S004-primary-003` | 18 | 99,320 |
| `llm-v0.3-S006-primary-001` | 61 | 181,579 |

There are seven primaries: one each for S001, S002, S003 and S006, and three
for S004.

## Deterministic repeat

The repeat policy is
`largest-primary-provider-payload-request-id-tiebreak-v0.3`. Before any model
result exists, it selects the largest primary payload and uses the
lexicographically smallest primary request ID for an exact tie.

The selected primary is `llm-v0.3-S004-primary-001` at 197,889 bytes. The
repeat is `llm-v0.3-S004-repeat-001`, appears last, contains the same 53 whole
blocks and provider semantics, and has distinct canonical request and cache
identities. Total planned invocations are eight.

## Alias-safe provider boundary

- provider configuration: `openai-responses-text-strict-json-v0.2`;
- model configuration: `openai-gpt-5.4-mini-text-strict-json-v0.2`;
- requested model: `gpt-5.4-mini`;
- response schema: `candidate_extraction_result_0_1_aliases_empty_v0_3`;
- strict-schema SHA-256: `C39E96B77BC2E9BEC3DF191071BC0C8B8F1AE545228A7D6CB6DF0CCA44E8269E`;
- prompt version: `0.3`;
- provider retries: zero;
- timeout: 120 seconds;
- reasoning effort: `none`;
- maximum output: 4,096 tokens;
- `store=false`, no streaming, no background execution and no tools.

The local `CandidateEntity` and `CandidateExtractionResult` 0.1 contracts are
unchanged. Provider-facing aliases remain required with `maxItems=0`; no
post-response repair is permitted.

## Successful compatibility binding

Development v0.3 binds the closed alias-safe synthetic compatibility preflight
v0.4, not the legacy-schema synthetic preflight v0.3.

- preflight ID: `openai-gpt-5.4-mini-synthetic-preflight-v0.4`;
- execution-plan SHA-256: `F68441CF6F2EA3B52AF709DD3529E755285719E04622DE9FC02F7C6608B4FD6E`;
- attempt outer/self hashes: `4E3706404B51C2BBA7218F18D26869CF05A4DBE1B2DF4C3AB761A3238DD96E1B` / `3F4E1B1F8EFD90218262EC24C5F75269CD9CBA3C87C92570448EB187ACD7752A`;
- success outer/self hashes: `1B4D40049671511B04B4D792A1F245D8325BE518AAB4E15CEC60683B49B504D6` / `36952C89DA9D1B56462AFCA39BD0EE58A6E9F7B7AAEE6A70C2AF068D705ACECF`;
- returned model: `gpt-5.4-mini-2026-03-17`;
- separate model-version or snapshot provenance: `unavailable`;
- SDK: `2.46.0`;
- compatibility and local validation: passed and valid;
- calls/retries: one/zero.

V0.4 is consumed, immutable and must not be rerun.

## Context admission

The existing reviewed context observation records a 400,000-token context
window, maximum output of 4,096 and reasoning effort `none`. Admission uses the
conservative planning rule that one serialized provider-payload UTF-8 byte is
at most one input token. This is not a tokenizer-accuracy claim.

The largest invocation is 197,889 bytes, so its admission equation is:

`197889 + 4096 = 201985 <= 400000`

Every invocation passes the same boundary.

## Cache and execution budget

The planned cache root is
`.cache/llm_extraction/llm-extraction-baseline-v0.3/openai/`. It remains local,
Git-ignored and append-only, with no replacement or unplanned bypass. No cache
directory or response was created.

- primary calls: 7;
- repeat calls: 1;
- maximum provider calls and total attempts: 8;
- retries per invocation: 0;
- planning input-token budget: 284,573;
- conservative input-token proxy: 1,138,284;
- maximum output-token budget: 32,768;
- aggregate planning cost: USD 0.36088575;
- aggregate conservative cost ceiling: USD 1.001169;
- planned authorization cap: USD 1.25;
- broad Stage 4 ceiling: USD 25.

The pricing and data-control observations are the safe committed observations
from the v0.4 success record, with explicit review bindings. They remain
planning provenance only. A same-day pricing, data-control and account-access
review is mandatory before any future real development execution.

## Isolation, limitations and next gate

No provider call, execution authorization, execution plan, candidate output,
development result, evaluation or held-out access was created by this task.
The manifest does not establish extraction quality, improved metrics, model
superiority, held-out generalization or production readiness.

After repository integration, the next engineering gate is preparation and
independent review of a separate bounded development-v0.3 execution plan and
transaction boundary. Any real execution would still require separate explicit
project-owner authorization.
