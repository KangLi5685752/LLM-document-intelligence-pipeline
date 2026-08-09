# Stage 4D bounded development execution v0.1 failed-evidence report

## Closure status

- **Execution ID:** `openai-gpt-5.4-mini-five-source-development-execution-v0.1`
- **Status:** closed after deterministic local validation failure
- **Evidence review date:** 2026-08-10
- **Final execution record:** absent
- **Held-out access:** 0

This report closes the first real bounded Stage 4D development execution as an
immutable failed observation. It is a sanitized evidence summary, not a
candidate output, evaluation result or authorization to rerun the transaction.

## Attempted invocation

- **Invocation order:** 1
- **Request ID:** `llm-v0.1-S001-primary-001`
- **Source ID:** `S001`
- **Attempt timestamp:** `2026-08-09T14:58:15.880299Z`
- **Original provider-call timestamp:** `2026-08-09T14:58:25.066079Z`
- **Failure-record timestamp:** `2026-08-09T14:58:25.118582Z`
- **Provider:** OpenAI Responses API
- **Provider terminal status:** `success`
- **Returned model identifier:** `gpt-5.4-mini-2026-03-17`
- **Input tokens:** 20,921
- **Output tokens:** 638
- **Latency:** 9,015 ms
- **Estimated newly incurred cost:** USD 0.01856175
- **Retry count:** 0

Invocation 1 consumed exactly one real provider attempt. The response completed
successfully and its immutable cache record was installed and verified before
local candidate validation began.

## Immutable artifact identities

### Attempt marker

- **Path:**
  `attempts/F2B9349EAA71220ADABD9327DA085AF7C3AF65D0A5492496338F1D6E07A82393.attempt.json`
- **Cache identity:**
  `F2B9349EAA71220ADABD9327DA085AF7C3AF65D0A5492496338F1D6E07A82393`
- **Canonical marker SHA-256 field:**
  `8E3B7F2A54E1EA1619742220621C49D406A829E1C85F939676E3B792FFE57146`

### Cache record

- **Local append-only cache identity:**
  `F2B9349EAA71220ADABD9327DA085AF7C3AF65D0A5492496338F1D6E07A82393`
- **Cache-record SHA-256:**
  `8786F03E7B6D9DF25B1CCD28DA05B67E06A76A28E98C2F523B89333AF461FD55`
- **Raw provider-response SHA-256:**
  `79B43702125F3582B8CAAFBF5106C2DDEA0B9E7167A046106A0A303D5887E09F`
- **Cache installation:** successful and verified

The raw provider response is not reproduced, quoted, normalized or reserialized
in this report.

### Failure record

- **Path:**
  `failures/F2B9349EAA71220ADABD9327DA085AF7C3AF65D0A5492496338F1D6E07A82393.failure.json`
- **Canonical failure-record SHA-256 field:**
  `32502713BF6C58565DB9902E3CB2BCF77A9FE92BEE0FFD40E33D1347EFDDEBD7`
- **Failure stage:** `local_parse`
- **Local error code:** `schema_invalid`
- **Cache present:** `true`
- **Provider call occurred:** `true`
- **Cache installation completed:** `true`
- **Local parsing started:** `true`
- **Local parsing completed:** `false`

Sanitized deterministic validation finding:

- **Location:** `entities.0`
- **Message:** `Value error, alias cannot equal canonical_name after casefold`

## Stop boundary and classification

The transaction stopped immediately after invocation 1. Invocations 2 through
8 were not attempted: there are no corresponding attempt markers or failure
records. No final execution record exists.

This is not an OpenAI transport or API failure. The provider call succeeded,
the response was cached, and deterministic application-level validation then
rejected a schema-valid structured response because it violated a semantic
`CandidateEntity` invariant.

No LLM-versus-deterministic-baseline evaluation result exists from this run.

## Immutable-artifact policy

The v0.1 attempt marker, failure record and cache record are immutable historical
evidence. They must not be edited, repaired, normalized, replaced, reserialized
or assigned a retroactive successful outcome. The cached raw response must not
be copied into a new request identity or treated as a valid candidate result.

**The v0.1 bounded development execution MUST NOT be rerun.**

Any future recovery requires a new additive prompt/schema/request version, a
new reviewed manifest and execution plan, a new explicit authorization, new
cache and artifact identities, and a separately reviewed transaction. No such
recovery version is implemented or executed by this evidence closure.
