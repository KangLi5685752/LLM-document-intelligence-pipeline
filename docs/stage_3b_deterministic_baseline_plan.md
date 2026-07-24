# Stage 3B Deterministic Baseline Plan v0.1

## Status

Stage 3B.1 plan version `deterministic-baseline-v0.1` becomes the implementation contract when merged. No extractor or metric result exists yet. Implementation must begin in a later branch and pull request. This plan must not be edited retrospectively after observing held-out results; a changed experiment requires a declared new version and cycle.

## Purpose

The deterministic baseline provides a transparent, reproducible comparison point for later structured LLM extraction. It is deliberately bounded and inspectable, and is not intended to be the highest-performing system.

## Fixed dependencies

- Corpus: `stage1-corpus-v1.0`
- Public gold: `public-gold-v0.1`
- Facts SHA-256: `CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690`
- Cases SHA-256: `328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237`
- Parser commit: `71148262f094d54ec7d95e45958bd1aaefc64793`
- Candidate extraction schema: `0.1`
- Predicate vocabulary: `0.1`
- Matching protocol: `0.1`
- Planning base commit: `65eb31fa07865e9fb6e18955503a06a3a57df186`

## Input boundary

The extractor receives only frozen `ParsedDocument` JSON and may inspect only its metadata and each block's text, type, order, location type and location value. It must not:

- reopen raw PDFs;
- inspect annotation notes;
- inspect gold evidence excerpts during extraction;
- use source IDs or filenames as rule conditions;
- call a network or LLM service.

## Scored dataset

The primary scored development set is the five public-PDF sources S001, S002, S003, S004 and S006. It contains 25 facts and three development challenge cases.

The held-out public set is S005 and S007. It contains 10 facts and three held-out challenge cases. Its semantic values remain outside this plan.

## Synthetic corpus role

S010 and S012-S014 may later be used for non-scored development format and schema smoke tests. S011 and S015-S017 remain held out. Public-gold fact F1 must not mix synthetic records, and `synthetic_ground_truth.jsonl` must not be loaded by the public-gold matcher. Evaluation of synthetic current, superseded and conflict states belongs to a later reconciliation experiment.

## Output contract

Implementation must produce one `CandidateExtractionResult` per source. Each result must:

- assign no final `fact_state`;
- use `extraction_method=deterministic`;
- order sources, blocks, rules and spans deterministically;
- derive candidate and evidence IDs deterministically;
- contain no runtime timestamps in canonical output;
- use deterministic JSON serialization;
- reference only existing evidence blocks from the same source.

## Supported predicates

Baseline v0.1 scoring is limited to:

- `recommendation`;
- `commitment`;
- `requirement`;
- `decision`;
- `risk`;
- `metric`;
- `budget`;
- `action_status`.

The full registry still contains 20 predicates. Predicates not listed above are outside baseline v0.1 scope and must not be silently invented.

## Rule families

The planning contract defines generic rule families rather than exact regular expressions. Rules must not contain source-, filename-, page- or expected-value-specific exceptions.

