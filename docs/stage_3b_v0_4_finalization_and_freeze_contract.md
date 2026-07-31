# Stage 3B.5E-1 v0.4 finalization and freeze contract

## Status and boundary

This milestone implements and tests the additive `deterministic-baseline-v0.4` development-finalization transaction. It does not freeze v0.4. No real development finalization has run, no real finalization output has been created and no held-out execution is authorized.

The R1 safety and provenance correction remains pending an independent read-only review. The earlier independent review record covers the owner-assessment package; it does not approve this correction.

Finalization is separate from owner review because the owner supplies qualitative challenge judgments, while finalization verifies immutable inputs, reproduces machine outputs, reconciles metrics and installs process evidence. The implementation must be independently reviewed and merged before real execution so the first real transaction runs against an immutable implementation commit.

A later valid freeze preserves development process evidence. It does not establish production readiness, exhaustive precision or held-out generalization.

## Authoritative commits

| Boundary | Commit |
| --- | --- |
| v0.4 semantic implementation merge | `4e6a7af3cc4ad86b157485d99cd6cdd472e4a4bc` |
| owner-review preparation merge | `36fe312ef07716a3597ea62a5d146a12b1c9312b` |
| owner-assessment feature commit | `bd9c7413a386c461bebc88f3e6ed5df7b19e7825` |
| owner-assessment merge / PR #21 | `d9cddfd21a302151213ea5cde27f400a382e1e64` |
| parser commit | `71148262f094d54ec7d95e45958bd1aaefc64793` |

All four v0.4 commits must be ancestors of the future finalization implementation commit.

## Fixed development observation

The exact source order is `S001`, `S002`, `S003`, `S004`, `S006`. The exact challenge order is `PGC-V01-S001-001`, `PGC-V01-S004-001`, `PGC-V01-S006-001`.

| Source | Candidates | Candidate SHA-256 | ParsedDocument SHA-256 |
| --- | ---: | --- | --- |
| S001 | 32 | `2D7668A267586A1B370C23FB856A94D39D661137ED3217B3102569ED5CDA0AD1` | `F688930865E34C738B848169BF7C53A8F5373D7555119B747D9731A2DFD74ECE` |
| S002 | 18 | `3DD2760F0398E88E624F77168197CBB41B99635E32211075FBB907ECBA011C92` | `39A8E6C106480A72CF907E3981D38CC2D84E6E4197DE7F791945C20F32881D4C` |
| S003 | 13 | `9CB4151E66B80C5FCF25E7102C3B5A9B233D767FF0524261BD04C9C0FFCC670B` | `8002DC78C9F6716156226FB48F6E673CB71F65ED914B474D8640BF4A095801E0` |
| S004 | 30 | `30522C9B3D285CF099AAB4F3F512B6F843340BA5FECD1BB7E58AE0085731D243` | `268F07D63B0202100E0131A30EAF122554435520F9228E752DC35E4AAB8A83D2` |
| S006 | 85 | `7E6DF1EAD8F9BA4F95A5F53AC8D36B55D3B537BDE14FB083CEE6395717664C98` | `D1BDB1166506E7C9A1A4725D374585BFC69A07A5D744C95D09B1DECCD766BCE2` |

The fixed total is 178 candidates. Predicate counts are action status 2, budget 2, commitment 25, decision 3, metric 84, recommendation 22, requirement 34 and risk 6. Non-commitment semantic and resolved-evidence parity with v0.3 is 153/153.

Strict matching remains unchanged and yields TP 5, FP 173, FN 20, precision 5/178 (`0.028089887640449437`), recall 5/25 (`0.2`), F1 10/203 (`0.04926108374384237`) and duplicate count 0. The exact matched annotations are:

1. `PG-V01-S001-001`
2. `PG-V01-S001-004`
3. `PG-V01-S003-001`
4. `PG-V01-S003-002`
5. `PG-V01-S003-003`

S002 has zero strict matches.

## Authoritative evidence hashes

| Evidence | SHA-256 |
| --- | --- |
| v0.4 config | `6D659638C732102D3CB4AB77DDE17229E1E36129245266F213D7FA29217A405A` |
| comparison JSON | `AD7DC43386A693553240587367ACCB84A3BF353FAFB8930575CDB484E2A8D8B8` |
| actor/value diagnosis JSON | `FC8EEFC61B307538948438ABBFF96F1280F1A9006DFFF56ED81A49FD69DE9573` |
| owner-review preparation manifest | `A401ABCEB77D9B73557283D12770DCF33E04E6DED7EEFE361719DF70678AB844` |
| blank owner template | `33991E3BA481FE4079EFAF9C6E938BB347F058F8AA2870ED92DD505FA790F859` |
| owner review packet | `0C95A1961E8C73409D9737E0C6A6DCB5AEEFDC3933CD75D10D78B650DD57B56E` |
| completed owner assessment | `8B1BEE334AAE3A1F3AF6A5DF8B9FBC039FE9DB79BBA9CEC931BE019DA68D7419` |
| owner validation report | `D7940A01E30FF1F0B735CCE94504BC76A23F0EB1BF6454F6264D7D56ED557E94` |
| owner assessment Markdown | `8F0ECA3E37A97198CE8C24737274317F2394077F7F71EB6860132D530411D309` |
| independent-review record | `58455CA84300C94D0DCB1AEAF0EC30023BB22EF4FDC1BF598A77DA40AAC9E0D9` |
| public-gold facts | `CA38D77B323220D5E51877F87D4BEAD901A0DE6A3493EDBFF6AF691C2027A690` |
| public-gold cases | `328844F6CD1D5E74A62FEC37B912D807FD3ABFFCC6F935A7985A5576C802A237` |
| strict matcher | `D3FA0EA195381586064E6716D0141B25BCE0A861CE9B8192FEAF26D818A554EC` |
| matching protocol | `18FD851347B395C2D54B6B02B632E94D3C4B15CFBD16A31C04EE2923D0991530` |

