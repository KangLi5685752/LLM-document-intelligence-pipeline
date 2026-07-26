# Stage 3B deterministic-baseline-v0.2 Error Matrix

## Status and evidence boundary

This development-only analysis is frozen with the v0.2 plan. It uses the immutable v0.1 observation lock, unmatched inventory, owner-review packet, four published candidate outputs and the guarded 25-fact development load. It did not run extraction, inspect held-out semantics or create a score. S004 has no candidate output because v0.1 failed on that source.

Preliminary v0.1 counts remain 0 TP, 288 FP and 25 FN. They are diagnostics for planning, not an accepted benchmark.

## Candidate distribution

| Source | Candidates |
| --- | ---: |
| S001 | 72 |
| S002 | 100 |
| S003 | 37 |
| S004 | 0 (source attempt failed) |
| S006 | 79 |
| **Total published** | **288** |

| Predicate | Candidates |
| --- | ---: |
| `action_status` | 0 |
| `budget` | 0 |
| `commitment` | 243 |
| `decision` | 5 |
| `metric` | 25 |
| `recommendation` | 0 |
| `requirement` | 15 |
| `risk` | 0 |

| Subject type | Candidates |
| --- | ---: |
| `initiative` | 1 |
| `metric` | 25 |
| `organisation` | 37 |
| `other` | 216 |
| `policy` | 8 |
| `programme` | 1 |

| Value type | Candidates |
| --- | ---: |
| `percentage` | 25 |
| `string` | 263 |

| Confidence | Candidates |
| --- | ---: |
| `0.7` | 21 |
| `0.9` | 267 |

All 288 candidates have `review_status=not_required`; none has `review_status=required`. Candidate-level warning arrays are empty. Result-level warning frequencies are:

| Warning code | Frequency |
| --- | ---: |
| `abstained_ambiguous_relationship` | 1 |
| `abstained_missing_subject` | 544 |
| `abstained_multiple_values` | 65 |
| `abstained_unsupported_subject_type` | 1 |

The exact semantic duplicate calculation identifies 7 extra duplicates. The unmatched inventory marks 13 candidate rows as members of duplicate groups; 13 is a diagnostic-row count, not the number of extra candidates.

## Gold and matching distribution

| Predicate | Development gold | Candidates | TP | FP | FN | Strict match rate | Gold-side closest reason counts | Candidate-side closest reason counts |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `action_status` | 1 | 0 | 0 | 0 | 1 | 0/1 | `no_candidate_same_source_predicate`: 1 | none |
| `budget` | 2 | 0 | 0 | 0 | 2 | 0/2 | `no_candidate_same_source_predicate`: 2 | none |
| `commitment` | 5 | 243 | 0 | 243 | 5 | 0/5 | `no_strict_match`: 5; `subject_text_mismatch`: 5; `normalized_value_mismatch`: 5 | `no_candidate_same_source_predicate`: 146; `no_strict_match`: 97; `subject_text_mismatch`: 97; `subject_type_mismatch`: 77; `normalized_value_mismatch`: 97; `additional_candidate_duplicate`: 8 |
| `decision` | 1 | 5 | 0 | 5 | 1 | 0/1 | `no_candidate_same_source_predicate`: 1 | `no_candidate_same_source_predicate`: 5; `additional_candidate_duplicate`: 3 |
| `metric` | 7 | 25 | 0 | 25 | 7 | 0/7 | `no_candidate_same_source_predicate`: 1; `no_strict_match`: 6; `subject_text_mismatch`: 6; `normalized_value_mismatch`: 2; `qualifier_missing`: 6; `qualifier_mismatch`: 6 | `no_candidate_same_source_predicate`: 1; `no_strict_match`: 24; `subject_text_mismatch`: 24; `normalized_value_mismatch`: 19; `qualifier_missing`: 24; `qualifier_mismatch`: 24; `additional_candidate_duplicate`: 2 |
| `recommendation` | 4 | 0 | 0 | 0 | 4 | 0/4 | `no_candidate_same_source_predicate`: 4 | none |
| `requirement` | 4 | 15 | 0 | 15 | 4 | 0/4 | `no_candidate_same_source_predicate`: 4 | `no_candidate_same_source_predicate`: 15 |
| `risk` | 1 | 0 | 0 | 0 | 1 | 0/1 | `no_candidate_same_source_predicate`: 1 | none |

The aggregate reason-code inventory is:

