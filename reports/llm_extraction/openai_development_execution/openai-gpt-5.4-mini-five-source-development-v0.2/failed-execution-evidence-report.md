# Stage 4D bounded development execution v0.2 failed-evidence report

## Closure status

- **Execution ID:** `openai-gpt-5.4-mini-five-source-development-execution-v0.2`
- **Status:** closed after deterministic local validation failure
- **Evidence review date:** 2026-08-10
- **Final execution record:** absent
- **Held-out access:** 0

This report closes the real bounded Stage 4D v0.2 development execution as
immutable failed-execution evidence. It is a sanitized summary, not a candidate
output, an evaluation result, a repaired response or authorization to rerun.

## Attempted invocation

- **Invocation order:** 1
- **Request ID:** `llm-v0.2-S001-primary-001`
- **Source ID:** `S001`
- **Attempt timestamp:** `2026-08-10T12:56:51.145280Z`
- **Failure-record timestamp:** `2026-08-10T12:56:56.666165Z`
- **Provider call occurred:** `true`
- **Cache installation completed:** `true`
- **Cache present:** `true`
- **Local parsing started:** `true`
- **Local parsing completed:** `false`
- **Retry count:** 0

Invocation 1 consumed exactly one provider call. Its terminal provider response
was installed in the immutable cache before deterministic local candidate
validation began. This report does not inspect or reproduce the cached response.

## Immutable artifact identities

### Attempt marker

- **Path:**
  `attempts/2E6E0E6234CDCE1AA93C8E40E45B654F9FE3D0AB5BBAAEFA62809A05389A88AC.attempt.json`
- **Cache identity:**
  `2E6E0E6234CDCE1AA93C8E40E45B654F9FE3D0AB5BBAAEFA62809A05389A88AC`
- **Execution-plan SHA-256:**
  `25588680A1362AC0192A378CD54288AA2DF5584F4C6108E3467BA06DA68AACE9`
- **Manifest SHA-256:**
  `16D9524377677F271CE7C33880B3E69E11A0157491FC8218A7666F8C5577D35C`
- **Authorization SHA-256:**
  `3FB00AEDFA675DB1CD3334F621F2C5D3159FA01D72C9D1CFB37D4EEF34F4837B`
- **Canonical marker SHA-256 field:**
  `FAE215AE081E1127FBD6C065A3B6856B8F34CE1519A7FB6D167B3BA38D51650A`

### Failure record

- **Path:**
  `failures/2E6E0E6234CDCE1AA93C8E40E45B654F9FE3D0AB5BBAAEFA62809A05389A88AC.failure.json`
- **Canonical failure-record SHA-256 field:**
  `843624B5D75FE6A305A406F8CD5CDB4A4F38DBE4124B9A0891DFB47CEE682F0C`
- **Attempt-marker SHA-256:**
  `FAE215AE081E1127FBD6C065A3B6856B8F34CE1519A7FB6D167B3BA38D51650A`
- **Failure stage:** `local_parse`
- **Local error code:** `schema_invalid`
- **Cache present:** `true`
- **Provider call occurred:** `true`
- **Cache installation completed:** `true`
- **Local parsing started:** `true`
- **Local parsing completed:** `false`
- **Retry count:** 0

The production v0.2 loaders validated both records, their canonical self-hashes
and their shared execution, plan, manifest, authorization, invocation, request,
cache and attempt-marker identities. Both files retain canonical LF bytes.

## Sanitized deterministic validation finding

- **Location:** `entities.0`
- **Message:** `Value error, alias cannot equal canonical_name after casefold`

The v0.2 prompt already required genuine alternative aliases, prohibited an
alias equal to `canonical_name` after Unicode casefold, required aliases to be
unique after casefold and instructed a semantic self-check. The returned entity
still violated that local `CandidateEntity` invariant.

## Offline counterfactual diagnostic

The separate read-only diagnostic recorded one entity, one alias, one
canonical-name conflict and zero duplicate-alias conflicts. Hypothetically
removing only that conflicting alias caused the complete
`CandidateExtractionResult` plus allowed-evidence validation to pass, with one
diagnostic-only alias removal and zero remaining errors.

That counterfactual was diagnostic only: it performed zero provider calls and
zero filesystem writes. The cached response was not repaired, mutated,
normalized, rewritten or converted into a valid result.

## Stop boundary and classification

The transaction stopped after invocation 1. Invocations 2 through 8 were not
attempted, and no final execution record exists. No LLM-versus-deterministic
evaluation exists from v0.2.

This is not classified as a provider transport failure. The call returned and
the cache installation completed; deterministic application-level validation
then failed closed on the alias/canonical-name casefold invariant.

## Immutable-artifact policy and recovery boundary

The attempt marker, failure record and cache are immutable historical evidence.
They must not be edited, repaired, normalized, replaced, reserialized or given a
retroactive successful outcome. The cache remains evidence of the original call
and must not be opened or reused as a valid candidate result.

**The v0.2 bounded development execution MUST NOT be rerun.**

PR #49 merged an additive v0.3 provider contract at
`c84ed618593c098b1d9ebf9bf383bc4af02b2002`. Its provider-facing strict schema
keeps `aliases` required but constrains the array with `maxItems: 0`. This
closure does not implement or authorize a v0.3 manifest, execution plan,
transaction or call, and no real v0.3 bounded development execution has
occurred.
