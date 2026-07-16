# Project Charter

## Problem statement

Project knowledge is commonly distributed across PDF reports, presentation decks, and email-style narrative text. These sources differ in layout and structure, and manual consolidation is slow and inconsistent. Naive automation can make the problem worse by losing source context, producing invalid structures, or asserting unsupported facts. The project will investigate a traceable workflow that converts heterogeneous documents into validated structured knowledge and makes uncertainty visible to a human reviewer.

## Product statement

An evaluated portfolio prototype that turns heterogeneous project documents into schema-validated, evidence-linked records and routes ambiguous or unsupported outputs for human review.

## Target users

- Analysts consolidating project facts from mixed document collections.
- Project and knowledge-management professionals reviewing extracted decisions, risks, actions, milestones, and entities.
- Data and AI practitioners assessing document extraction quality and provenance.
- Portfolio reviewers evaluating practical LLM engineering, testing, and responsible-use decisions.

## Core use cases

1. Convert supported PDF, PPTX, and email-style text documents into a common structured representation.
2. Extract defined project-intelligence fields into schema-valid records.
3. Trace an extracted claim to its page, slide, or section-level source evidence.
4. Flag unsupported, conflicting, incomplete, or ambiguous outputs for human review instead of silently accepting them.
5. Compare a deterministic baseline with structured LLM extraction using a reproducible evaluation set.

## Non-goals

- Recommending products or users, predicting preferences, or implementing any recommendation functionality.
- Building a production enterprise document-management, records-management, or compliance platform.
- Supporting OCR or scanned-image documents in the MVP.
- Supporting every document format, language, domain, or extraction schema.
- Building grounded RAG, an API, BigQuery integration, or cloud deployment before extraction evaluation.
- Fully automating decisions that require accountable human judgement.

## Separation from the recommendation-system project

The recommendation dissertation asks: **What products should be recommended to a user and why?** This project asks: **How can heterogeneous documents be converted into validated, traceable, and queryable structured knowledge?** They have separate data, models, evaluation criteria, and deliverables. This repository replaces a previously planned standalone RAG portfolio project; it does not replace or extend the recommendation dissertation.

## Data strategy

The evaluation corpus will use appropriately licensed public documents plus clearly labelled synthetic documents and mutations. Public documents will provide realistic structure and language. Synthetic edge cases will deliberately cover missing fields, contradictory statements, duplicated facts, ambiguous references, unsupported claims, malformed structures, and boundary conditions that may be rare in a small public corpus. No confidential, employer, client, personal mailbox, or dissertation data will be used.

## Intended use

- Portfolio-scale experimentation with heterogeneous document parsing and structured extraction.
- Reproducible comparison of baseline and LLM-assisted extraction approaches.
- Demonstration of schema validation, source provenance, uncertainty handling, and human-review routing.
- Local exploration of structured search after extraction quality has been evaluated.

## Out-of-scope use

- Unsupervised use for legal, financial, medical, employment, compliance, or safety-critical decisions.
- Treating extracted records as authoritative without checking their evidence and review status.
- Processing secrets, personal mailboxes, confidential business documents, or regulated data.
- Production-scale ingestion, high-availability serving, or enterprise access control.

## Initial success criteria

These are design targets, not achieved results. Quantitative thresholds will be fixed in the evaluation plan before model experiments begin.

- Supported documents can be represented without losing the page, slide, or section identity needed for evidence links.
- The extraction contract is explicit, versioned, and automatically schema-validated.
- A deterministic baseline and one future LLM approach can be evaluated on the same labelled examples.
- Evaluation reports field-level extraction quality, schema validity, evidence alignment, and review-routing behaviour rather than one aggregate score alone.
- Unsupported, conflicting, and ambiguous cases are surfaced for review according to documented rules.
- Tests and mock-mode workflows run locally without network access or real credentials.

## Main scope risks

- **Format sprawl:** three MVP formats may still create too much parser work before evaluation begins.
- **Schema drift:** an overly broad project-intelligence schema could make annotation and comparison unreliable.
- **Evidence ambiguity:** source locations may not be sufficient when a claim depends on several distant passages.
- **Evaluation leakage:** synthetic cases or prompt iteration could unintentionally overfit a small benchmark.
- **Provider variance:** results from one future LLM provider may not generalise across models or versions.
- **Review design:** routing everything to humans would be safe but unhelpful; routing too little would hide uncertainty.
- **Demo pressure:** retrieval or cloud features could distract from measuring extraction quality.
