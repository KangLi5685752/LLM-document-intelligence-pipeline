# Stage 3B deterministic-baseline-v0.2 Experiment Plan

## Status

Frozen before implementation on 2026-07-26. This plan defines a development-only, source-independent correction and tuning scope for `deterministic-baseline-v0.2`. No v0.2 extractor, candidate output, score, observation lock, owner assessment or freeze manifest exists.

The parent is the immutable failed first observation of `deterministic-baseline-v0.1`. Candidate schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1`, `public-gold-v0.1`, corpus `stage1-corpus-v1.0` and parser commit `71148262f094d54ec7d95e45958bd1aaefc64793` remain fixed.

The machine-readable plan freezes its exact 33-key top-level shape, every ordered array, all policy text, the complete future file inventory and the nested behavior contracts. The validator also anchors 24 v0.1 semantic and planning files to their SHA-256 values at planning base `ad8ef2d40a10c16047ebec37acaa2b890310c0f4`, in addition to the nine published artifacts.

## Motivation

The v0.1 workflow preserved repeat-identical outputs for S001, S002, S003 and S006 but failed reproducibly on S004. Read-only diagnosis isolated one commitment draft whose `metric` subject type is incompatible with the frozen commitment predicate contract. The schema correctly rejected it, but aggregate result construction allowed one invalid draft to fail the document.

The incomplete observation also provides bounded tuning evidence: 243 of 288 published candidates were commitments, all 288 were marked `review_status=not_required`, and strict diagnostics were 0 TP, 288 FP and 25 FN. These are preliminary parent-observation diagnostics, not accepted metrics. The exact evidence and source-independent decisions are recorded in the [v0.2 error matrix](stage_3b_v0_2_error_matrix.md).

## Parent v0.1 observation

- Parent experiment: `deterministic-baseline-v0.1`.
- Planning base: `ad8ef2d40a10c16047ebec37acaa2b890310c0f4`.
- Observation-lock SHA-256: `AD560F6DC634F99B08564ECFDB54C3156425473B305894F6D6BD4BB475D64DC0`.
- Successful repeat-identical source outputs: S001, S002, S003 and S006.
- Reproducible failed source: S004, with no candidate output.
- Preliminary diagnostics: 0 TP, 288 FP, 25 FN, 7 extra semantic duplicates and 0 review-required candidates.
- Formal challenge outcomes: deliberately deferred because S004 did not complete.
- Freeze state: v0.1 cannot be finalized and no accepted development result exists.

All nine published v0.1 artifacts and all 24 protected v0.1 semantic, shared-contract and planning files remain immutable.

## Scope

The scored inventory remains exactly S001, S002, S003, S004 and S006, with 25 development facts and the three development challenge cases declared in the machine-readable plan. Only already-observed development evidence may justify a change. Neutral synthetic unit fixtures may test general behavior but are not scored.

The result remains candidate extraction only. Network calls, LLM use and reconciliation remain disabled. The extractor receives `ParsedDocument` only. The unchanged guarded gold loader remains evaluation-only, and neither extraction rules nor neutral rule tests may import it.

The implementation scope is limited to the five required change families and six included optional families below. An optional family may be omitted during implementation if its neutral tests cannot demonstrate the bounded behavior safely; no replacement family may be added without reviewing and refreezing this plan before execution.

## Required corrections

### Candidate-level predicate-contract guard

Each proposed draft must be checked against the unchanged predicate contract before `CandidateFact` construction. The exact validation order is predicate, subject type, value type, required qualifiers and declared qualifier names. An incompatible draft must be omitted, the result must receive the stable warning `abstained_incompatible_predicate_contract`, and unrelated valid candidates must remain in the document result.

The guard must not weaken schema validation, coerce `metric` to `organisation`, invent a substitute subject type, or silently discard the draft. Unexpected programming or result-level validation errors must still fail explicitly; the guard is bounded to candidate predicate-contract incompatibility.

### Neutral incompatible-commitment regression

A future neutral one-block fixture must combine a commitment trigger with a subject classified as `metric`. It must contain no real source identifier, source wording, government title, fixed page, annotation identifier or expected benchmark value. The test must prove that:

- the document completes without an exception;
- the incompatible candidate is absent;
- `abstained_incompatible_predicate_contract` is present;
- an unrelated valid candidate remains present; and
- two executions serialize to byte-identical output.

### Commitment trigger eligibility and confidence

The frozen trigger inventories are:

- explicit commitment: `commit to`, `commits to`, `has committed to`;
- weaker future intent: `intend to`, `intends to`, `plan to`, `plans to`, `will`, `will not`.

Explicit commitment receives confidence `0.9`; weaker future intent receives `0.7`. Eligible subject types are exactly `initiative`, `organisation`, `other`, `policy` and `programme`. An `other` subject must pass the generic noun-phrase actor contract: 1-12 normalized tokens, at most 79 characters, at least one ASCII letter, no clause boundary or finite subordinate/relative clause, no impersonal demonstrative, and no metric/population head from the frozen inventory.

The exact weak copular/passive exclusions are `intend to be`, `intends to be`, `plan to be`, `plans to be`, `will be` and `will not be`; passive constructions without a named actor abstain. Clause-like rejection covers `:`, `;`, `?`, `!`, a newline, coordinated finite clauses, and the markers `although`, `because`, `if`, `that`, `when`, `where`, `which`, `while` and `who`. A heading-context actor is same-block only, must be the one unique eligible heading, must pass the actor contract and receives confidence `0.7`. Trigger negation is retained in both raw and normalized values.

Exact commitment warning codes are `abstained_commitment_ambiguous_heading_context`, `abstained_commitment_clause_like_subject`, `abstained_commitment_copular_or_passive`, `abstained_commitment_ineligible_subject` and `abstained_commitment_subject_too_long`. Subject-span trimming may remove one frozen bullet/enumeration marker only; semantic word removal is forbidden.

These rules are source-independent. They contain no identifier, title, filename, page or expected value.

### Ambiguous metric review routing

When one bounded statement contains multiple nearby values and the population/value relationship supports more than one plausible metric interpretation, v0.2 must not select one interpretation as authoritative. For a bounded inventory of at most three values and three plausible interpretations, it may emit each plausible candidate with:

- confidence `0.5`;
- `evidence_status=ambiguous`;
- `review_status=required`;
- warning `ambiguous_metric_value_relationship`; and
- the same bounded evidence span.

Ordering is frozen as evidence block sequence, evidence start offset, normalized subject text, typed normalized value and candidate ID. Duplicate candidate identities must be suppressed. If either maximum is exceeded, the extractor emits no ambiguous candidate and records `abstained_ambiguous_metric_bounds_exceeded`. The unchanged candidate schema therefore represents every bounded plausible interpretation separately rather than inventing a missing value, changing value types or choosing one value.

### Additive version isolation

Implementation must use new `_v0_2` modules and two distinct v0.2 CLIs. `deterministic_v0_2_cli.py` handles exactly one `ParsedDocument`. `development_run_v0_2_cli.py` handles prepare/finalize, exact five-source execution, primary/repeat attempts, first-observation locking, owner review and final freeze. The existing candidate schema, predicate vocabulary, guarded development gold loader and strict matching functions may be reused unchanged. Report, run, observation, owner-review, unmatched-inventory and freeze models require additive v0.2 forms because the v0.1 models hard-code `deterministic-baseline-v0.1`.

The exact future inventory and immutable boundary are in the [versioning and freeze record](stage_3b_v0_2_versioning_and_freeze.md). No implementation file is created by this planning task.

## Optional bounded corrections

| Family | v0.1 evidence | Predicate | Approved behavior and neutral test | FP risk | FN risk | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| `action_status_phrase_coverage` | PG-V01-S003-001 had no same-source candidate; its bounded evidence contains an explicit progress cue but no action-noun form recognized by v0.1 | `action_status` | Same-statement status values are exactly `completed`, `delayed`, `delivered`, `in progress`, `met`, `not started`, `on track`; require an `initiative`, `policy` or `programme` subject, shared bounds and one frozen action cue | A generic progress phrase could be misread as an action | Narrow actor eligibility may retain the miss | Include |
| `generic_noun_phrase_actor_validation` | 216 candidates used `subject_type=other`; commitments contributed 201, requirements 10 and decisions 5 | `commitment`, `requirement`, `decision` | For `other` only, require 1-12 tokens, at most 79 characters, an ASCII letter, no clause/impersonal form and no frozen metric/population head | A weak noun phrase could still pass | Legitimate unusual actors may abstain | Include |
| `metric_qualifier_extraction` | Six metric annotations and 24 candidate diagnostics had `qualifier_missing` and `qualifier_mismatch`; 19 metric candidates were confidence `0.7` | `metric` | Same-statement only: one explicitly linked metric-name noun phrase, frozen population cues, adjacent literal percentage unit and one four-digit year; competing pairings use the ambiguous-metric contract | Nearby qualifiers could attach incorrectly | Conservative attachment may leave qualifiers missing | Include |
| `requirement_trigger_narrowing` | 15 requirement candidates were FP; 10 used `other` subjects and 6 had clause-like subjects | `requirement` | Exact triggers are `are required to`, `is required to`, `must`, `must not`, `required to`, `shall`, `shall not`; require an eligible bounded actor and a 1-40-token, at-most-240-character action; exclude `could`, `may`, `might`, `should` | A formal-looking sentence may still over-trigger | Passive but genuine requirements may abstain | Include |
| `semantic_duplicate_suppression` | Seven extra semantic duplicates were observed; 13 candidate rows belonged to duplicate groups in structural diagnostics | all approved predicates | Exact key order: source ID, normalized subject, subject type, predicate, value type, typed normalized value, sorted qualifiers; retain the first by block sequence, statement offset, rule priority and stable signature | Over-broad keys could hide distinct facts | Exact-key policy leaves paraphrase duplicates | Include |
| `subject_span_trimming` | 86 commitment, 6 requirement and 2 decision subjects met the bounded clause-like diagnostic; 5 commitment subjects were at least 80 characters | `commitment`, `requirement`, `decision` | Remove at most one frozen bullet or one ASCII letter/integer enumeration marker; never remove semantic words; reject the span if bounds still fail | Trimming could remove meaningful actor text | Strict limits may abstain on long valid actors | Include |

The following families are excluded because the parent evidence does not identify a bounded safe correction:

- Heading-context numbered recommendation extraction: four S001 recommendation annotations had no candidate, but their evidence did not expose a stable numbered-recommendation or explicit-recommend trigger. Expanding heading inference would be speculative.
- Budget subject resolution: two S003 budget annotations had no candidate, but the evidence exposed currency without the relationship cue required by v0.1. Relaxing that cue risks treating bare currency as budget.
- Explicit risk-statement coverage: the single development risk annotation belongs to failed S004 and cannot be compared with a completed source result; no stable generic missed trigger is established.
- Decision proposal exclusion: none of the five observed decision candidates contained the diagnosed proposal/option pattern, and v0.1 already excludes that pattern. No additional exclusion is evidenced.

## Prohibited changes

- Modify any v0.1 observation artifact, source module or planning document.
- Modify public gold, development/held-out splits or source checksums.
- Change the parser or parser version.
- Change `CandidateExtractionResult` schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1`, strict-match normalization or metric denominators.
- Add fuzzy matching to improve apparent TP.
- Add embeddings, an LLM or network calls.
- Use source IDs, filenames, document titles, fixed page numbers, annotation IDs or known expected values as rule conditions.
- Add per-document exceptions.
- Read held-out facts or held-out challenge semantics.
- Change code after the first v0.2 observation while retaining the same experiment version.