| Reason code | Unmatched annotations | Unmatched candidates | Combined diagnostic rows |
| --- | ---: | ---: | ---: |
| `no_candidate_same_source_predicate` | 14 | 167 | 181 |
| `subject_text_mismatch` | 11 | 121 | 132 |
| `subject_type_mismatch` | 0 | 77 | 77 |
| `value_type_mismatch` | 0 | 0 | 0 |
| `normalized_value_mismatch` | 7 | 116 | 123 |
| `qualifier_missing` | 6 | 24 | 30 |
| `qualifier_mismatch` | 6 | 24 | 30 |
| `additional_candidate_duplicate` | 0 | 13 | 13 |
| `no_strict_match` | 11 | 121 | 132 |

Reason rows overlap: one annotation or candidate can carry multiple structural reasons.

## Required investigation findings

### Commitment over-triggering

Commitment contributed 243/288 candidates: S001 59, S002 97, S003 36 and S006 51. Its subject distribution is `other` 201, `organisation` 33, `policy` 7, `initiative` 1 and `programme` 1. No published commitment has `subject_type=metric`; the unpublished draft that failed S004 supplies the one diagnosed metric-subject incompatibility.

The raw-value trigger partition is exact and mutually exclusive:

| Trigger prefix | Count |
| --- | ---: |
| `commit to` | 3 |
| `has committed to` / `commits to` | 0 |
| `intend to` | 1 |
| `intends to` | 1 |
| `plan to` | 30 |
| `plans to` | 19 |
| `will not` | 2 |
| `will be` | 30 |
| other `will` | 157 |

The v0.1 actor-trigger regex treats each allowed future token as an explicit commitment and non-greedily assigns the preceding span as subject. It then assigns confidence `0.9` to 241/243 candidates. A bounded structural diagnostic identifies 86 clause-like commitment subjects; 5 subject spans are at least 80 characters. The median subject length is 19 characters. The combination of broad `will` eligibility, 30 generic `will be` values, 201 `other` actors and clause-like spans explains the dominant false-positive population.

### Requirement and decision

Requirement produced 15 candidates: S001 11, S002 2, S003 1 and S006 1. All begin with `must`, all have confidence `0.9`, 10 use `subject_type=other`, and 6 have clause-like subject spans. All are FP, although the four requirement annotations belong to failed S004, so development coverage cannot be assessed from a completed same-source output. The evidence supports actor/subject narrowing, not broader requirement coverage.

Decision produced five candidates, all from S006 and all confidence `0.9`; every subject is `other` and two are clause-like. The trigger partition is `agreed` 3, `decided` 1 and `approved` 1. None contains the proposal/option pattern considered for further exclusion, while the only decision annotation belongs to failed S004. Additional proposal exclusion is therefore not evidenced.

### Sparse or absent predicates

- Recommendation: PG-V01-S001-001, PG-V01-S001-002, PG-V01-S001-004 and PG-V01-S001-005 have no same-source recommendation candidate. The bounded evidence profile does not expose a stable numbered-recommendation or explicit-recommend construction, so the proposed heading expansion is excluded.
- Budget: PG-V01-S003-002 and PG-V01-S003-003 have no same-source budget candidate. Currency is present, but the v0.1 budget relationship cue is absent; accepting bare currency would be unsafe, so the change is excluded.
- Action status: PG-V01-S003-001 has an explicit progress cue but no recognized action-noun form. A bounded allowed-actor phrase extension is included with neutral negative tests.
- Metric: PG-V01-S003-004 has no same-source metric candidate. Six other metric annotations have close candidates, but qualifier attachment, subject text and sometimes normalized value disagree. Explicit qualifier extraction is included without changing matching.
- Risk: PG-V01-S004-005 belongs to the failed source and has no completed candidate result. The evidence is insufficient to define a new risk trigger, so the change is excluded.

The other no-same-source records are PG-V01-S004-001 through PG-V01-S004-004 (`requirement`) and PG-V01-S004-006 (`decision`); their absence reflects the failed source output and cannot establish rule recall.

### Structurally close candidates and matcher boundary

PG-V01-S002-001 through PG-V01-S002-005 each tie to the same 20 S002 commitment candidates at the closest two-field distance. Every tied pair fails both `subject_text_mismatch` and `normalized_value_mismatch`; no pair fails only one strict field. The 20 candidate IDs are:

