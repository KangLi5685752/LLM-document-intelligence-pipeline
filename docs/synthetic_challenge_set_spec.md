# Stage 1B Synthetic Challenge-Set Specification

## Objectives

Controlled synthetic files complement the public-PDF corpus by providing exact ground truth, deliberate conflicts, deterministic evidence locations, PPTX and EML format coverage, safe redistribution, and an explicit development-versus-held-out separation.

## Challenge families

### Family F-SYN-001 – Northstar portfolio update

- **Source:** S010
- **Format:** PPTX
- **Provisional split:** development
- **Primary challenges:** Slide titles and sections; a project-status table; a process diagram; a risk register; repeated project metadata; an explicit superseded snapshot; and current facts that replace earlier facts.

### Family F-SYN-002 – Civic Assist steering pack

- **Source:** S011
- **Format:** PPTX
- **Provisional split:** held_out
- **Primary challenges:** Project aliases; a workflow diagram; a KPI table; a budget revision; an unresolved launch-date conflict; a risk matrix; and a decision summary.

### Family F-SYN-003 – Atlas migration email thread

- **Sources:** S012, S013, S014
- **Format:** EML
- **Provisional split:** development
- **Primary challenges:** A chronological reply chain; `In-Reply-To` and `References` headers; quoted history; signature noise; status changes; an owner change; an approved budget replacing a proposed budget; and a latest message that resolves earlier facts.

### Family F-SYN-004 – Harbour analytics email thread

- **Sources:** S015, S016, S017
- **Format:** EML
- **Provisional split:** held_out
- **Primary challenges:** Reply and forwarding structure; quoted content; a draft-versus-approved budget; a status change; an unresolved launch-date conflict; an open vendor risk; and a latest message that explicitly preserves uncertainty.

## Leakage controls

- All sources in one family must remain in one split.
- S012-S014 cannot be separated.
- S015-S017 cannot be separated.
- Held-out facts must not be copied into future parser rules or prompt examples.
- Split assignments remain provisional until the Stage 1 corpus freeze.

## Out of scope

This task does not implement PPTX ingestion, EML ingestion, extraction, schema validation, LLM calls, retrieval, RAG, or evaluation metrics.
