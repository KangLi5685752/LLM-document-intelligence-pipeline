# Stage 3 Candidate-Extraction Design

## Status and scope

Stage 3A, Stage 3B.1 planning, the Stage 3B.2 development-only gold access boundary, the Stage 3B.3 deterministic rule engine, the Stage 3B.4A strict evaluator, the Stage 3B.4B execution/freeze workflow implementation and the Stage 3B.4C v0.2 planning freeze are complete. The first `deterministic-baseline-v0.1` development observation is preserved: four sources produced reproducible outputs and S004 failed reproducibly. The run did not satisfy five-source acceptance and produced no complete report or baseline freeze. The source-independent `deterministic-baseline-v0.2` scope is frozen before implementation, with candidate schema, predicate vocabulary and matching unchanged. The repository contains no v0.2 extractor or score, reconciliation, LLM call or held-out extraction.

## Three distinct data layers

### ParsedDocument

`ParsedDocument` is the implemented Stage 2 format-level output. It contains normalized text blocks, document metadata, parsing warnings, and source provenance. It does not contain extracted entities or facts.

### CandidateExtractionResult

`CandidateExtractionResult` is the implemented Stage 3 pre-reconciliation contract. It contains:

- proposed entities;
- candidate facts;
- evidence references linked to existing `ParsedDocument` blocks;
- bounded extraction metadata and warnings.

A candidate fact is an observation proposed by a deterministic extractor, future LLM extractor, or manual annotation. It is not a current fact and has no final `fact_state`.

### KnowledgeExtractionResult

`KnowledgeExtractionResult` remains a planned reconciled output. A later stage may assign current, superseded, duplicate, and unresolved-conflict states only after comparing candidates and their evidence. No runtime model or reconciliation implementation exists yet.

## Why extraction and reconciliation are separate

Extraction answers: “What bounded statement and evidence did this source appear to contain?” Reconciliation answers: “How should candidates across related documents be combined, compared, or left unresolved?” Keeping these questions separate prevents an extractor from silently presenting a recent, repeated, or high-confidence candidate as authoritative.

This boundary also allows deterministic and future LLM approaches to emit the same candidate schema. Their candidate quality can later be compared before any shared reconciliation policy is applied.

## Candidate contract

Schema version `0.1` uses strict Pydantic v2 models with unknown fields forbidden. Candidate facts preserve:

- source and document-family identifiers;
- source-stated subject text and bounded subject type;
- one registered predicate;
- raw and bounded normalized values;
- qualifiers;
- evidence IDs;
- confidence, review status, method, and warnings.

Candidate evidence preserves a short excerpt plus the existing block ID, source ID, location type, and location value. Paths are not part of the contract. References to missing evidence or sources are invalid. `CandidateFact` and `GoldFactAnnotation` call the same runtime predicate-use validator, so registered subject types, value types, required qualifiers, and declared qualifier names cannot diverge between production candidates and evaluation labels.

## Predicate vocabulary

Vocabulary v0.1 contains exactly 20 canonical predicates. It is intentionally bounded rather than a general ontology. Definitions constrain subject types, value types, aliases, and contextual qualifiers. Normalization handles spacing, hyphens, case, and documented legacy synthetic names; unknown predicates fail instead of extending the registry implicitly. Runtime validation also rejects incompatible subject or value types, missing or empty required qualifiers, and qualifiers not declared for the canonical predicate.

The vocabulary contains no source IDs, filenames, held-out values, or source-specific rules.

## Evidence and annotation requirements

Every frozen public fact points to one existing Stage 2 `PAGE_TEXT` block, the correct 1-based PDF page, and a short excerpt that occurs in normalized block text. Structural validation also reconciles the source split and document family. Project-owner semantic review is complete for all 35 facts and six challenge cases, and the manifest protects both JSONL files with SHA-256 hashes.

Ambiguous, unsupported, and missing-value examples are separate challenge cases. They specify review, rejection, or missing-value preservation without inventing an expected value.

## Stage 3A held-out control

The public benchmark is procedural because labels are visible in the repository. Stage 3B may load development labels during deterministic-baseline design and development evaluation. Held-out facts and cases cannot be loaded by rule-design code, tests or tuning; the experiment version, rules and code must be frozen before held-out evaluation.

