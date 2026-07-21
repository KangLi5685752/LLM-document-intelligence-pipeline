# Stage 2 Document Ingestion Design

## Scope

Stage 2A implements a local, single-document ingestion boundary comprising:

- the versioned Common Document Object v0.1;
- strict Pydantic validation;
- deterministic document and block identifiers;
- PDF, PPTX, and plain-text EML parsing;
- source-location preservation;
- explicit warnings and structured errors;
- UTF-8 JSON serialisation;
- extension-based dispatch and a single-document CLI.

The output describes document structure and provenance. It does not interpret document statements as facts.

## Input and output example

~~~text
S010 PPTX
    -> ParsedDocument
    -> ordered slide-level DocumentBlock records
       - slide title
       - text shape
       - table
       - slide number and shape position
~~~

This is ingestion, not extraction. `ParsedDocument` and `DocumentBlock` records do not classify current facts, superseded facts, duplicates, entities, or conflicts.

## Common Document Object

`ParsedDocument` records:

- schema version and deterministic document ID;
- optional source ID;
- source format, filename, and uppercase SHA-256;
- title, date, and authors or senders when available;
- ordered `DocumentBlock` records;
- simple serialisable metadata;
- warnings and successful parse status.

Every block has a deterministic ID, a unique sequence, a block type, text, a source location, simple metadata, and warnings. Parsing failures use structured exceptions instead of successful documents with a failed status.

## Parser responsibilities

### PDF

- read with `PdfReader(..., strict=False)`;
- preserve one block per page in page order;
- retain 1-based page numbers;
- record simple PDF metadata and encryption state;
- keep blank pages as warned empty blocks;
- report unreadable or protected files as structured failures.

The parser does not run OCR, reconstruct columns, or infer tables.

### PPTX

- retain slide titles, non-empty text shapes, and tables;
- retain 1-based slide numbers and original shape indexes;
- order shapes by top, left, then original index;
- preserve shape geometry and group context;
- represent tables as tab-separated rows with row and column counts;
- summarise skipped non-text or unsupported visual objects.

The parser does not interpret pictures, charts, SmartArt, diagrams, embedded files, or external assets.

### EML

- decode supported message headers;
- retain Message-ID, reply, reference, recipient, and date metadata;
- create separate header, current-body, and quoted-history blocks;
- preserve plain-text multipart order;
- skip attachments and record warnings;
- reject messages without a readable `text/plain` body.

Separator-based history detection recognizes common original-message, forwarded-message, selected-history, `On ... wrote:`, and leading `>` forms. It does not infer whether any statement is current or superseded.

## Dispatcher and CLI

The dispatcher selects `.pdf`, `.pptx`, or `.eml` parsers case-insensitively from the filename suffix. It does not sniff arbitrary binary formats.

The CLI accepts one file and emits one `ParsedDocument` JSON document. It does not read the source register, corpus split, or synthetic ground truth, and it does not perform batch ingestion.

## Non-goals

- OCR or scanned-image interpretation;
- semantic table reconstruction;
- chart, image, SmartArt, or diagram interpretation;
- fact or entity extraction;
- current/superseded classification;
- reconciliation or conflict resolution;
- ground-truth scoring;
- LLM calls;
- retrieval or RAG;
- storage, API, UI, or cloud deployment.

## Determinism

- SHA-256 values are calculated from exact source bytes.
- A supplied source ID determines the document ID; otherwise the checksum prefix is used.
- Block IDs derive from the document ID and the 1-based block sequence.
- PDF page order, PPTX spatial order, EML header order, and multipart text order are stable.
- Identical source bytes and source ID should produce equivalent JSON with no environment-derived timestamps, paths, network values, or random identifiers.

## Warnings and errors

Readable documents may return `success` or `success_with_warnings`. Blank PDF pages, skipped PPTX visuals, missing EML Message-ID headers, and skipped attachments are explicit warnings. Missing, unsupported, malformed, unreadable, encrypted-without-access, or body-less inputs raise structured errors.

## Security and privacy

- Parsers read local files only.
- No macros, attachments, or embedded files are executed.
- External assets are not fetched.
- No network calls are made.
- Source bytes are not embedded in output JSON.
- The pipeline is not approved for confidential production data.

## Held-out protocol

- Stage 2A tests and content assertions use temporary fixtures plus development sources S010 and S012-S014 only.
- Held-out files are not used for parser-specific rules.
- Generic format support may be evaluated on the six frozen held-out sources in Stage 2B after the Stage 2A parser version is frozen.
- Any held-out failure must be recorded before a format-general correction is made.
