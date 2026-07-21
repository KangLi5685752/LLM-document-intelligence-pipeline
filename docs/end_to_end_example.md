# End-to-End Product Example

This example uses development sources S010 and S012-S014 only.

## Scenario

An analyst uploads:

- the Northstar portfolio deck;
- the three-message Atlas migration email thread.

The analyst wants a consolidated view that distinguishes current facts from superseded values while preserving slide, message-body, and quoted-history evidence.

## Expected processing stages

1. Register each source and its family.
2. Parse PPTX and EML with format-specific provenance.
3. Create common Document Objects.
4. Identify candidate facts.
5. Normalize dates, money, status values, and names.
6. Link each candidate to source evidence.
7. Reconcile duplicates and temporal changes.
8. Produce final structured knowledge.
9. Route unresolved or unsupported items for review.
10. Later expose validated records through an interface or query layer.

These are expected future stages, not implemented behavior.

## Northstar example

Current:

- status: Green;
- owner: Emma Clarke;
- approved budget: GBP 1.35 million;
- target launch: 2026-12-15;
- reporting date: 2026-07-15.

Superseded:

- status: Amber;
- owner: Alex Morgan;
- budget: GBP 1.20 million;
- target launch: 2026-11-30.

Relevant evidence includes S010 slide 2, slide 6, and slide 7.

## Atlas example

Current:

- status: Green;
- owner: Daniel Reed;
- approved budget: GBP 480,000;
- target migration date: 2026-10-15.

Superseded:

- status: Amber;
- owner: Priya Shah;
- proposed budget: GBP 450,000;
- target migration date: 2026-09-30.

Relevant evidence includes the S012 body, S013 body and quoted history, and S014 body and quoted history.

## Example output

**Illustrative expected output – not an implemented or measured system result.**