## Stage 3B.1 deterministic-baseline plan

The baseline contract was frozen before implementation in the [Stage 3B deterministic baseline plan](stage_3b_deterministic_baseline_plan.md), [machine-readable experiment configuration](../configs/experiments/deterministic_baseline_v0.1.json), and [matching protocol v0.1](stage_3b_matching_protocol.md).

Baseline v0.1 scores candidate extraction for eight predicates: `action_status`, `budget`, `commitment`, `decision`, `metric`, `recommendation`, `requirement` and `risk`. Its primary scored scope is development-only public-PDF data. Development synthetic documents may later provide non-scored format and contract smoke tests, while reconciliation and synthetic final-state evaluation remain separate future work.

Stage 3B.2 development-only annotation loading and its fail-closed held-out access guard were implemented before baseline execution. The later v0.1 observation produced preliminary incomplete counts, not an accepted metric.

## Stage 3B.2 development-only gold access

The [development-only public-gold loader](stage_3b_development_gold_loader.md) validates the frozen experiment configuration, public-gold manifest, repository-relative paths, corpus split and binary content hashes before returning labels. It metadata-scans ID, source and split fields from bounded binary JSONL lines, semantically validates only the 25 development facts and three development challenge cases, and returns them in deterministic experiment-source order.

Held-out or unknown access modes fail before repository-root resolution or file I/O. Held-out lines are read only for content hashing and metadata routing; no held-out semantic model is constructed. The generic complete-dataset loaders remain available for Stage 3A validation only. Baseline implementation and evaluation code must use the guarded API, while the future extractor must receive only `ParsedDocument` and must not import any gold loader.

The gold loader remains evaluation-only and is not imported by the extractor. Stage 3B.3 implements candidate generation without enabling held-out access or computing a metric.

## Stage 3B.3 deterministic rule engine

The [deterministic rule engine](stage_3b_deterministic_rule_engine.md) is a pure `ParsedDocument`-to-`CandidateExtractionResult` transform. It emits only the eight baseline predicates: `action_status`, `budget`, `commitment`, `decision`, `metric`, `recommendation`, `requirement` and `risk`.

The implementation has a frozen ten-family inventory: eight candidate-producing rules plus shared same-block subject-attribution and exact-evidence policies. It segments bounded statements inside individual blocks, never crosses a source location, preserves exact evidence excerpts of at most 240 characters and derives batch, evidence and candidate IDs from stable SHA-256 inputs. Canonical serialization uses sorted, two-space-indented JSON with no timestamp.

Explicit same-statement candidates use the `0.90` confidence band, eligible same-block contextual candidates use `0.70`, and bounded flattened-layout ambiguity uses `0.50` with required review. Unsafe subjects, multiple plausible values, unbounded table relationships and overlong evidence cause deterministic abstention warnings. Candidate entities remain empty; each fact retains the source-stated subject, while entity consolidation remains future work.

The v0.1 rule engine and observation are immutable. The separately reviewed v0.2 experiment plan now freezes the permitted source-independent correction and tuning scope; implementation remains future work and held-out access remains blocked.

## Stage 3B.4A strict development evaluator

The [strict development evaluator](stage_3b_development_evaluator.md) implements protocol-v0.1 comparison normalization, typed value comparison, material gold qualifiers and source-bounded deterministic one-to-one matching. Extra semantic duplicates remain in the candidate population as false positives, while extra declared qualifier keys are reported rather than used to block an otherwise strict match.

Normalized-value accuracy uses a separate one-to-one alignment that excludes normalized value from its key. Evidence source, block/location and normalized excerpt diagnostics use only referenced evidence on strict matches. Explicit attempt models keep failed sources in the five-source schema-valid-rate denominator, and source-level primary/repeat hashes produce deterministic reproducibility states.

Challenge-case outcomes require three explicit owner assessments; the evaluator adds no source-specific automated pass rule. Reports retain exact numerators and denominators and serialize deterministically without timestamps, paths, source text or final fact state. The evaluator accepts already loaded gold and precomputed attempts and performs no file loading or extraction itself.

Stage 3B.4A itself observed no score. Stage 3B.4B records the first preliminary result in a separate observation lock before owner challenge assessment.

