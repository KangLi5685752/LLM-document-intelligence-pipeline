# Stage 4 Development-Only LLM-Assisted Candidate Extraction Plan

## Status and authority

- **Stage:** Stage 4A - planning and experiment contract.
- **Working experiment identity:** `llm-extraction-baseline-v0.1`.
- **Status:** Planned only. No LLM extraction implementation, provider adapter, real request, result or evaluation exists under this experiment identity.
- **Comparison parent:** frozen `deterministic-baseline-v0.4` development evidence.
- **Access boundary:** development only. Stage 4A-E do not authorize held-out access or execution.
- **Provider status:** no provider or model is selected by this plan. A separate reviewed provider decision is required before a real-provider adapter is implemented or invoked.

This plan defines the contract that must be reviewed before implementation. It does not authorize RAG, retrieval, reconciliation, cloud deployment, a user interface or held-out evaluation.

## Objective

Build a controlled LLM-assisted candidate extraction comparator that consumes validated Common Document Object records and emits evidence-linked candidates through the existing extraction contract. The comparator must make LLM engineering choices auditable, bounded and reproducible, and must be evaluated fairly against `deterministic-baseline-v0.4` on the same development sources and strict matching protocol.

The objective is a credible engineering comparison, not an API demonstration. Generated text is never authoritative merely because a model produced it.

## Fixed comparison boundary

The following inputs and contracts remain fixed unless a later separately reviewed schema decision explicitly authorizes a change:

| Boundary | Fixed value |
| --- | --- |
| Input model | Validated Common Document Object / `ParsedDocument` |
| Candidate output | `CandidateExtractionResult` schema `0.1` |
| Predicate vocabulary | `0.1` |
| Evaluation asset | `public-gold-v0.1` |
| Matching protocol | `0.1` |
| Matcher | Existing unchanged strict matcher |
| Development sources | S001, S002, S003, S004 and S006 |
| Deterministic comparator | Immutable `deterministic-baseline-v0.4` |

The deterministic comparator remains fixed at 178 candidates, 25 commitment candidates, TP 5, FP 173, FN 20, precision 0.028089887640449437, recall 0.2, F1 0.04926108374384237, zero duplicates and zero S002 strict matches. These are comparison observations, not target values to encode in prompts or extraction logic.

Any later deterministic semantic change requires `deterministic-baseline-v0.5`. Any post-observation LLM prompt, parsing, candidate or evaluation semantic change requires a new LLM experiment version rather than an in-place rewrite of `llm-extraction-baseline-v0.1`.

## Scope

Stage 4 may plan and later implement:

- one provider-neutral request and response interface;
- one deterministic mock provider for all unit and transaction tests;
- at most one separately approved real LLM provider;
- versioned prompts and structured candidate output;
- development-only request orchestration, local caching and provenance;
- strict development comparison with the frozen deterministic baseline;
- structural and safety evaluation, error analysis and owner review;
- an optional development freeze after every mandatory process gate passes.

Stage 4 does not include:

- retrieval, RAG or vector search;
- cross-document reconciliation or recommendation;
- cloud deployment, managed storage or a user interface;
- held-out source access, extraction or evaluation;
- changes to deterministic v0.4 evidence or semantics;
- claims of production readiness, enterprise scalability, exhaustive precision, held-out generalization or model superiority.

## Development and held-out boundary

The runner must use an explicit allowlist containing only S001, S002, S003, S004 and S006. Development routing must fail closed before any non-allowlisted source path, `ParsedDocument` or semantic annotation is opened.

No Stage 4A-E workflow may open or execute a held-out source, held-out `ParsedDocument` or held-out semantic annotation. In particular, S005 and S007 are excluded from request construction, cache lookup, extraction and evaluation. Gold labels must be loaded only through the existing guarded development-only path and only after candidate outputs are fixed for evaluation.

A development freeze does not authorize held-out access. Held-out evaluation requires a later separately reviewed guard, and any held-out provider invocation requires explicit project-owner authorization. No held-out result may be predicted or claimed.