| Rule family | Intended predicate | Generic trigger type | Subject-attribution boundary | Value boundary | Evidence boundary | Known failure modes | Why source-independent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Numbered recommendation detection | `recommendation` | A bounded recommendation label, numbering cue or explicit recommendation construction | Explicit subject in the statement, otherwise an eligible heading or immediately preceding same-block context | The complete recommended action in the bounded statement | Exact supporting span from that block | Lists mistaken for recommendations; detached numbering; multiple actions in one item | Uses document structure and language patterns, not named documents or expected recommendations |
| Explicit commitment language | `commitment` | Explicit commitment or future-action language attributable to an actor | Explicit actor in the statement, otherwise eligible same-block context | The action the actor commits to undertake, without unrelated following clauses | Exact clause or sentence that contains actor, trigger and action | Predictions or aspirations mistaken for commitments; negation; multi-actor ambiguity | Applies generic modal and commitment constructions across sources |
| Mandatory requirement language | `requirement` | Mandatory terms such as obligations, requirements or prohibitions | The entity subject to or issuing the bounded requirement, when explicit or safely attributable in the same block | The mandatory condition or action, preserving negation and modality | Exact bounded requirement statement | Guidance strengthened into a mandate; quoted obligations; missing scope | Uses generic mandatory-language cues and bounded syntax |
| Explicit decision language | `decision` | Explicit decision, approval, agreement or resolution wording | Named decision-maker or bounded subject in the statement or eligible same-block context | The determination explicitly made, excluding proposals and commentary | Exact statement that supports the decision | Proposals mistaken for decisions; conditional approvals; multiple determinations | Depends on decision language rather than document identity |
| Risk or impact statement detection | `risk` | Explicit risk, threat, adverse impact or consequence wording | The named risk, affected subject or safely bounded same-block context | The source-stated risk or impact, retaining conditions and modal strength | Exact statement connecting the subject to the risk or impact | Benefits misclassified as risks; causal overreach; qualifier loss | Uses generic risk and impact constructions across the corpus |
| Quantitative metric detection | `metric` | A named measure paired with a number or percentage | The explicitly measured subject or eligible same-block heading/context | The exact typed value plus source-supported metric qualifiers | Exact sentence or intact table relationship supporting measure and value | Denominator loss; chart or table flattening; nearby numbers paired incorrectly | Relies on typed numeric and measure cues, not known values |
| Monetary budget detection | `budget` | Currency and amount associated with an explicit budget concept | The initiative, programme, policy or organisation explicitly linked to the amount | Exact non-negative amount and stated ISO currency, preserving budget status when supported | Exact span connecting subject, budget meaning and amount | Ceilings, proposals or expenditure mistaken for approved budgets; unit scaling | Uses generic monetary and budget cues rather than fixed amounts |
| Action progress status detection | `action_status` | Explicit progress or completion status attached to an identified action | The named action or eligible same-block action context | The exact stated progress status without inferring completion | Exact bounded action-status statement | General project status confused with action status; tense and negation errors | Applies generic progress language and action references |
| Heading and same-block subject attribution | All eight supported predicates | A structural heading or immediately preceding bounded context in the same block | Never crosses a block or page; ambiguous competing subjects require review or abstention | The value remains within the triggered bounded statement | The evidence excerpt must include enough same-block context to support the attribution | Over-broad headings; flattened layout; competing subjects | Uses `ParsedDocument` structure consistently and contains no source-specific mapping |
| Exact evidence-span preservation | All eight supported predicates | A candidate-producing trigger with a recoverable exact source span | Follows the subject boundary of the producing rule | Preserves the complete bounded value without reconstruction | One exact excerpt of at most 240 characters from the same block and source | Whitespace artifacts; truncated qualifiers; reconstructed tables; invented ellipses | Applies the same model constraint and exact-span rule to every source |

## Subject attribution

1. Prefer an explicit grammatical or named subject in the same bounded statement.
2. Otherwise allow a heading or immediately preceding bounded context in the same `ParsedDocument` block.
3. Do not cross pages or blocks for subject attribution in v0.1.
4. Multiple plausible subjects require review or abstention.
5. Never use the known gold subject to fill a missing subject.

## Evidence rules

- Evidence must be exact text from one `ParsedDocument` block.
- Excerpts must remain within the `CandidateEvidenceReference` maximum length.
- Source and location must match the candidate and an existing block.
- `supported` is permitted only when the excerpt directly supports the complete bounded candidate.
- Use `ambiguous` when a relationship cannot be recovered safely.
- Do not invent ellipses or reconstruct table relationships.

## Confidence contract

Confidence is a fixed rule-strength heuristic, not a calibrated probability:

- `0.90`: explicit same-block subject, trigger, value and supported evidence;
- `0.70`: bounded subject attribution from a heading or immediately preceding same-block context;
- `0.50`: multiple plausible relationships or flattened-layout ambiguity, requiring review.

These values must not be tuned using held-out results.

## Review and abstention behaviour

- **Ambiguous:** route to review or abstain with an explicit warning.
- **Unsupported:** do not emit the unsupported generalized fact.
- **Missing expected value:** preserve the missing value and do not fabricate it.

