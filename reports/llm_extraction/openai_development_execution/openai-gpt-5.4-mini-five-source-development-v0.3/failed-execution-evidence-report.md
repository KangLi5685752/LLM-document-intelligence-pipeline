# Stage 4D bounded development execution v0.3 failed-evidence report

## Closure status

- **Execution ID:** `openai-gpt-5.4-mini-five-source-development-execution-v0.3`
- **Status:** closed after deterministic local evidence-grounding validation failure
- **Evidence review date:** 2026-08-11
- **Final execution record:** absent
- **Held-out access:** 0

This report closes the real bounded Stage 4D development-v0.3 execution as immutable failed-execution evidence. It is a sanitized summary, not a candidate output, evaluation result, repaired response or authorization to rerun the transaction.

## Attempted invocation

- **Invocation order:** 1
- **Request ID:** `llm-v0.3-S001-primary-001`
- **Source ID:** `S001`
- **Cache identity:** `34E53A8295541C7052D78414C6D8302CC659039642A510E1613C19D7A83E0511`
- **Attempt timestamp:** `2026-08-10T22:47:41.933132Z`
- **Original provider/cache timestamp:** `2026-08-10T22:47:48.952695Z`
- **Failure-record timestamp:** `2026-08-10T22:47:48.987826Z`
- **Provider:** OpenAI Responses API
- **Provider terminal status:** `success`
- **Returned model identifier:** `gpt-5.4-mini-2026-03-17`
- **Provider SDK version:** `2.46.0`
- **Provider calls:** 1
- **Provider attempts:** 1
- **Input tokens:** 21,174
- **Output tokens:** 908
- **Latency:** 6,878 ms
- **Estimated newly incurred cost:** USD 0.0199665
- **Retry count:** 0

Invocation 1 consumed exactly one authorized provider attempt. Provider transport completed successfully, and the immutable cache record was installed and verified before deterministic local validation began. The transaction then stopped; invocations 2 through 8 were not attempted.

## Immutable repository artifact identities

### Attempt marker

- **Path:** `attempts/34E53A8295541C7052D78414C6D8302CC659039642A510E1613C19D7A83E0511.attempt.json`
- **Outer SHA-256:** `E64BE65A29D121B83597344C7032C91DBB79D62FB84D2EBB78EE7411D4B40CA2`
- **Canonical marker self-hash:** `945DB923A5294C75A4642C609ABBEB94AB50E6B78482B1338EF11723F7757B3B`
- **Execution-plan self-hash:** `12191955D5ED1F6EBF0B0BC97AA6A2EF11B164186645FD68D6270D8A241A0F0A`
- **Manifest self-hash:** `D1044BA06EEDF235AFEDC23826F4ABFA385494ACFBD8F6D99453FB8ED5C0E327`
- **Authorization self-hash:** `F4A0344041DCE64AFE5B75C7953EF6784E87D6BE468FE367E628EFCD8B74B3EE`

### Failure record

- **Path:** `failures/34E53A8295541C7052D78414C6D8302CC659039642A510E1613C19D7A83E0511.failure.json`
- **Outer SHA-256:** `D4B94C6FD407690B59D4A015F9A2B4877FFF38CCC5CCE1559D397D658AF1A6BD`
- **Canonical failure-record self-hash:** `3D6FF1E25D52FB579F48284839292CB97CE2787CC9F2CA75B5ED070E2CB4F8F1`
- **Attempt-marker self-hash:** `945DB923A5294C75A4642C609ABBEB94AB50E6B78482B1338EF11723F7757B3B`
- **Failure stage:** `local_parse`
- **Local error code:** `unknown_evidence_reference`
- **Provider call occurred:** `true`
- **Cache present:** `true`
- **Cache installation completed:** `true`
- **Local parsing started:** `true`
- **Local parsing completed:** `false`
- **Retry count:** 0

The production v0.3 loaders validated both repository records, their canonical self-hashes and their shared execution, plan, manifest, authorization, invocation, request, cache and attempt-marker identities.

## Immutable local cache identity

The provider cache remains local, append-only, untracked and immutable. It is not copied, opened, reproduced, normalized or reserialized by this repository report. Only the reviewed identities are recorded:

- **Cache-file outer SHA-256:** `F23E8FF0383321266FD2FB13D0B7CB850DCBF0FA41CD783ABEDC1700514E3CD3`
- **Cache-record canonical self-hash:** `D4C05B4B37E34D338CD44AB309E83DDC86AA8AE5A3B07ED09F152BB53266070A`
- **Raw provider-response SHA-256:** `36308CC0572295F1FF4EE7480FB0FE02632558E4744197FBCB5554B3C9F12F7A`
- **Provider request ID:** `req_ce0da46ac0914251a4f6c72744694d89`
- **Provider response ID:** `resp_0e329a99cc0435aa016a7a5510d1d08192a70f88fb57681d3d`
- **Model-version or snapshot provenance:** `unavailable`
- **Same-call public metadata SHA-256:** `9B1C4E710F1397E76E2E3C3FE8193C45A72F5867D52BF0B7626DD7A975164EF5`
- **Cache installation:** completed and verified before local validation

Neither the raw cached response nor source text is reproduced in this report.

## Sanitized deterministic validation finding

The returned output satisfied the `CandidateExtractionResult` schema `0.1` structural contract before supplied-evidence provenance validation. The validated structure contained three candidate facts and six evidence references. Aliases were correctly empty; every returned evidence ID was supplied in the request, and every returned block ID corresponded to a supplied block.

All three candidate facts referenced only `llm-evidence-v0.3-S001-DOC-S001-B0002`, whose returned evidence reference retained the exact approved provenance. Two unused evidence references had incorrect `location_value` fields:

1. `llm-evidence-v0.3-S001-DOC-S001-B0008`, block `DOC-S001-B0008`: returned `7`; approved request value `8`.
2. `llm-evidence-v0.3-S001-DOC-S001-B0022`, block `DOC-S001-B0022`: returned `21`; approved request value `22`.

The returned values `7` and `21` correspond to page numbers visible in document text. The approved immutable provenance values `8` and `22` are the physical one-based PDF page locations supplied by the request.

This is conservatively classified as **provider semantic provenance drift**: the model appears to have substituted visible document page numbering for supplied immutable location metadata on two unused evidence references.

It is not classified as parser corruption, manifest corruption, routing failure, identifier fabrication, OpenAI transport failure, transaction failure or validator failure. The deterministic validator was correct to fail closed.

## Offline counterfactual diagnostic

In a separate offline diagnostic, changing only the two returned location values (B0008 from `7` to `8` and B0022 from `21` to `22`) while retaining every other returned field caused:

- `CandidateExtractionResult` model validation to pass;
- supplied-evidence provenance validation to pass; and
- the remaining provenance-error count to equal 0.

This was diagnostic only and is not a repair. The original cached response remains immutable and invalid. No retroactive successful result exists.

## Stop boundary and recovery policy

The transaction stopped after invocation 1. Invocations 2 through 8 were not attempted, no final execution record exists, no successful five-source development result exists and no LLM-versus-deterministic evaluation exists from v0.3.

The v0.3 attempt marker is permanently consumed. The marker, failure record and provider cache are immutable historical evidence and must not be edited, repaired, normalized, replaced, reserialized or assigned a retroactive successful outcome. The cached response must not be changed, repaired or replaced.

**The development-v0.3 bounded execution MUST NOT be rerun.**

Any future recovery requires a new additive version, a separate reviewed design and fresh version-specific identities and authorization. This closure does not implement or authorize v0.4, any recovery transaction or any new provider call.