## Provider decision gate

### Gate G4-P1: provider and model approval

Before any real-provider adapter is implemented or any network request is made, a separate reviewed decision must record:

- the single provider selected for `llm-extraction-baseline-v0.1`;
- the exact model identifier and available model-version identifier;
- endpoint and structured-output capabilities;
- documented context and output limits;
- data retention, training-use and logging terms suitable for the approved public inputs;
- credential and environment-variable handling;
- timeout, retry and rate-limit behavior;
- token pricing and the approved cost ceiling;
- model-parameter defaults and all parameters that affect output;
- owner approval for the bounded development execution.

If a stable model identity, acceptable data terms or complete cost provenance cannot be established, real-provider implementation and execution remain blocked. This planning PR deliberately does not select a provider or model.

### Narrow provider interface

The future provider-neutral interface must accept one canonical request envelope and return one response envelope. Its responsibility is limited to transport and provider metadata. It must not contain source-specific extraction rules, gold knowledge, matching logic or evaluation decisions.

The request envelope must carry the experiment ID, invocation role, provider/model configuration identity, prompt identity, input identity and approved source blocks. The response envelope must preserve the raw response bytes or exact canonical raw-response representation, provider identifiers, usage, latency, retry and terminal status metadata.

Only one real adapter may be active for v0.1. Unit tests must use the deterministic mock provider and must make no network calls. API keys must be supplied only through environment configuration. Secrets, authorization headers, raw credentials and private data must never be committed, cached in provenance records or written to logs.

## Request budget and stop conditions

Stage 4A, 4B and 4C permit zero real provider calls. Stage 4D may proceed only after G4-P1 and a reviewed dry-run request manifest.

Let `N` be the number of canonical primary request envelopes in that frozen manifest:

- `N` must cover only the five approved development sources and must not exceed 100;
- an optional repeat sample `R` must be selected deterministically before observation and must not exceed 10 envelopes;
- at most one retry is permitted for each primary or predeclared repeat request;
- total real call attempts must not exceed `2 * (N + R)` and therefore cannot exceed 220;
- aggregate estimated provider cost must not exceed USD 25;
- each attempt has a maximum 120-second response timeout;
- no unplanned refresh, exploratory call or automatic cache bypass is permitted.

Repeat calls must use a distinct predeclared invocation identity and must never overwrite the primary response. Ordinary repeated development runs must use the cache rather than silently issue new calls.

Execution must stop immediately when any of these conditions occurs:

- the request-count, cost or configured token budget would be exceeded;
- a held-out or non-allowlisted source is encountered;
- the actual provider, model identifier, model version or parameters differ from the frozen configuration;
- a prompt, input, request or cache hash mismatch is detected;
- a secret or prohibited field appears in a request, cache record or log;
- three consecutive transport, authentication, timeout or rate-limit failures occur;
- cache identity is ambiguous or an existing response would be replaced;
- required provenance cannot be recorded;
- the project owner withdraws or has not supplied execution authorization.

Invalid JSON, schema-invalid output and invalid evidence references fail closed for the affected response. They are recorded as observed failures and cannot create accepted candidates. They do not authorize an ad hoc prompt change or an unplanned replacement call.

## Prompt contract

### Versioning and canonical identity

System and extraction prompts must be stored as versioned repository assets. Prompt composition must be deterministic. The exact system prompt, extraction prompt, ordered block envelope, model parameters and output-contract identifier must have a canonical serialization and uppercase SHA-256 identity before any real request.

A prompt change after observation creates a new experiment version. Whitespace normalization, ordering and template-variable serialization must be explicit so that the same prompt inputs produce the same prompt hash.

### Permitted prompt content

Source text may come only from validated blocks in an approved development `ParsedDocument`. Every supplied block must include its source ID, evidence/block ID, text and allowed location metadata. Source IDs and evidence IDs must be explicit rather than inferred by the model.

Prompts must not include:

- development or held-out gold labels;
- expected answers, matched annotation IDs or target metric values;
- owner outcomes or rationales;
- source-specific exceptions, aliases, titles, filenames or page rules intended to reproduce gold;
- deterministic baseline candidates as answers to imitate;
- held-out source content or metadata.

Prompts must instruct the model to use only supplied evidence, abstain when evidence is absent or ambiguous, preserve uncertainty, and route uncertain candidates to review. They must state that unsupported inference and invented evidence identifiers are invalid.

## Output and validation contract

The model must return structured output that can be validated against the existing candidate models. No provider-specific object may bypass `CandidateExtractionResult` schema `0.1`.

Validation must occur in this order:

1. Confirm a complete terminal provider response and raw-response hash.
2. Parse exact JSON without permissive repair or prose extraction.
3. Validate the result and every fact against the existing candidate models.
4. Validate predicates against predicate vocabulary `0.1`.
5. Validate predicate-scoped qualifiers through existing qualifier rules.
6. Verify that every source and evidence reference belongs to the supplied request envelope.
7. Reject candidates without at least one valid evidence reference.
8. Apply explicit abstention and review routing without converting uncertainty into accepted fact.
9. Canonically serialize and hash the validated parsed output.

Invalid JSON, schema-invalid facts, invalid predicates, invalid qualifiers, unsupported evidence references and candidates without valid evidence must produce explicit warning or failure codes. Unsupported candidates must be rejected or routed according to the existing schema; they must not be silently repaired into facts.

Evidence-reference validity establishes that a reference points to a supplied block. It does not by itself establish semantic entailment. LLM output remains candidate evidence for later evaluation and review, not authoritative knowledge.

## Cache and provenance contract

### Local cache

The real-response cache must be local and Git-ignored during development. Its key must bind the experiment ID, provider and model identity, all model parameters, prompt version and hash, input document hash, canonical request hash and invocation role.

Cache entries are append-only for a request identity. A cache hit must return the original response and provenance, record that no provider call occurred, and increment cache-hit observability. A conflicting entry, missing provenance or hash mismatch must fail closed. Refreshing a response requires a new predeclared invocation identity or a new experiment version; it must never silently replace an observed response.

Cached and fresh responses must be distinguishable in every downstream artifact. Re-parsing a cached raw response must retain the original provider-call timestamp and usage while recording the new local parse event separately.

### Required request provenance

Every real request record must contain:

- experiment ID;
- provider;
- model identifier and model-version provenance;
- complete model parameters;
- prompt version and prompt hash;
- input document hash;
- canonical request hash;
- raw-response hash;
- parsed-output hash when parsing succeeds;
- provider-call timestamp;
- latency;
- input and output token counts;
- estimated cost and pricing reference identity;
- retry count;
- cache status and original invocation identity;
- validation result;
- ordered warning and failure codes.

Provenance serialization must exclude credentials, authorization headers, machine-specific absolute paths and private environment values. Missing mandatory provenance makes the request ineligible for evaluation or freeze.

## Evaluation contract

Evaluation must use the unchanged strict matcher and the same development gold selection used for the deterministic comparator. Candidate output must be fixed before development labels are loaded for scoring.

### Existing strict comparison metrics

The evaluation report must record:

- TP, FP and FN;
- precision, recall and F1;
- duplicate candidate count;
- per-source candidate counts;
- per-predicate candidate counts;
- exact matched annotation IDs.

The deterministic v0.4 observation must be reproduced in the comparison report from immutable committed evidence, not rerun or rewritten.

### LLM-specific structural and safety metrics

The evaluation report must also record:

- provider-call success rate;
- valid JSON rate;
- schema-valid output rate;
- evidence-reference validity rate;
- unsupported evidence-reference count;
- candidate-without-valid-evidence count;
- invalid predicate count;
- invalid qualifier count;
- review-required count;
- abstention count;
- response-cache hit count;
- input and output token usage;
- estimated cost;
- latency distribution;
- repeated-run and repeated-parse stability.