## Pre-observation test gates

1. The plan validator passes and the machine-readable plan remains canonical.
2. All nine v0.1 development observation artifact hashes match their frozen values.
3. v0.1 implementation, plans and semantic files remain byte-identical.
4. A neutral incompatible commitment fixture completes without a document-level exception.
5. The incompatible draft is omitted with `abstained_incompatible_predicate_contract`.
6. Unrelated valid candidates survive candidate-level contract abstention.
7. Repeated neutral fixture outputs are byte-identical.
8. Explicit and weak commitment trigger groups have separate neutral unit coverage.
9. A bounded ambiguous multi-value metric routes to required review without choosing a value.
10. Every included optional change family has neutral positive and negative regression coverage.
11. The full test suite passes.
12. The implementation commit exists before any real v0.2 development extraction.

## Process acceptance gates

1. All five development public PDFs complete in primary and repeat runs.
2. Zero unhandled extraction exceptions.
3. Every result validates against `CandidateExtractionResult` schema `0.1`.
4. All five primary/repeat output pairs are byte-identical.
5. Exact output hashes are preserved.
6. Exact metric numerators and denominators are reported.
7. All three development challenge cases receive explicit owner review.
8. No held-out semantic content is loaded.
9. No source-specific extraction rule exists.
10. v0.1 code and observation hashes remain unchanged.
11. v0.2 implementation is committed before its first real development run.
12. No minimum F1 is required for process acceptance.

