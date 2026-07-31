# Stage 3B.5D deterministic-baseline-v0.4 owner-assessment record

## Assessment identity

- Experiment ID: `deterministic-baseline-v0.4`
- Preparation merge commit: `36fe312ef07716a3597ea62a5d146a12b1c9312b`
- Owner identity: Kang Li
- Assessment method: `project_owner_review`
- Assessment status: completed
- Deterministic validation: passed
- Held-out status: blocked
- Baseline-freeze status: not created
- Independent read-only review: pending

The three owner outcomes below were supplied by the project owner. They are separate from the three automated structural diagnostics in the preparation packet; the diagnostics did not populate or determine the owner outcomes or rationales.

## PGC-V01-S001-001

- Source: `S001`
- Expected behavior: `preserve_missing`
- Outcome: `passed`
- Evidence-linked candidate count: 6
- Decisive evidence: recommendation 28 is a distinct candidate and retains no effective-start date, start year or deadline; the other page-linked recommendation IDs remain separate candidates.
- Owner rationale: Passed because recommendation 28 is represented as a separate recommendation requiring annual publication, while no effective start date, start year or deadline is added to the candidate or its qualifiers. The other five candidates linked to the same page retain distinct recommendation IDs and are not treated as supplying or satisfying the missing effective-start value.

## PGC-V01-S004-001

- Source: `S004`
- Expected behavior: `do_not_extract`
- Outcome: `passed`
- Evidence-linked candidate count: 0
- Decisive evidence: no candidate in the merged v0.4 packet resolves to the frozen contributed FCDO Services case-study challenge block.
- Owner rationale: Passed because no v0.4 candidate references the contributed FCDO Services case-study evidence block. The local implementation is therefore not extracted or generalized into a government-wide finding, policy, requirement or commitment.

## PGC-V01-S006-001

- Source: `S006`
- Expected behavior: `route_to_review`
- Outcome: `passed`
- Evidence-linked candidate count: 6
- Decisive evidence: all six linked metric candidates retain confidence 0.5, required human review, ambiguous resolved evidence and the `ambiguous_metric_value_relationship` warning.
- Owner rationale: Passed because all six percentage candidates linked to the challenge block are handled conservatively. Each uses confidence 0.5, has ambiguous evidence status, requires human review and carries the ambiguous_metric_value_relationship warning. None is accepted as an unambiguous population-and-measure fact.

## Validation evidence

- Completed-assessment SHA-256: `8B1BEE334AAE3A1F3AF6A5DF8B9FBC039FE9DB79BBA9CEC931BE019DA68D7419`
- Validation-report SHA-256: `D7940A01E30FF1F0B735CCE94504BC76A23F0EB1BF6454F6264D7D56ED557E94`
- Passed: 3
- Failed: 0
- Pending: 0
- Null outcomes: 0
- Null rationales: 0
- Candidate-reference reconciliation: passed
- Warning-reference reconciliation: passed
- Evidence-consistency validation: passed
- Owner-versus-machine separation: passed
- Held-out isolation: passed

The deterministic validator confirms structure, fixed metadata, preparation-package references and evidence consistency. It does not replace the project owner's qualitative judgment.

## Claim boundary

The 25-fact development gold set is deliberately sparse. Three successful challenge assessments do not establish exhaustive precision, overall extraction accuracy, production readiness or held-out readiness. The v0.4 baseline is not frozen or finalized, held-out execution remains unauthorized, and independent read-only review remains pending.
