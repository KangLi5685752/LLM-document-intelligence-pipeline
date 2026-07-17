# Stage 1A Corpus Strategy

## Status

This document defines a planned source strategy. The initial register contains candidates only: no corpus audit or parser has been completed, and no source has yet been used for extraction evaluation.

## Corpus objective

Build a traceable, legally cautious evaluation corpus for testing how heterogeneous public documents can be converted into structured, evidence-linked project intelligence. The corpus should support later comparison of deterministic and LLM-assisted extraction while preserving enough source diversity to test ambiguity, conflicts, missing information, and provenance.

## Primary domain

The primary domain is **UK public-sector AI initiatives, adoption, evaluation and governance**.

This domain supports the planned extraction schema because its documents commonly describe organisations, sectors, technologies, programme or project stages, decisions, actions, milestones, risks, governance controls, findings, and outcomes. Those fields can later support project comparison while retaining page, slide, or section-level evidence. This is a scope hypothesis for corpus design, not an extraction result.

## Planned document roles

| Role | Intended contribution |
| --- | --- |
| strategy | Direction, priorities, commitments, actors, and intended outcomes. |
| government response | Accepted, rejected, or qualified recommendations and planned actions. |
| progress report | Delivery status, milestones, changes, dependencies, and reported outcomes. |
| operational guidance | Controls, processes, responsibilities, risks, and implementation practices. |
| adoption research | Adoption patterns, barriers, enablers, sectors, methods, and evidence. |
| governance report | Standards, accountability, oversight, risks, and recommendations. |
| project evaluation | Project context, intervention, evaluation method, findings, limitations, and lessons. |

The role labels describe intended corpus coverage. They do not imply that any candidate has been approved or analysed.

## Real and synthetic document strategy

- **Real documents:** use public-sector sources to provide authentic language, structure, publication conventions, and cross-document variation. Each source remains a candidate until its provenance, licence, content risk, format, and relevance have been reviewed.
- **Synthetic documents:** create clearly labelled challenge cases for controlled ambiguity, contradictions, missing fields, unsupported claims, duplicated facts, temporal changes, and evidence-location tests. Synthetic material must not be presented as an authentic government source.
- **Evaluation separation:** record whether an item is real or synthetic and define train, development, and evaluation boundaries before extraction experiments to reduce leakage.

## Format strategy

- Public PDFs are the primary real-document corpus for the MVP.
- Public or synthetic PPTX files may be used for format testing when they are relevant and appropriately licensed; unrelated PPTX files will not be added merely to satisfy format variety.
- Synthetic email-style text will provide controlled edge cases without using private mailboxes or personal correspondence.
- HTML sources are deferred unless HTML ingestion is explicitly added in a later stage.

## Inclusion criteria

A source may advance from candidate to approved only when all applicable criteria are satisfied:

- It is materially relevant to UK public-sector AI initiatives, adoption, evaluation, or governance.
- It has an identifiable publisher, stable landing page, publication date or version, and traceable provenance.
- Its document role adds useful coverage rather than unnecessary duplication.
- Its format is supported by the current corpus plan, or a documented exception is approved.
- Its copyright and licence notices have been reviewed for the specific source.
- Third-party material, logos, photographs, graphics, and personal-data risks have been recorded.
- The planned local use, derived-text handling, and any redistribution are permitted by the recorded decision.
- The document is sufficiently accessible for later structure and text-extractability inspection without requiring OCR in the MVP.
- Its inclusion will not compromise a predefined evaluation split or introduce known leakage.

## Exclusion criteria

A source should be rejected or deferred when any applicable condition holds:

- Provenance, publisher, version, or licence evidence cannot be established.
- The source is unrelated to the primary domain or duplicates existing coverage without a clear analytical purpose.
- It contains confidential material, material personal-data risk, or third-party content that cannot be safely separated or reviewed.
- It is image-only or depends on OCR, which is outside the MVP.
- Its format is unsupported and does not justify an explicit scope change.
- It is withdrawn, superseded, or materially updated without adequate version history for the intended use.
- Its use would create evaluation leakage or an unmanageable imbalance in document roles, publishers, sectors, or publication periods.

## Corpus-status values

- **candidate:** identified for review; not approved for download, extraction, or evaluation.
- **approved:** all required scope, licence, risk, and technical reviews are complete for the documented use.
- **deferred:** potentially relevant, but blocked by format, timing, licence review, duplication, or another recorded dependency.
- **rejected:** excluded with a documented reason.

Candidate does not mean approved.

## Main risks

- **Licence ambiguity:** landing-page terms may not resolve the rights attached to a specific file.
- **Third-party material:** charts, photographs, quotations, or commissioned content may have separate rights.
- **Format sprawl:** adding formats before their value is established may delay evaluation.
- **Domain imbalance:** central-government strategy documents may crowd out operational, regional, health, or evaluation perspectives.
- **Source updates:** landing pages and files may change after registration.
- **Withdrawn or superseded documents:** later versions may alter interpretation or make the selected copy unsuitable.
- **Evaluation leakage:** repeated publications, derived reports, or synthetic cases influenced by evaluation examples may inflate results.

## Current evaluation boundary

No registered source has yet been approved as an evaluation-corpus item or used for extraction evaluation. Stage 1A records candidates and review requirements only.
