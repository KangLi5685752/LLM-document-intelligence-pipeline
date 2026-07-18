# Stage 1B Source Audit Protocol

## Purpose and pilot scope

This protocol defines a manual, evidence-based audit for the S001–S003 pilot source family. It separates official-source verification, local file integrity, licence and rights review, technical suitability, and corpus decisions. The protocol and template do not record completed audits: all three pilot audits start as not_started, and no source is approved through Stage 1B.

## A. Official-source verification

For each source:

1. Open the landing-page URL already recorded in the source register and confirm that it is an official publisher page.
2. Compare the displayed title, publisher, publication date, and intended document role with the register. Record discrepancies; do not silently overwrite them.
3. Manually click the official PDF link from the landing page.
4. Verify that the final file URL is hosted by the publisher or by an official publishing asset domain reached through that link.
5. Do not infer, construct, or fabricate a direct-file URL.
6. Record the final verified URL in the source register only after this check, and record the date checked in the audit record.

If the link cannot be verified, stop acquisition and leave the source and audit states unapproved.

## B. Local acquisition

After official-source verification:

1. Save the audit-only file under the Git-ignored local data/raw directory.
2. Use a stable source-ID-based filename, such as S001.pdf, without implying that the source is approved.
3. Do not commit the PDF or any other source binary.
4. Record the local filename only after the file exists locally.
5. Treat local acquisition as permission to perform the documented audit only. It does not change corpus_status to approved.

## C. File integrity

For the exact acquired file:

1. Verify that the PDF opens without an error.
2. Calculate and record its SHA-256 checksum.
3. Record its size in bytes.
4. Record the actual page count from the opened file.
5. Compare the actual file, page count, title, and version indicators with the landing-page metadata.
6. Record any mismatch and pause approval until it is resolved.

The checksum, file size, and local filename identify the ignored local audit copy; they are not evidence that a binary was committed.

## D. Licence and rights review

This review records observed evidence and project decisions; it is not legal advice.

1. Inspect the landing-page terms and record the authoritative location used.
2. Inspect the PDF copyright or licence page and record the licence name and evidence location exactly.
3. Check for “except where otherwise stated” or equivalent limitations.
4. Inspect third-party charts, photographs, logos, quotations, appendices, commissioned material, and credits.
5. Record personal-data observations without copying unnecessary personal information into the repository.
6. Distinguish the copyright owner, information provider, and third-party rights holders when the document does so.
7. Do not assume that a public document, a GOV.UK landing page, or an OGL reference makes every component redistributable.
8. Record unresolved questions and retain a review-required decision when evidence is incomplete.

## E. Technical document inspection

Inspect the beginning, middle, and end of the PDF and record the exact sample pages checked. Review:

- whether text can be selected;
- whether representative terms can be found with Ctrl+F;
- scanned-page or image-only risk;
- the presence and consistency of headings;
- tables and their structural complexity;
- figures, charts, captions, and image-based text;
- bullet lists;
- multi-column layouts;
- repeated headers and footers;
- printed versus PDF page-number consistency;
- empty or near-empty pages;
- material layout changes across the sampled pages.

Do not infer whole-document suitability from one page. Expand the sample when layouts vary or a risk is observed.

## F. Corpus and evaluation risks

- Record document-family relationships in related_source_group.
- Record whether a source supersedes, updates, responds to, or substantially repeats another source.
- Keep closely related documents in the same future development or held-out evaluation split to reduce cross-document information leakage.
- Distinguish technical suitability from licence approval: a technically extractable PDF may still be unusable for the intended corpus purpose.
- Distinguish local-use approval from redistribution approval: permission to audit or use a local file does not permit committing the original or derived text.
- Record unresolved version, scope, duplication, or leakage risks before making a recommendation.

## G. Decision rules

Use one of these values for technical_recommendation after the audit evidence has been recorded:

- **suitable_for_mvp:** the source is technically suitable for the MVP and no unresolved technical blocker is recorded.
- **suitable_with_caveats:** the source is usable only with documented limitations, preprocessing needs, sampling constraints, or evaluation caveats.
- **deferred:** the decision cannot be completed because evidence, format support, version resolution, or another dependency is outstanding.
- **rejected:** the source is unsuitable for the MVP under the documented scope or presents an unresolved blocker that is not proportionate to address.

A technical recommendation does not grant licence, local-use, redistribution, derived-text, or corpus approval. corpus_status may remain candidate until the complete scope, licence, risk, and technical review is finished and the source register is updated from observed evidence.

Use audit_status to track workflow state:

- **not_started:** only template metadata is present; no audit observation has been made.
- **in_progress:** manual verification or inspection has begun, but required fields remain incomplete.
- **complete:** all required protocol sections have been reviewed and evidence or explicit not-applicable findings are recorded.
- **blocked:** the audit cannot continue until a documented dependency is resolved.
