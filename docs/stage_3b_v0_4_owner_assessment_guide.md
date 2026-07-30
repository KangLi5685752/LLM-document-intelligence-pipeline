# Stage 3B.5C v0.4 owner assessment guide

## Purpose

This package prepares the three frozen development challenge cases for formal project-owner review of `deterministic-baseline-v0.4`. The owner review is required because predefined structural checks cannot decide whether the observed output satisfies the intended qualitative behaviour in its source context.

The automated diagnostics recorded three structural passes. Those machine results are evidence only: they are not owner outcomes, do not complete the assessment, and do not authorize baseline finalization.

## Review materials

Preserve the tracked preparation files unchanged:

- `owner_challenge_review_packet.json` contains frozen case descriptions, bounded source evidence, every v0.4 candidate linked to each challenge block, resolved evidence, warnings, and the separate automated diagnostic.
- `owner_challenge_assessment_template.json` contains exactly three blank assessment rows. Every outcome and rationale is null.
- `owner_review_preparation_manifest.json` records fixed inventories, provenance, hashes, pending counts, and the held-out boundary.

For each case, inspect `frozen_description`, `challenge_source_evidence`, `evidence_linked_candidate_count`, `evidence_linked_candidates`, result and candidate warning codes, `automated_diagnostic`, and `owner_question`. Candidate evidence includes its actual locator and bounded excerpt. The automated diagnostic's `not_an_owner_outcome` field must remain true.

## Decisions required

The owner must independently answer these questions from the packet evidence:

1. `PGC-V01-S001-001` (`preserve_missing`): Does the v0.4 output avoid inventing an effective start date and preserve the absence of that value, without presenting an unrelated candidate as satisfying the missing-value requirement?
2. `PGC-V01-S004-001` (`do_not_extract`): Does the v0.4 output avoid extracting or generalizing the contributed case-study implementation into a government-wide finding, policy, requirement or commitment?
3. `PGC-V01-S006-001` (`route_to_review`): Are all ambiguous percentage relationships represented conservatively and routed to human review rather than accepted as unambiguous facts?

Codex must not answer these questions or populate owner decisions.

## Completing a later assessment

Do not edit the tracked blank template in place. Instead:

1. Copy it to an ignored working file.
2. Set every `outcome` to exactly `passed` or `failed`.
3. Add a specific, evidence-based `rationale` for all three cases. A minimum acceptable rationale identifies the inspected candidate or absence, the decisive evidence and warning or review state, and why those observations satisfy or fail the frozen expected behaviour.
4. Retain the exact experiment ID, case IDs, source IDs, expected behaviours, related candidate IDs, and warning codes.
5. Record the project owner identity through the later completed-assessment schema.
6. Provide the completed working file for independent validation and review.
7. Do not run a finalization transaction until the completed file has passed that independent review.

A later validator must reject missing rows, null outcomes, blank rationales, changed case metadata, unknown candidate or warning IDs, and non-owner assessment methods. This milestone deliberately does not create a completed assessment schema instance or a finalization command.

## Boundaries and limitations

Held-out ParsedDocuments and held-out semantics remain blocked. Preparation does not create a freeze manifest, finalize v0.4, authorize held-out access, or permit extraction tuning. Any later semantic extraction change requires a new baseline version.

The development gold set contains 25 deliberately sparse facts. Consequently, strict precision treats unmatched candidates as false positives for the frozen protocol, but it cannot establish that every unmatched candidate is a real semantic error. The owner challenge review must therefore remain separate from broad precision claims.
