# Stage 4D v0.2 semantic-contract coverage audit

## Scope and conclusion

This audit records why the real bounded OpenAI development execution v0.2 is a
failed historical observation and why the next recovery boundary is additive
v0.3 provider-schema enforcement. It does not reproduce model output, inspect a
provider cache, evaluate extraction quality or authorize another call.

The observed evidence shows that prompt-only semantic enforcement was
insufficient for the alias/canonical-name conflict. The local
`CandidateEntity` validator behaved correctly and must remain unchanged.

## V0.1 coverage gap

The v0.1 real execution failed because one entity alias equalled its
`canonical_name` after Unicode casefold. The v0.1 prompt did not state that
cross-field semantic constraint. The desired Unicode casefold comparison
between two output fields was also not represented at the strict provider JSON
Schema boundary.

The local validator therefore supplied the authoritative fail-closed boundary:
it rejected the response after the provider call had completed and the response
had been cached.

## V0.2 prompt coverage and observed result

V0.2 added the missing semantic coverage explicitly. Its prompt required that:

- aliases are genuine alternative names;
- an alias never repeats `canonical_name`, including a Unicode casefold
  equivalent;
- aliases are unique after casefold; and
- the model performs a semantic self-check before emitting JSON.

The real v0.2 response nevertheless contained one entity with one alias equal to
its canonical name after casefold. Deterministic local parsing failed at
`entities.0` with `schema_invalid` and the sanitized message
`Value error, alias cannot equal canonical_name after casefold`.

The exact same application-level invariant therefore blocked both real
versions. For this observed failure class, prompt-only enforcement is
empirically insufficient even when the instruction and self-check are explicit.

## Local validation remains authoritative

`CandidateEntity` correctly supports genuine aliases while rejecting aliases
that equal the canonical name after casefold and duplicates after casefold. The
validator detected the real semantic defect and prevented an invalid result
from entering downstream candidate processing.

The local contract must not be weakened, bypassed or reinterpreted as a repair
layer. `CandidateExtractionResult` schema 0.1 also remains unchanged.

## Counterfactual diagnostic boundary

The separate read-only diagnostic found:

- entity count: 1;
- total aliases: 1;
- canonical-alias conflicts: 1;
- duplicate-alias conflicts: 0;
- diagnostic-only aliases removed: 1; and
- remaining errors after that hypothetical removal: 0.

Removing only the conflicting alias in memory caused complete
`CandidateExtractionResult` plus allowed-evidence validation to pass. This
establishes that the conflict was the only observed blocker in the S001 v0.2
response; it does not establish broader extraction quality or correctness.

The diagnostic made zero provider calls and zero filesystem writes. It did not
repair, normalize, mutate, rewrite or recache the response and does not change
the historical failed outcome.

## Additive v0.3 structural boundary

Prompt-only repetition is not the recovery design. Additive v0.3 instead makes
the observed provider-generated alias state structurally unavailable at the
strict Structured Outputs boundary:

- `aliases` remains a required array;
- the provider-facing v0.3 schema sets `maxItems: 0`; and
- provider-generated entities must therefore emit `aliases` as `[]`.

This deliberately defers provider-generated alternative-name extraction. The
local `CandidateEntity` contract remains unchanged and continues to accept valid
aliases from other producers.

The additive v0.3 provider contract was merged in PR #49 at
`c84ed618593c098b1d9ebf9bf383bc4af02b2002`. No v0.3 bounded-development
manifest, execution plan, transaction, authorization or real provider execution
exists yet. Those are separate future review boundaries.

## Closure decision

The v0.2 attempt marker, failure record and cache remain immutable evidence.
V0.2 must not be rerun, repaired or assigned a retroactive successful outcome.
No LLM-versus-deterministic evaluation exists from this incomplete execution,
and held-out access remained zero.