A lower candidate count is not automatically a failure; unsupported extraction is a substantive error.

## Metrics

Every metric report must retain its exact numerator and denominator:

- fact precision = strictly matched candidate facts / all emitted candidate facts = TP / (TP + FP);
- fact recall = strictly matched gold facts / all in-scope gold facts = TP / (TP + FN);
- fact F1 = `2 * precision * recall / (precision + recall)`, calculated from unrounded counts and reported as null when its denominator is zero;
- normalized-value exact match = aligned candidate/gold pairs with exactly matching normalized typed values / all deterministic pairs aligned without value;
- schema-valid result rate = schema-valid source-level results / all attempted development source outputs;
- evidence-source accuracy = strictly matched facts with matching evidence source / all strictly matched facts;
- evidence-location accuracy = strictly matched facts with at least one matching block ID, location type and location value / all strictly matched facts;
- development challenge-case pass rate = development challenge cases that satisfy their declared behaviour / all three development challenge cases.

Reports must also include total candidates, candidates per source, unmatched predictions, unmatched gold facts, duplicate candidate count, review-required candidate count, unsupported extraction count, and per-predicate TP, FP and FN.

No minimum development F1 is required for baseline acceptance. The baseline is accepted when its execution and reporting contract is reproducible and complete, even if performance is modest.

## Development process

1. Implement a fail-closed development-only loader.
2. Add source-independent unit fixtures.
3. Implement deterministic rules.
4. Run development-only extraction.
5. Produce development metrics and failure analysis.
6. Freeze rules, code and experiment identity.
7. Only then permit one held-out run.

## Baseline freeze gate

Before held-out access, a future freeze manifest must record:

- experiment ID;
- code commit;
- rule inventory and hash;
- plan/config hash;
- parser commit;
- public-gold hashes;
- development output hash;
- development metrics;
- Python version;
- dependency snapshot;
- run command;
- freeze date.

This freeze manifest is planned but is not created in Stage 3B.1.

## Held-out protocol

- Held-out loading must require an explicit flag and the valid future freeze manifest.
- The first held-out result must be preserved.
- No rule may change after held-out results are seen under v0.1.
- Any change requires `deterministic-baseline-v0.2` and a declared new experiment cycle.
- Held-out results must be reported separately from development results.

## Acceptance gates

- All five development public-PDF sources complete without an unhandled exception.
- All emitted `CandidateExtractionResult` records validate against schema version `0.1`.
- Development metrics report exact numerators and denominators.
- Repeated runs over identical inputs produce byte-identical canonical outputs.
- No held-out fact or challenge-case semantic content is loaded during rule design or tuning.
- No source-specific, filename-specific, page-specific or expected-value-specific extraction rules are used.
- All three development challenge cases receive an explicit case-level outcome.
- No minimum development F1 is required for baseline acceptance.

These are process and reporting gates, not an unobserved performance claim.

## Failure analysis taxonomy

- parser loss;
- reading-order error;
- subject-attribution failure;
- predicate-classification failure;
- modal-strengthening error;
- value-boundary error;
- value-normalisation error;
- denominator or qualifier loss;
- false precision;
- table-relationship loss;
- unsupported extraction;
- missed fact;
- duplicate candidate;
- over-routing;
- under-routing;
- incorrect evidence.

## Limitations

- The development set is small.
- The scored data are concentrated in public-sector PDFs.
- Review was completed by a single project owner.
- The held-out set is procedural, not blind.
- Strict matching may under-credit semantically similar wording.
- PDF blocks are page-level.
- Confidence is heuristic.
- No LLM comparison exists yet.
- Reconciliation and final fact states are not included.

## Claim boundary

- No baseline result exists yet.
- No public-gold score exists yet.
- No held-out extraction has run.
- No production-readiness claim is made.
- No claim is made that deterministic rules outperform an LLM.
- This pull request freezes only the experiment plan.

## Next implementation PRs

1. Stage 3B.2 development-only annotation loader and held-out guard.
2. Stage 3B.3 deterministic rule engine.
3. Stage 3B.4 development evaluation and baseline freeze.
4. Stage 3B.5 first held-out evaluation.
