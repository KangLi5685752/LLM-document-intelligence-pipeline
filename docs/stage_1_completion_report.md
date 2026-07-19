# Stage 1 Corpus Audit and Freeze Report

## Scope completed

Stage 1 completed:

- source strategy;
- licence and redistribution policy;
- public-source register;
- exact-file audit;
- deterministic PDF audit utility;
- S001-S007 public-PDF review;
- synthetic PPTX and EML corpus;
- synthetic ground truth;
- family-level split;
- product contract;
- evaluation plan;
- corpus freeze.

## Corpus inventory

The `stage1-corpus-v1.0` split contains 15 active sources:

| Split | PDF | PPTX | EML | Total |
| --- | ---: | ---: | ---: | ---: |
| Development | 5 | 1 | 3 | 9 |
| Held-out | 2 | 1 | 3 | 6 |
| **Total** | **7** | **2** | **6** | **15** |

S008-S009 are deferred and excluded.

## Evidence and controls

- Official public-source URLs were verified and recorded.
- Exact-file SHA-256 values are recorded in `source_register.csv`.
- Original public PDFs remain local and uncommitted.
- Project-created synthetic files are committed.
- Open Government Licence and third-party-material caveats are recorded per public source.
- No confidential data is used.
- Synthetic messages contain no real email addresses.
- Synthetic PPTX files contain no external assets.
- Related documents and complete email threads use family-level leakage controls.

## Testing evidence

Verified evidence available before this documentation task:

- 32 local pytest tests reported passing;
- the deterministic PDF audit validated S001-S007;
- synthetic-generator determinism was tested;
- synthetic PPTX and EML structure was tested.

This is not described as CI; no GitHub Actions result is claimed.

## Remaining limitations

- No Stage 2 parser exists.
- No common Document Object is implemented.
- No extraction system is implemented.
- Public-PDF gold labels do not yet exist.
- No extraction metrics exist.
- The held-out set is procedural rather than blind.
- The project has one developer and annotator.
- The corpus is small.
- OCR is excluded.
- No production deployment exists.

## Stage 2 entry criteria

The Stage 2 entry criteria are satisfied at the planning and corpus-control level:

- the corpus is frozen;
- supported formats are fixed;
- source IDs and splits are fixed;
- the product contract exists;
- the extraction-schema design exists;
- evaluation gates exist.

The next work is the common Document Object and format-specific parsing.

## Claim boundary

The project may currently claim:

- an audited and versioned corpus;
- a deterministic corpus-quality utility;
- reproducible synthetic challenge fixtures;
- explicit ground truth and split controls;
- a documented product and evaluation contract.

It may not claim:

- extraction accuracy;
- parser coverage;
- LLM performance;
- conflict-detection accuracy;
- evidence-linking accuracy;
- RAG;
- cloud deployment;
- production readiness.