`DET-CAND-0738140AFF7CAD987C3FD008F66256FADE226F48A0FC9F636F14C7D47E250C3F`, `DET-CAND-0EB12CD7392C9A941358BA020961F115BBC9B61059C249741390BA72EE5467F2`, `DET-CAND-17522A30E1EBB599F30FF2CEAC3F698AFAF6FFFC64D2C724BE50F6BB2B149D9A`, `DET-CAND-243E0C0A17921FA85B22FF4790DADA8671C5DB28A0C099627812498CF142DB9A`, `DET-CAND-244D3DAE8235B1ED20317615032BD43599C166F87C157693B5E2DCB662AC9FB8`, `DET-CAND-2A945A4FD746A93D81C561DD67A624113FA95CA2D8BD1E18B603671FFE2B9137`, `DET-CAND-3B8D73468CAB88F0A719DBBF23F8B8A16E286F634881730E9498E95813E45925`, `DET-CAND-4351C42D93D832C4ABF125E98589BDBDF53F0CFC292D0E032B8DA1349AA146BE`, `DET-CAND-749A0BB687A32AA17EC05079EB5227894424AE9836DA26C8A32EF08590685DA8`, `DET-CAND-7B8F03C76EA2C4FA6D0078D1FE928806DE9A2006AE699EA20FD37431CDA498BE`, `DET-CAND-9245AA21D326421AD6F42FF3A64E418C3BED73F2BE1A1FD4406784417FD39DC4`, `DET-CAND-A8C667D050BFA67FBCF5B823F7AA0AEFDC866ADFDFCB4039D4887FE089D8F2E0`, `DET-CAND-B0042ED4AED3357EAA9969A298E94258AFE499ACCC21AA821D0604F99EB24BB4`, `DET-CAND-B8379EED8EE4C9D032510072A469F2FC3C5367368DC1442D4012D46664D87914`, `DET-CAND-C98F9D3C69A6740F2A9B8CBB0D84853B9DE3B95FA88EADF0A916584456C9B594`, `DET-CAND-CB01C70B76A21EA577D75D253387FFD2042E967B4644311CB4D26A48D44248D1`, `DET-CAND-CD4FF72DADB90456D97CD0CAEACAFF7DAC2553C396DC49C6AE957ECA14744170`, `DET-CAND-D8754C69C01AE7FBF8347D7FB24EE334764027EEFBEB2EAA65ACC33071A06A9D`, `DET-CAND-EE5996E6EEE9FC1F5D705F7ED523379E454A8B2B129CE8FD505B0985927DEED5`, `DET-CAND-FE02C9AB4047C9C73DD0EFB63EDD141942476D395E199D6CA36EC305E48CC417`.

No observed candidate represents a true semantic pair hidden by a single protocol normalization issue. Crediting the closest S002 pairs would require ignoring two semantic fields, not correcting a matcher defect. Matching protocol `0.1` and strict normalization therefore remain unchanged.

### S006 review routing

The S006 challenge evidence is referenced by three published candidates: two commitments and one metric. Their confidence distribution is `0.7`: 1 and `0.9`: 2. All three have `evidence_status=supported`, `review_status=not_required` and no candidate warning. The source result contains `abstained_multiple_values` and `abstained_missing_subject`, but no emitted ambiguous candidate and no review-required candidate.

Thus v0.1 records only an abstention warning for the bounded ambiguous relationship while unrelated supported candidates share the challenge block. v0.2 must preserve those unrelated candidates and route each bounded plausible metric interpretation at confidence `0.5` for required review, rather than selecting one value.

## Error-family decisions