## Stage 3B.4B development execution and freeze

The [development execution and freeze workflow](stage_3b_development_execution_and_freeze.md) implements explicit `prepare` and `finalize` modes.

`prepare` validates the exact five public development PDFs and their frozen Stage 2 parser provenance, opens their ParsedDocument JSON through explicit paths, runs deterministic extraction twice, stores canonical primary and repeat evidence, and immediately writes the first observation lock. It then creates structural unmatched diagnostics and a development-only owner-review packet. The accompanying template leaves every outcome and rationale null.

`finalize` is implemented before observation. It refuses incomplete owner assessments, changed immutable hashes, failed source attempts, non-identical repeated outputs or counts that differ from the observation lock. Only after three completed owner assessments does it invoke the frozen evaluator and write the complete report, bounded error analysis and baseline freeze manifest.

The baseline freeze manifest retains `held_out_access_status=still_blocked_pending_separate_guarded_execution`. It records evidence for a future gate but neither changes the development-only loader nor authorizes held-out execution.

## First v0.1 execution and transition boundary

The first real v0.1 workflow execution parsed all nine development sources and attempted the five scored public PDFs twice. S001, S002, S003 and S006 produced byte-identical outputs. S004 failed identically during `CandidateFact` validation, so the aggregate five-source reproducibility gate failed and no S004 output exists.

The immutable observation lock records preliminary strict diagnostics of 0 TP, 288 FP and 25 FN. They are not accepted extraction metrics. No complete report, owner-assessed challenge result or baseline freeze exists. The [failed first-observation report](stage_3b_v0_1_first_observation_failure.md) records the sanitized diagnosis and claim boundary.

The v0.1 implementation and observation must not be modified or overwritten. The diagnosed failure is source-independent, but correcting it changes extraction output semantics. Work therefore transitions to the separately planned and frozen `deterministic-baseline-v0.2`; formal owner challenge review resumes only after a complete versioned run. Held-out sources and labels remain inaccessible.

## Stage 3B.4C v0.2 planning and freeze

The [v0.2 experiment plan](stage_3b_v0_2_experiment_plan.md), [error matrix](stage_3b_v0_2_error_matrix.md), [versioning and freeze record](stage_3b_v0_2_versioning_and_freeze.md), and machine-readable configuration freeze the next experiment before implementation. The evidence base is limited to the immutable v0.1 development observation, four published outputs, structural diagnostics, guarded development gold and source-independent implementation review.

The required v0.2 behavior is candidate-level predicate-contract abstention with a stable warning, neutral reproduction of the diagnosed incompatible commitment draft, bounded commitment trigger eligibility, ambiguous metric review routing and additive version isolation. Optional changes are limited to directly evidenced action-status coverage, actor validation, metric qualifiers, requirement narrowing, exact duplicate suppression and subject-span trimming.

Candidate schema `0.1`, predicate vocabulary `0.1`, matching protocol `0.1`, strict normalization, metric denominators, public gold, splits and parser behavior remain frozen. The v0.2 report/run/freeze stack must use additive versioned models because the v0.1 contracts hard-code their experiment identity. Shared candidate models, predicates, guarded gold loading and matching may be reused unchanged.

The plan separates twelve mandatory process gates from seven non-binding quality targets. Implementation must be committed before its first real development execution; the first diagnostics must be locked before owner review; and any later semantic change requires v0.3. No v0.2 execution or score is produced by Stage 3B.4C.

## Current limitations

- The deterministic extractor uses shallow English-language regex and structural heuristics; no LLM extractor exists.
- Frozen `public-gold-v0.1` has 35 owner-verified facts and six owner-verified challenge cases, but only one project-owner reviewer and no inter-annotator agreement.
- Page-level blocks can preserve awkward PDF whitespace and coarse evidence spans.
- The v0.1 preliminary observation is limited to its immutable lock and four successful outputs; the S004 failure prevents finalization and no final public-gold report is implied.
- The v0.2 plan is frozen, but its additive modules, neutral regressions, real development execution, owner review and final freeze remain unimplemented.
- Final reconciliation, duplicate handling, conflict handling, and review workflow remain planned.
