# Project Status

- **Current stage:** Stage 1B - pilot source audit and audit automation design
- **Last updated:** 2026-07-19
- **Latest milestone:** Deterministic PDF audit utility validated against S001–S003 with matching hashes, sizes, and page counts
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0A project foundation.
- Stage 1A corpus strategy and licence register.
- Stage 1B audit protocol.
- Source and direct-file verification for S001–S003.
- Pilot technical audit for S001–S003.
- Integrity, page-count, text-extractability, document-structure, and licence-notice observations recorded.
- S001–S003 approved for documented local corpus and future evaluation use.
- Original source PDFs remain local and uncommitted.
- Deterministic batch PDF audit utility implemented.
- Unit tests added for hashing, sampling, scan-risk screening, PDF failures, CSV output, and CLI validation.
- Utility validated locally against S001–S003.
- Hashes, file sizes, and page counts reconciled with recorded evidence.

## In progress

- Preparing S004–S007 for batch acquisition and audit.
- Targeted manual licence review for S004–S007.
- Defining the synthetic challenge set.
- Planning future development and held-out document-family splits.

## Next tasks

1. Acquire S004–S007 from manually verified official URLs.
2. Run the batch audit utility over S001–S007.
3. Investigate only generated warnings and structural exceptions.
4. Complete targeted licence and third-party-material review for S004–S007.
5. Update the source and document-audit registers using observed evidence.
6. Design the synthetic PPTX and email-style challenge set.

## Blockers

No repository blocker is identified. S004–S007 remain candidates pending official-source verification, local acquisition, licence and risk review, and technical audit.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