| error_family_id | v0.1 symptom | affected predicate | evidence count | structural reason codes | required or optional | proposed source-independent change | neutral test requirement | false-positive risk | false-negative risk | decision |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| EFM-001 | One incompatible S004 draft failed the whole source | `commitment` | 1 diagnosed draft | incompatible predicate/subject contract | Required | Validate every draft before construction; omit incompatible draft and warn | Metric-subject commitment plus unrelated valid candidate; repeat bytes | Guard could hide an unexpected defect if scoped broadly | Conservative abstention drops a recoverable fact | Include with narrow guard |
| EFM-002 | Commitment dominated output | `commitment` | 243 candidates | `no_strict_match`, `subject_text_mismatch`, `subject_type_mismatch`, `normalized_value_mismatch` | Required | Separate explicit commitment from weaker future intent; require eligible bounded actors; reject generic `will be` | Positive/negative tests for every trigger group, actor class, passive form and heading context | Weak future statements may still pass | Genuine future commitments may abstain | Include |
| EFM-003 | Ambiguous S006 relationship produced warning only | `metric` | 1 challenge class; 0 review candidates | `abstained_multiple_values` | Required | At no more than 3 values and 3 interpretations, emit every plausible pairing at confidence 0.5 with ambiguous evidence, required review and `ambiguous_metric_value_relationship`; otherwise abstain with `abstained_ambiguous_metric_bounds_exceeded` | Multiple values, plausible pairings, exact frozen ordering and both exceeded-bound cases | Multiple plausible candidates count as FP | Conservative cap may omit reviewable ambiguity | Include |
| EFM-004 | v0.1 experiment ID is hard-coded across report/run/freeze contracts | workflow | 7 protected core source modules plus versioned CLIs and shared contracts | version identity conflict | Required | Add separate one-document extractor CLI and prepare/finalize five-source workflow CLI, plus v0.2 rules, report/run models, orchestration and freeze modules | Import/identity and CLI-boundary tests prove v0.1/v0.2 and single/workflow entry points remain distinct | Duplicate code can drift | Reuse errors could retain v0.1 identity | Include |
| EFM-005 | One action-status annotation had no same-source candidate | `action_status` | 1 annotation | `no_candidate_same_source_predicate` | Optional | Add explicit progress/status phrases only for allowed actor types | Active actor positive; overall-project and descriptive negatives | Generic progress may over-trigger | Narrow actor list may miss valid actions | Include |
| EFM-006 | Generic `other` and clause subjects dominate actor-trigger rules | `commitment`, `requirement`, `decision` | 216 `other`; 94 clause-like across these rules | `subject_text_mismatch`, `subject_type_mismatch` | Optional | Validate bounded actor noun phrases and trim only structural residue | Allowed noun phrase, metric/population, impersonal, clause and prefix cases | Loose noun-phrase test retains noise | Unusual actors may abstain | Include |
| EFM-007 | Metric qualifier structure prevents close matches | `metric` | 6 annotations; 24 candidate diagnostics | `qualifier_missing`, `qualifier_mismatch` | Optional | Extract explicit same-statement name, population, unit and period; route competing attachments | Complete, missing and competing qualifier fixtures | Nearby qualifier may attach incorrectly | Strict attachment may stay incomplete | Include |
| EFM-008 | Requirement produced only FP in completed outputs | `requirement` | 15 candidates | `no_candidate_same_source_predicate` | Optional | Require mandatory trigger plus eligible bounded actor/action | Obligation positive; guidance, impersonal and clause negatives | Formal prose may remain noisy | Genuine passive obligations may abstain | Include |
| EFM-009 | Exact semantic duplicates inflate candidate population | all | 7 extra duplicates | `additional_candidate_duplicate` | Optional | Key exact ordered source ID, normalized subject, subject type, predicate, value type, typed normalized value and sorted qualifiers; retain first by block sequence, statement offset, rule priority and stable signature | Exact duplicate, each single-field near-distinct case and retained-order fixture | Key could collapse distinct facts | Paraphrase duplicates remain | Include |
| EFM-010 | S001 recommendation annotations had no candidate | `recommendation` | 4 annotations | `no_candidate_same_source_predicate` | Optional | Proposed heading/number inference lacks a stable observed cue | Would require positive and arbitrary-number negatives | Heading numbers are easily over-read | Exclusion retains misses | Exclude as speculative |
| EFM-011 | S003 budget annotations had no candidate | `budget` | 2 annotations | `no_candidate_same_source_predicate` | Optional | No safe relationship relaxation identified | Would require bare-currency negatives | Bare currency becomes budget | Exclusion retains misses | Exclude as unsafe |
| EFM-012 | Risk annotation is on failed source | `risk` | 1 annotation, 0 completed source results | `no_candidate_same_source_predicate` | Optional | No new trigger until completed development evidence exists | No evidenced neutral rule boundary | Generic risk language over-triggers | Exclusion retains miss | Exclude as insufficient evidence |
| EFM-013 | Proposed decision exclusion has no observed candidate example | `decision` | 0 proposal/option candidates | none | Optional | Retain existing proposal guard unchanged | Existing neutral proposal tests remain | Extra exclusions could reject decisions | No additional risk from exclusion | Exclude as unsupported |
