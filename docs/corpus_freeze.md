# Stage 1 Corpus Freeze

- **Corpus version:** `stage1-corpus-v1.0`
- **Freeze date:** 2026-07-20
- **Active source count:** 15
- **Deferred source count:** 2
- **Development sources:** 9
- **Held-out sources:** 6

## Frozen assets

The freeze covers:

- source IDs;
- source files and hashes;
- active versus deferred status;
- document-family assignments;
- development and held-out splits;
- synthetic source contents;
- synthetic ground truth;
- evidence locations;
- source-provenance records.

## Active source inventory

The active corpus contains:

- 7 public PDFs;
- 2 synthetic PPTX decks;
- 6 synthetic EML messages;
- 4 labelled synthetic document families.

## Deferred sources

S008-S009 remain deferred. They are not part of corpus v1.0 and cannot silently enter Stage 2 or evaluation.

## Split rationale

- S001-S003 remain together to prevent family leakage.
- S005 tests visual and multi-column PDF generalisation.
- S007 tests older governance content and two-column reading order.
- S011 tests held-out PPTX conflict behavior.
- S015-S017 test held-out email chronology and unresolved-conflict behavior.
- Each email family remains wholly within one split.

## Freeze rules

Allowed without a new corpus version:

- parser and extraction implementation;
- tests that do not change source contents;
- additional versioned annotations;
- clarification of documentation;
- correction of non-semantic metadata errors with a recorded decision.

A new corpus version is required for:

- adding or removing active sources;
- modifying source-file bytes;
- changing hashes;
- changing synthetic facts;
- changing ground-truth meaning;
- moving a source or family between splits;
- changing family boundaries;
- adding deferred sources to active evaluation.

## Held-out protocol

Held-out is procedural, not a secret blind benchmark:

- the repository is public;
- the same person designs and evaluates the project;
- source contents have already been audited;
- held-out values must not be used as prompt examples or special-case extraction rules;
- final held-out evaluation occurs only after an experiment version is frozen;
- any post-held-out adjustment creates a new declared experiment cycle.

## Annotation status

- Synthetic ground truth is complete for four families.
- Public-PDF gold annotation is planned but not yet created.
- Future public labels do not change source membership or splits.
- Single-annotator limitations must be reported.

## Readiness decision

The corpus is ready for Stage 2 ingestion implementation.

This is not evidence that ingestion or extraction currently works.
