# Project Status

- **Current stage:** Stage 1B - source verification and technical corpus audit setup
- **Last updated:** 2026-07-18
- **Latest milestone:** Stage 1A corpus strategy and licence register merged via PR #2
- **AG News replacement status:** Not yet eligible

## Completed

- Stage 0A project foundation merged via PR #1.
- Stage 1A corpus strategy, licence policy, source register, and local-audit workflow merged via PR #2.
- Defined the project purpose, portfolio boundary, intended use, and non-goals.
- Documented the planned high-level architecture without claiming implementation.
- Recorded the initial project decisions and trade-offs.
- Established minimal Python packaging with a deterministic smoke test.
- Added environment and ignore-file safeguards for local secrets and generated data.

## In progress

- Stage 1B manual audit protocol and pilot audit-record template for S001–S003.
- Pilot setup only; no source audit has started and no source is approved.

## Next tasks

1. Manually verify the S001–S003 direct PDF URLs.
2. Acquire the verified files locally under data/raw.
3. Record hashes, actual page counts, and structure observations.
4. Review document-level licence notices and third-party material.
5. Update the source and audit registers from observed evidence.

## Blockers

No repository blocker is identified. S001–S003 remain candidates until their official URLs, exact files, licence and rights evidence, content risks, and technical suitability have been manually reviewed.

## AG News replacement status

Not yet eligible. This repository replaces the portfolio slot previously associated with a standalone RAG project, but it should not be treated as an evaluated replacement until the document pipeline and its benchmark have been implemented and reported.