A complete but weak baseline may be frozen and reported honestly.

## Non-binding quality targets

- Strict TP greater than zero.
- Total commitment candidates below the v0.1 count of 243.
- Total candidate count below the v0.1 count of 288.
- At least one candidate routed to review when a bounded ambiguous relationship is emitted.
- No incompatible predicate/subject candidate.
- No new predicate family dominates the entire candidate population.
- Fewer semantic duplicates than v0.1 where generic deduplication is approved.

Each failure must be reported. A failed quality target does not authorize additional v0.2 tuning after observation and does not by itself prevent process acceptance.

## Development execution protocol

1. Review and merge this frozen plan.
2. Implement only the approved additive modules and neutral tests.
3. Satisfy every pre-observation test gate and commit the complete implementation.
4. Record that commit as the preparation boundary.
5. Run primary and repeat extraction over exactly the five development public PDFs.
6. Write a versioned v0.2 observation lock immediately when the first strict diagnostics become visible, preserving input/output hashes and all attempts.
7. Make no semantic code change under v0.2 after that lock.
8. If all sources complete reproducibly, prepare structural diagnostics and the three-case owner-review packet.
9. Finalize only after complete owner review and every process gate passes.

The future `development_run_v0_2_cli.py` owns this prepare/finalize workflow. The single-document `deterministic_v0_2_cli.py` must not load gold, run five-source orchestration, create an observation lock or finalize a baseline. The workflow must fail closed on an existing output root unless explicitly operating in the approved versioned v0.2 location. It must not overwrite v0.1 evidence.

## Owner-review boundary

Owner review begins only after all five source attempts succeed twice and the first v0.2 observation is locked. The three development challenge cases require explicit outcome, rationale and candidate/warning references. An extraction crash, missing source output or mere absence of a candidate is not a passing challenge outcome.

## Post-observation policy

After the first v0.2 observation, bug fixes, trigger changes, subject/qualifier changes, confidence changes, review-routing changes or any other output-semantic change require `deterministic-baseline-v0.3`. The v0.2 code commit and evidence remain preserved. Documentation may clarify an existing result only if it does not change code, evaluation semantics or artifact bytes.

## Held-out boundary

Held-out access is `blocked_until_successful_v0.2_development_freeze_and_separate_guard`. A successful development freeze is necessary but not sufficient. A later reviewed guard and explicit invocation are still required. This plan contains no held-out source inventory, fact value or challenge semantic description, and the validator performs no held-out load.

## Claim boundary

After this planning commit, the project may claim that a source-independent v0.2 correction and tuning scope was frozen before implementation, based only on immutable development evidence. It may not claim that v0.2 is implemented, that extraction completed, that any v0.2 metric or quality target was achieved, that owner review occurred, that v0.2 was frozen as a result, or that held-out performance exists.