~~~json
{
  "schema_version": "0.1",
  "batch_id": "example-development-batch",
  "source_documents": [
    {
      "source_id": "S010",
      "document_family": "F-SYN-001",
      "source_format": "PPTX",
      "filename": "S010_northstar_portfolio_update.pptx",
      "split": "development",
      "parse_status": "illustrative_expected_success"
    },
    {
      "source_id": "S012",
      "document_family": "F-SYN-003",
      "source_format": "EML",
      "filename": "S012_atlas_migration_01.eml",
      "split": "development",
      "parse_status": "illustrative_expected_success"
    },
    {
      "source_id": "S013",
      "document_family": "F-SYN-003",
      "source_format": "EML",
      "filename": "S013_atlas_migration_02.eml",
      "split": "development",
      "parse_status": "illustrative_expected_success"
    },
    {
      "source_id": "S014",
      "document_family": "F-SYN-003",
      "source_format": "EML",
      "filename": "S014_atlas_migration_03.eml",
      "split": "development",
      "parse_status": "illustrative_expected_success"
    }
  ],
  "entities": [
    {
      "entity_id": "ENT-NORTHSTAR",
      "canonical_name": "Northstar Programme",
      "entity_type": "programme",
      "aliases": [],
      "source_ids": ["S010"]
    },
    {
      "entity_id": "ENT-ATLAS",
      "canonical_name": "Atlas migration",
      "entity_type": "initiative",
      "aliases": [],
      "source_ids": ["S012", "S013", "S014"]
    }
  ],
  "facts": {
    "records": [
      {
        "fact_id": "FACT-NORTHSTAR-BUDGET-CURRENT",
        "subject_id": "ENT-NORTHSTAR",
        "predicate": "approved_budget",
        "raw_value": "GBP 1.35 million",
        "normalized_value": {"amount": 1350000, "currency": "GBP"},
        "value_type": "money",
        "fact_state": "current",
        "evidence_ids": ["EV-S010-2"]
      },
      {
        "fact_id": "FACT-NORTHSTAR-BUDGET-DUPLICATE",
        "subject_id": "ENT-NORTHSTAR",
        "predicate": "approved_budget",
        "raw_value": "GBP 1.35 million",
        "normalized_value": {"amount": 1350000, "currency": "GBP"},
        "value_type": "money",
        "fact_state": "duplicate",
        "duplicate_of_fact_id": "FACT-NORTHSTAR-BUDGET-CURRENT",
        "evidence_ids": ["EV-S010-6"]
      },
      {
        "fact_id": "FACT-NORTHSTAR-BUDGET-OLD",
        "subject_id": "ENT-NORTHSTAR",
        "predicate": "approved_budget",
        "raw_value": "GBP 1.20 million",
        "normalized_value": {"amount": 1200000, "currency": "GBP"},
        "value_type": "money",
        "fact_state": "superseded",
        "superseded_by_fact_id": "FACT-NORTHSTAR-BUDGET-CURRENT",
        "evidence_ids": ["EV-S010-6", "EV-S010-7"]
      },
      {
        "fact_id": "FACT-ATLAS-STATUS-CURRENT",
        "subject_id": "ENT-ATLAS",
        "predicate": "project_status",
        "raw_value": "Green",
        "normalized_value": "Green",
        "value_type": "status",
        "fact_state": "current",
        "evidence_ids": ["EV-S014-BODY"]
      },
      {
        "fact_id": "FACT-ATLAS-STATUS-OLD",
        "subject_id": "ENT-ATLAS",
        "predicate": "project_status",
        "raw_value": "Amber",
        "normalized_value": "Amber",
        "value_type": "status",
        "fact_state": "superseded",
        "superseded_by_fact_id": "FACT-ATLAS-STATUS-CURRENT",
        "evidence_ids": ["EV-S012-BODY", "EV-S014-HISTORY"]
      }
    ],
    "evidence_references": [
      {
        "evidence_id": "EV-S010-2",
        "source_id": "S010",
        "location_type": "slide",
        "location_value": "2",
        "text_excerpt": "Approved budget: GBP 1.35 million"
      },
      {
        "evidence_id": "EV-S010-6",
        "source_id": "S010",
        "location_type": "slide",
        "location_value": "6",
        "text_excerpt": "Budget changed from GBP 1.20 million to GBP 1.35 million"
      },
      {
        "evidence_id": "EV-S010-7",
        "source_id": "S010",
        "location_type": "slide",
        "location_value": "7",
        "text_excerpt": "SUPERSEDED"
      },
      {
        "evidence_id": "EV-S012-BODY",
        "source_id": "S012",
        "location_type": "email_body",
        "location_value": "body",
        "text_excerpt": "Status: Amber"
      },
      {
        "evidence_id": "EV-S014-BODY",
        "source_id": "S014",
        "location_type": "email_body",
        "location_value": "body",
        "text_excerpt": "Status: Green"
      },
      {
        "evidence_id": "EV-S014-HISTORY",
        "source_id": "S014",
        "location_type": "quoted_history",
        "location_value": "quoted_history",
        "text_excerpt": "Initial update: status Amber"
      }
    ]
  },
  "conflicts": [],
  "duplicate_groups": [
    {
      "duplicate_group_id": "DUP-NORTHSTAR-BUDGET",
      "canonical_fact_id": "FACT-NORTHSTAR-BUDGET-CURRENT",
      "duplicate_fact_ids": ["FACT-NORTHSTAR-BUDGET-DUPLICATE"],
      "evidence_ids": ["EV-S010-2", "EV-S010-6"]
    }
  ],
  "review_items": [],
  "processing_summary": {
    "source_count": 4,
    "current_fact_examples": 2,
    "superseded_fact_examples": 2,
    "unresolved_conflict_count": 0,
    "note": "Illustrative subset only"
  },
  "run_metadata": {
    "status": "planned"
  }
}
~~~

## User-facing view

This conceptual view does not currently exist.

| Initiative | Status | Owner | Approved budget | Target date | Unresolved conflict count |
| --- | --- | --- | ---: | --- | ---: |
| Northstar Programme | Green | Emma Clarke | GBP 1.35 million | 2026-12-15 | 0 |
| Atlas migration | Green | Daniel Reed | GBP 480,000 | 2026-10-15 | 0 |

## Later question example

**Question:** What is the current approved budget for Northstar, and which previous value was superseded?

**Expected evidence-grounded answer:** The current approved budget is GBP 1.35 million, supported by S010 slides 2 and 6. It supersedes GBP 1.20 million, shown as the previous value on slide 6 and in the superseded snapshot on slide 7.

Grounded RAG is planned only after extraction evaluation.
