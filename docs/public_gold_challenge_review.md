# Public Gold Challenge-Case Review

Project-owner review was completed on 2026-07-22 for all six challenge cases. Five were approved without correction and one was corrected before approval. All final cases are `owner_verified`.

## 1. PGC-V01-S001-001

- Case ID: PGC-V01-S001-001
- Source: S001
- Page: 15
- Case type: `missing_expected_value`
- Description: The annual-publication requirement does not state an effective start date on the evidence page.
- Expected behavior: `preserve_missing`
- Owner decision: Approve without correction
- Final review status: `owner_verified`
- Final notes: Owner verified on 2026-07-22 against the original PDF page and ParsedDocument evidence; no semantic field correction was required. Annual frequency is present, but no effective start date or first reporting deadline is supplied.
- [x] Evidence verified
- [x] Case type verified
- [x] Expected behavior verified
- [x] Approve
- [ ] Reject

## 2. PGC-V01-S004-001

- Case ID: PGC-V01-S004-001
- Source: S004
- Page: 110
- Case type: `unsupported`
- Description: A contributed case study describes an implementation; it must not be generalized into a government-wide finding or policy claim.
- Expected behavior: `do_not_extract`
- Owner decision: Approve without correction
- Final review status: `owner_verified`
- Final notes: Owner verified on 2026-07-22 against the original PDF page and ParsedDocument evidence; no semantic field correction was required. Page 110 supports narrowly attributed Digital Sensitivity Review project facts, but not government-wide policy, implementation or performance claims.
- [x] Evidence verified
- [x] Case type verified
- [x] Expected behavior verified
- [x] Approve
- [ ] Reject

## 3. PGC-V01-S005-001

- Case ID: PGC-V01-S005-001
- Source: S005
- Page: 50
- Case type: `ambiguous`
- Description: The page contains a multi-row risk-and-mitigation table. In page-level ParsedDocument text, the row association between each risk and its corresponding mitigating outcome may not be reliably preserved.
- Expected behavior: `route_to_review`
- Owner decision: Correct before approval
- Final review status: `owner_verified`
- Final notes: Owner verified on 2026-07-22 against the original PDF page and ParsedDocument evidence; the description was corrected to identify flattened page-text row-association ambiguity rather than ambiguity in the visually structured original table. Individual risk statements or mitigating outcomes may be extracted independently when supported, but a risk-to-mitigation relationship must be routed to review unless the row association is explicitly recoverable from the parsed evidence.
- [x] Evidence verified
- [x] Case type verified
- [x] Expected behavior verified
- [x] Approve
- [ ] Reject

## 4. PGC-V01-S005-002

- Case ID: PGC-V01-S005-002
- Source: S005
- Page: 30
- Case type: `unsupported`
- Description: A third-party global survey statistic is contextual evidence and must not be represented as the publisher's own Scotland-specific finding.
- Expected behavior: `do_not_extract`
- Owner decision: Approve without correction
- Final review status: `owner_verified`
- Final notes: Owner verified on 2026-07-22 against the original PDF page and ParsedDocument evidence; no semantic field correction was required. The 71% statistic is attributed to a McKinsey global survey and must not be represented as a Scottish Government or Scotland-specific finding.
- [x] Evidence verified
- [x] Case type verified
- [x] Expected behavior verified
- [x] Approve
- [ ] Reject

## 5. PGC-V01-S006-001

- Case ID: PGC-V01-S006-001
- Source: S006
- Page: 13
- Case type: `ambiguous`
- Description: The page presents several percentages for different adoption states, sectors and business sizes; a candidate without its population and measure is ambiguous.
- Expected behavior: `route_to_review`
- Owner decision: Approve without correction
- Final review status: `owner_verified`
- Final notes: Owner verified on 2026-07-22 against the original PDF page and ParsedDocument evidence; no semantic field correction was required. Page 13 contains multiple percentages with different measures and populations, so a candidate lacking those qualifiers must be routed to review.
- [x] Evidence verified
- [x] Case type verified
- [x] Expected behavior verified
- [x] Approve
- [ ] Reject

## 6. PGC-V01-S007-001

- Case ID: PGC-V01-S007-001
- Source: S007
- Page: 8
- Case type: `missing_expected_value`
- Description: The regulatory-assurance-body recommendation does not state an implementation date on the evidence page.
- Expected behavior: `preserve_missing`
- Owner decision: Approve without correction
- Final review status: `owner_verified`
- Final notes: Owner verified on 2026-07-22 against the original PDF page and ParsedDocument evidence; no semantic field correction was required. 'Act swiftly' communicates urgency but is not an implementation date, deadline or target period.
- [x] Evidence verified
- [x] Case type verified
- [x] Expected behavior verified
- [x] Approve
- [ ] Reject