Metric denominators, treatment of failed requests and aggregation order must be frozen before Stage 4D. Repeated-parse stability means that the same raw response parsed twice produces identical canonical parsed-output bytes. Repeated-run stability compares only the predeclared repeat sample and must report exact agreement and differences without treating nondeterminism as a hidden retry opportunity.

Sparse development gold cannot establish exhaustive semantic precision. Strict unmatched candidates are structural false positives under the fixed matcher but are not automatically confirmed hallucinations without separate evidence review. No held-out performance, generalization or superiority may be inferred from development results.

## Process gates and quality observations

### Mandatory process gates

The exact ordered gate inventory must be frozen before Stage 4D. At minimum it must require:

1. Stage 4 plan and experiment identity reviewed.
2. Provider and model decision G4-P1 accepted.
3. Five-source development allowlist fixed and held-out denial tested.
4. Common Document Object and candidate schema boundaries unchanged.
5. Predicate vocabulary, public gold, matching protocol and strict matcher unchanged.
6. Versioned prompts and canonical prompt hashes fixed.
7. Provider/model parameters and request manifest fixed.
8. Request-count, timeout, retry, token and cost budgets fixed.
9. Deterministic mock and no-network unit tests passed.
10. JSON, schema, predicate, qualifier and evidence validation fail closed.
11. Canonical request, raw-response and parsed-output hashing verified.
12. Cache identity, append-only behavior and cache-hit provenance verified.
13. Credential and path redaction checks passed.
14. Every real call attempt has complete provenance and a terminal status.
15. No held-out source, `ParsedDocument` or semantic annotation was opened or executed.
16. Repeated parsing of each successful raw response is byte-stable.
17. Strict and LLM-specific metrics reconcile with the fixed artifacts.
18. Owner judgments, if collected, remain separate from automated diagnostics.
19. Error analysis preserves sparse-gold and non-authoritative-output limitations.
20. Optional freeze inventory, hashes and transaction behavior pass independent review.

A mandatory process-gate failure blocks optional freeze. It does not permit repair by changing prompts or semantics under the same observed experiment identity.

### Non-binding quality observations

All strict comparison metrics and LLM-specific structural, safety, latency, cost and stability metrics are observations. No minimum F1, precision, recall, provider-success, JSON-validity or schema-validity threshold may be invented after results are visible. Stage 4A does not predict that the LLM comparator will outperform deterministic v0.4.

## Planned artifact boundary

Stage 4B-E may define versioned prompts, provider-neutral contracts, mock fixtures, a development request manifest, local cache records, candidate outputs, provenance, evaluation, error-analysis and optional freeze artifacts. Exact paths and schemas must be reviewed in the PR that introduces them.

Real request and response bodies remain local and Git-ignored unless a later evidence decision confirms that their content, licensing, secret redaction and provenance are suitable for a committed freeze. Hash-only evidence must not be described as independently reproducible if the underlying approved response is unavailable.

## Small-PR decomposition

### Stage 4A - planning and experiment contract

- **Goal:** Freeze the development-only objective, comparison contracts, provider decision gate, budget, provenance, evaluation and access boundaries.
- **Authorized changes:** Planning documentation, project status and planning-time decisions only.
- **Prohibited changes:** Production code, tests, prompts, provider selection, API calls, extraction, evaluation, evidence generation and held-out access.
- **Tests:** Documentation review plus `git diff --check`, changed-path and staging checks.
- **Artifacts:** This plan, DEC-096 through DEC-099 and Stage 4A status.
- **Completion criteria:** The plan is independently reviewable, no provider/model is selected, no call occurred, and implementation remains gated.

### Stage 4B - provider interface, mock mode and prompt/output contracts