The preparation manifest remains authoritative for its additional 16-file protected committed-blob inventory. Finalization loads and verifies that inventory rather than maintaining a second competing list.

## Owner and machine provenance

Formal owner outcomes are three passed, zero failed and zero pending. They were supplied through `project_owner_review` and retain their owner-authored rationales. Automated diagnostics are separately recorded as three passed and did not populate the owner outcomes or rationales.

The additive independent-review record documents the later read-only audit of the completed owner package and public file boundary. Its verdict is `approved_for_commit`, with zero critical findings and zero required corrections. It is machine review evidence, not an owner judgment, extraction result, baseline freeze or held-out authorization. The historical owner validation report remains unchanged with its then-current independent-review status.

The development evaluation report, finalization record and freeze manifest each carry the same strict provenance object. It pins the three fixed upstream merge commits, the clean execution-time finalization implementation commit, corpus and schema versions, the parser commit, all core evidence hashes, the ordered five-source ParsedDocument hashes and identical ordered primary/repeat candidate hashes. Public validation reloads all three objects, requires exact equality and independently reconciles committed evidence and installed candidate bytes. The report contains no self-hash and no finalization-record or freeze-manifest hash, so this shared provenance creates no circular hash dependency.

## Candidate-output reproduction contract

Future finalization must:

1. resolve the exact Git repository root and require a clean tree;
2. verify authoritative commit ancestry and every protected evidence hash;
3. accept exactly the five fixed development ParsedDocument filenames and hashes;
4. verify the fixed ingestion-report hash;
5. load gold only through guarded development access;
6. invoke unchanged `extract_deterministic_candidates_v0_4` twice per source;
7. validate candidate schema `0.1` and canonical bytes;
8. require primary and repeat bytes and hashes to match for every source;
9. require all source, predicate and total counts to match the fixed observation;
10. invoke unchanged `match_strict_facts` and require the exact metrics and matches above.

The operation accepts no arbitrary experiment, source, gold, matcher, network, LLM, tuning or held-out option. Any post-v0.4 semantic change requires v0.5.

## Process acceptance gates

The fixed ordered, fail-closed gate inventory is:

1. `required_commit_ancestry_valid`
2. `repository_clean_before_finalization`
3. `exact_development_source_inventory`
4. `exact_development_challenge_inventory`
5. `protected_v0_4_hashes_valid`
6. `owner_preparation_hashes_valid`
7. `completed_owner_assessment_hash_valid`
8. `owner_validation_report_hash_valid`
9. `independent_review_record_valid`
10. `parsed_document_hashes_valid`
11. `all_sources_complete_both_passes`
12. `zero_unhandled_extraction_exceptions`
13. `candidate_schema_valid`
14. `repeat_outputs_byte_identical`
15. `candidate_output_hashes_match_preparation`
16. `candidate_counts_reconciled`
17. `strict_matches_reconciled`
18. `exact_metrics_reconciled`
19. `owner_assessments_complete`
20. `owner_and_machine_provenance_separate`
21. `automated_challenge_diagnostics_reconciled`
22. `no_post_v0_4_semantic_change`
23. `source_independent_rules`
24. `sparse_gold_limitation_preserved`
25. `held_out_semantics_not_loaded`
26. `held_out_execution_not_authorized`
27. `output_transaction_complete`
28. `artifact_identities_agree`

Every gate appears exactly once, in this order, with outcome `passed` and bounded path-free evidence. There is no minimum-F1 gate.

## Non-binding quality observations

Quality observations are separate from process acceptance:

| Observation | Outcome | Exact evidence |
| --- | --- | --- |
| `strict_tp_greater_than_zero` | `met` | Five strict true positives were observed. |
| `total_candidates_below_v0_2` | `met` | 178 candidates is below the v0.2 total. |
| `commitment_candidates_below_v0_2` | `met` | 25 commitments is below the v0.2 total. |
| `duplicate_candidate_count_zero` | `met` | Strict duplicate count is zero. |
| `owner_challenge_pass_rate_three_of_three` | `met` | Formal owner outcomes are 3 of 3 passed. |
| `ambiguous_metric_relationship_routed_to_review` | `met` | Ambiguous metric relationships remain routed to review. |
| `s002_strict_commitment_recovery` | `not_met` | S002 has zero strict matches. |
| `f1_above_zero` | `met` | Observed strict F1 is above zero. |
| `exhaustive_precision_established` | `not_applicable` | Sparse gold cannot establish exhaustive precision. |

Each item is fixed to `deterministic-baseline-v0.4` and `non_binding=true`. The exact ordered tuple of experiment ID, observation ID, outcome, evidence and non-binding status is required in the report, finalization record and freeze manifest. The selected 25-fact development gold is deliberately sparse. Official strict FP and precision remain useful comparison metrics, but unmatched candidates are not independently confirmed semantic errors.

## Transaction and future output inventory

Before any filesystem creation or write, the transaction resolves the exact Git root, requires a clean tree, requires the fixed output root, validates the complete existing chains through `primary` and `repeat`, and snapshots the output-root topology. The snapshot records output-relative paths, file/directory/link/reparse type, raw regular-file SHA-256, link target and whether the root existed; it excludes timestamps, hostnames and absolute paths.

All fourteen payloads are built and validated in a unique transaction workspace under the approved ignored `artifacts/stage_3b/v0_4_finalization_transactions` location, outside the final output root. Backups also remain in that workspace. Installation is restricted to the fixed inventory, revalidates both path chains immediately before every backup and replacement, and installs the freeze manifest last.

Rollback capability remains independent of the transaction workspace. Before installation, an in-memory capsule retains the complete pre-transaction topology, output-root existence, exact relative target identities, raw bytes for every pre-existing fixed target and transaction-created directory tracking. Workspace cleanup is not the transaction commit point, and deleting workspace backups does not discard these recoverable prior-output bytes.

Rollback removes only files installed by the transaction, restores every prior fixed target from the capsule through safely staged atomic replacement, removes transaction temporary content, and removes only explicitly recorded transaction-created directories, deepest first and only while empty. An initially absent output root therefore becomes absent again; a pre-existing output root, owner evidence, directories and unrelated files remain exactly preserved. A failure after workspace removal or during final cleanup and residue validation still restores the exact prior topology. The post-rollback topology must equal the pre-transaction snapshot or the operation raises a bounded restoration error. The implementation never recursively deletes the authorized output root.

Every existing path component is inspected with `os.lstat`. Symbolic links, junctions and Windows reparse points, lexical parent traversal, repository escape and output-root escape are rejected. Safety and exact parent/filename identity are rechecked immediately before each filesystem mutation. The workflow assumes a trusted local run without hostile concurrent filesystem mutation; if concurrent unrelated content changes, topology verification fails closed and does not delete that content.

After successful installation, all fourteen artifacts and their cross-references are validated, the six owner-review files must remain byte-identical, and the external transaction workspace must be absent. Recoverable capsule data remains available through every fallible cleanup, residue and final validation step; the transaction commits only when the function returns successfully. R2 remains pending final independent read-only review.

Exactly fourteen future files are permitted:

- `primary/S001.json`, `primary/S002.json`, `primary/S003.json`, `primary/S004.json`, `primary/S006.json`
- `repeat/S001.json`, `repeat/S002.json`, `repeat/S003.json`, `repeat/S004.json`, `repeat/S006.json`
- `development_evaluation_report.json`
- `final_error_analysis.json`
- `finalization_record.json`
- `baseline_freeze_manifest.json`

The bounded final error analysis may report strict structural mismatches, counts, review routing, owner outcomes and limitations. It may not reinterpret every unmatched candidate as semantically wrong, claim manual review of all unmatched candidates, introduce fuzzy or LLM classification, generalize to held-out data or claim production readiness.

## Public commands and future sequence

Read-only audit:

```text
python -m document_intelligence.extraction.development_finalization_v0_4_cli audit --repository-root .
```

Future real finalization, only after this implementation is reviewed and merged:

```text
python -m document_intelligence.extraction.development_finalization_v0_4_cli finalize --repository-root . --parsed-root artifacts/stage_3b/development_parsed --ingestion-report artifacts/stage_3b/development_ingestion_report.json --output-root evaluation/baselines/deterministic-baseline-v0.4/development --freeze-date YYYY-MM-DD
```

Read-only installed-artifact validation:

```text
python -m document_intelligence.extraction.development_finalization_v0_4_cli validate --repository-root . --output-root evaluation/baselines/deterministic-baseline-v0.4/development
```

The controlled sequence is: complete implementation tests; obtain independent read-only review; merge the implementation; rerun the public audit on the merge commit; run real finalization once with an explicit date; validate all fourteen installed files; independently review the generated evidence; then commit the evidence only if every process gate passes. Held-out execution remains blocked behind a later separate guard and explicit authorization.
