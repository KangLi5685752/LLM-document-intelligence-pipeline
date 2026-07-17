# Source Manifests

## Purpose

The source register is the audit trail for corpus candidates. It records provenance, scope, licence-review state, data risks, local-file handling, and corpus decisions without committing the source documents themselves. One row represents one identifiable source version.

The initial rows are metadata-only candidates or deferred sources. They are not an approved evaluation corpus.

## Fields completed before download

Record the following from the authoritative landing page before any download:

- source ID, title, publisher, landing-page URL, source format, and publication date;
- access date, planned document role, domain, and language;
- any visible licence name or evidence without inferring missing terms;
- initial licence-verification status, third-party-material risk, and personal-data risk;
- redistribution decision, corpus status, exclusion reason, and notes.

A direct-file URL should be added only after it has been manually verified. A page or slide count copied from authoritative metadata may be recorded provisionally, but it must be checked against the acquired file before approval.

## Fields completed after download and inspection

When a source is approved for local acquisition, complete or confirm:

- direct-file URL and access date;
- page or slide count and local filename;
- SHA-256 checksum for the exact local file;
- licence name, licence evidence, verification status, and copyright owner;
- third-party-material and personal-data findings;
- redistribution and derived-text decisions;
- final corpus status, exclusion reason when applicable, and review notes.

Blank fields mean not yet verified; they must not be interpreted as approval or absence of risk.

## Local files

Downloaded source files belong under `data/raw/`. That directory is local and ignored by Git. Do not commit source binaries merely because they are publicly accessible. Follow the project licence policy and record an explicit redistribution decision first.

## Updating source status

1. Add a source as `candidate` when it is identified for review.
2. Record review findings in the same row and preserve the stable source ID.
3. Change the status to `approved` only after scope, licence, data-risk, and technical checks are complete for the intended use.
4. Use `deferred` when a known dependency prevents review or use, and record the reason.
5. Use `rejected` when the source is excluded, and preserve the exclusion reason for auditability.
6. Revisit the row when the publisher updates, withdraws, or supersedes the source.

**Candidate does not mean approved.** Contributors must not use candidate rows as evaluation inputs until their status and intended-use decisions have been reviewed.