- **Goal:** Implement the provider-neutral boundary, deterministic mock, versioned prompts and fail-closed structured-output validation.
- **Authorized changes:** New isolated LLM extraction contracts, mock fixtures, prompt assets and neutral unit tests defined by the reviewed Stage 4A contract.
- **Prohibited changes:** Real provider calls, development execution, gold-informed prompts, source-specific exceptions, matcher changes, held-out access and evidence claims.
- **Tests:** Deterministic mock behavior, canonical prompt hashing, invalid JSON/schema/predicate/qualifier rejection, evidence-reference validation, abstention/review routing, secret redaction and enforced no-network unit tests.
- **Artifacts:** Provider-neutral interface, mock provider, prompt versions and hashes, output validator and neutral fixtures.
- **Completion criteria:** All contract tests pass without a network connection and no real-provider adapter or response exists unless G4-P1 has first been separately accepted.

### Stage 4C - development runner, cache and provenance

- **Goal:** Build a development-only orchestrator that creates canonical request envelopes, uses the mock provider, caches append-only responses and records complete provenance.
- **Authorized changes:** Development runner, request manifest, cache/provenance models, dry-run CLI and fictional transaction tests.
- **Prohibited changes:** Real provider execution, evaluation against visible gold, response replacement, unbounded retries, absolute-path leakage, held-out access and final freeze.
- **Tests:** Development allowlist, held-out denial before file open, request hashing, cache hit/miss/conflict behavior, retry/timeout simulation, budget stops, repeated parsing, provenance completeness, redaction and rollback with fictional data.
- **Artifacts:** Canonical dry-run request manifest, local cache contract, provenance schema and mock-run report.
- **Completion criteria:** A complete five-source dry run succeeds in mock mode, all failure paths are bounded, and no network or gold access occurs.

### Stage 4D - one-provider development execution

- **Goal:** After G4-P1, execute the frozen development request manifest once with at most one real provider and collect immutable local response/provenance evidence.
- **Authorized changes:** One approved provider adapter, frozen provider/model configuration, bounded development execution and local Git-ignored cache/provenance records.
- **Prohibited changes:** A second provider, prompt tuning after observation, matcher or gold changes, unplanned refreshes, budget overrides, held-out access, performance claims and freeze before review.
- **Tests:** Adapter tests with the deterministic mock or sanctioned recorded transport fixtures, dry-run identity checks, stop-condition tests and pre-execution audit. Unit tests still make no network calls.
- **Artifacts:** Reviewed request manifest, primary and predeclared repeat response records, validated candidate outputs, hashes, usage, cost and execution summary.
- **Completion criteria:** Every planned request has terminal provenance, budgets and stop conditions were respected, invalid outputs failed closed, cache records were not overwritten, and no held-out resource was accessed.

### Stage 4E - evaluation, error analysis, owner review and optional freeze

- **Goal:** Evaluate fixed development candidates with the unchanged matcher, analyze structural/safety behavior, obtain bounded owner review where required, and optionally freeze a process-valid observation.
- **Authorized changes:** Development evaluator/report, error analysis, owner-review packet and records, fictional freeze-transaction tests, and optional reviewed development evidence.
- **Prohibited changes:** Prompt or extraction tuning under v0.1 after observation, exhaustive-precision claims, owner/machine provenance conflation, held-out execution, production-readiness claims and automatic RAG work.
- **Tests:** Metric reconciliation, deterministic report serialization, provenance and cache reconciliation, owner/automated separation, claim-boundary checks, fictional transaction rollback and read-only validation.
- **Artifacts:** Development comparison report, LLM structural/safety report, error analysis, owner-review evidence, finalization record and optional freeze manifest.
- **Completion criteria:** Every mandatory process gate passes, all quality observations are reported without retrospective thresholds, independent review is complete, and any freeze preserves exact artifacts and explicitly denies held-out authorization.

## Portfolio boundary

Stage 4 is intended to demonstrate disciplined LLM integration: explicit prompts, structured validation, evidence provenance, cost controls, caching, reproducibility, failure handling and fair comparison with a deterministic baseline.

Completion of Stage 4 would not establish production readiness, enterprise scalability, exhaustive semantic precision, held-out generalization, model superiority or a complete RAG system. Retrieval, reconciliation, cloud deployment and user-interface work remain later separately reviewed decisions.

