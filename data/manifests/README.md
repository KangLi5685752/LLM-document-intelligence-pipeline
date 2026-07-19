# Source Manifests

## Purpose

The source register is the audit trail for corpus candidates. It records provenance, scope, licence-review state, data risks, local-file handling, and corpus decisions without committing the source documents themselves. One row represents one identifiable source version.

The initial rows are metadata-only candidates or deferred sources. They are not an approved evaluation corpus.

## Source register and document audit

- **source_register.csv** records source provenance, publication metadata, licence state, data-risk state, redistribution decisions, and corpus decisions.
- **document_audit.csv** records integrity facts and technical observations for an exact locally acquired file, including its local filename, checksum, page count, structure, and extraction risks.
- **synthetic_ground_truth.jsonl** records one evaluation record per synthetic document family, including expected current facts, superseded facts, unresolved conflicts, duplicate groups, and evidence locations.

The files serve different control points: a document audit does not replace the source-level licence and corpus decision, and a source-register candidate does not imply that an exact file has been inspected. Blank audit fields mean not yet inspected, not “false”, “none”, or “passed”.

Synthetic ground truth is evaluation metadata and must not be passed into a source parser. `source_register.csv` remains the source-level provenance record for both public and synthetic sources.

Local filenames and hashes in document_audit.csv refer to files held under the Git-ignored local data/raw directory; they do not indicate that source binaries are committed. Related documents must share a stable related_source_group so they can be kept in the same future development or held-out evaluation split and reduce cross-document information leakage.

## Fields completed before download

Record the following from the authoritative landing page before any download:

- source ID, title, publisher, landing-page URL, source format, and publication date;
- access date, planned document role, domain, and language;
- any visible licence name or evidence without inferring missing terms;
- initial licence-verification status, third-party-material risk, and personal-data risk;
- redistribution decision, corpus status, exclusion reason, and notes.

A direct-file URL must be manually verified against an official source before local acquisition. After verification, a candidate may be acquired only into the Git-ignored local `data/raw/` directory for licence, structure, and technical audit. A page or slide count copied from authoritative metadata may be recorded provisionally, but it must be checked against the acquired file before approval.

## Fields completed after download and inspection

After a manually verified candidate is acquired locally for audit, complete or confirm:

- direct-file URL and access date;
- page or slide count and local filename;
- SHA-256 checksum for the exact local file;
- licence name, licence evidence, verification status, and copyright owner;
- third-party-material and personal-data findings;
- redistribution and derived-text decisions;
- final corpus status, exclusion reason when applicable, and review notes.

Blank fields mean not yet verified; they must not be interpreted as approval or absence of risk.

## Local files

Audit-only source files remain under `data/raw/`. That directory is local and ignored by Git, and original source files must not be committed. Local audit acquisition does not change `corpus_status` to `approved`. Approval requires completion of the documented scope, licence, risk, and technical checks. Follow the project licence policy and record an explicit redistribution decision before any broader handling.

## Updating source status

1. Add a source as `candidate` when it is identified for review.
2. Record review findings in the same row and preserve the stable source ID.
3. Change the status to `approved` only after scope, licence, data-risk, and technical checks are complete for the intended use.
4. Use `deferred` when a known dependency prevents review or use, and record the reason.
5. Use `rejected` when the source is excluded, and preserve the exclusion reason for auditability.
6. Revisit the row when the publisher updates, withdraws, or supersedes the source.

**Candidate does not mean approved.** Contributors must not use candidate rows as evaluation inputs until their status and intended-use decisions have been reviewed.
